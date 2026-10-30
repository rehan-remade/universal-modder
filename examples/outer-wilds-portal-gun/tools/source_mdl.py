"""Reader for Source engine studio models, MDL v44-49 (Portal 2 is v49) + VVD v4 + VTX v7.

Reads what a runtime needs: bones, LOD0 mesh per material with bone weights, textures, attachments,
sequences with their events, and the compressed animations decoded to per-frame local bone poses.
All values stay in Source space (Z up, X forward, inches); the converter changes axes.
"""
import math
import struct

import numpy as np

# mstudioanim_t flags
ANIM_RAWPOS, ANIM_RAWROT, ANIM_ANIMPOS, ANIM_ANIMROT, ANIM_DELTA, ANIM_RAWROT2 = 1, 2, 4, 8, 16, 32


def cstr(data, off):
    end = data.index(b"\0", off)
    return data[off:end].decode("latin-1")


def euler_to_quat(x, y, z):
    """Source AngleQuaternion(RadianEuler)."""
    sr, cr = math.sin(x * 0.5), math.cos(x * 0.5)
    sp, cp = math.sin(y * 0.5), math.cos(y * 0.5)
    sy, cy = math.sin(z * 0.5), math.cos(z * 0.5)
    return (sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy)


def quat48(b):
    x, y, zw = struct.unpack("<HHH", b)
    z, wneg = zw & 0x7FFF, zw >> 15
    x = (x - 32768) / 32768.0
    y = (y - 32768) / 32768.0
    z = (z - 16384) / 16384.0
    w = math.sqrt(max(0.0, 1.0 - x * x - y * y - z * z))
    return (x, y, z, -w if wneg else w)


def quat64(b):
    v = int.from_bytes(b, "little")
    x = ((v & 0x1FFFFF) - 1048576) / 1048576.5
    y = (((v >> 21) & 0x1FFFFF) - 1048576) / 1048576.5
    z = (((v >> 42) & 0x1FFFFF) - 1048576) / 1048576.5
    wneg = v >> 63
    w = math.sqrt(max(0.0, 1.0 - x * x - y * y - z * z))
    return (x, y, z, -w if wneg else w)


def vec48(b):
    return tuple(float(v) for v in np.frombuffer(b, dtype="<f2"))


def anim_value(data, off, frame):
    """Extract one value from a run-length mstudioanimvalue_t stream at `off`."""
    k = frame
    while True:
        valid, total = data[off], data[off + 1]
        if total == 0:
            return 0
        if k < total:
            break
        k -= total
        off += (valid + 1) * 2
    if k < valid:
        return struct.unpack_from("<h", data, off + (k + 1) * 2)[0]
    return struct.unpack_from("<h", data, off + valid * 2)[0]


class Model:
    def __init__(self, mdl, vvd, vtx):
        self.mdl = mdl
        h = mdl
        ident, self.version = struct.unpack_from("<4si", h, 0)
        if ident != b"IDST":
            raise ValueError("not a studio model")
        self.name = cstr(h, 12)
        (self.numbones, self.boneindex, _nbc, _bci, _nhs, _hsi, self.numanim, self.animindex,
         self.numseq, self.seqindex, _alv, _ei, self.numtextures, self.textureindex,
         self.numcdtextures, self.cdtextureindex, self.numskinref, self.numskinfamilies,
         self.skinindex, self.numbodyparts, self.bodypartindex, self.numattach,
         self.attachindex) = struct.unpack_from("<23i", h, 156)
        self._bones()
        self._textures()
        self._attachments()
        self._mesh(vvd, vtx)
        self._sequences()

    # --- skeleton -------------------------------------------------------------------------------
    def _bones(self):
        self.bones = []
        for i in range(self.numbones):
            o = self.boneindex + i * 216
            nameoff, parent = struct.unpack_from("<ii", self.mdl, o)
            pos = struct.unpack_from("<3f", self.mdl, o + 32)
            quat = struct.unpack_from("<4f", self.mdl, o + 44)
            rot = struct.unpack_from("<3f", self.mdl, o + 60)
            posscale = struct.unpack_from("<3f", self.mdl, o + 72)
            rotscale = struct.unpack_from("<3f", self.mdl, o + 84)
            pose_to_bone = np.array(struct.unpack_from("<12f", self.mdl, o + 96), dtype=np.float64).reshape(3, 4)
            self.bones.append(dict(name=cstr(self.mdl, o + nameoff), parent=parent, pos=pos, quat=quat,
                                   rot=rot, posscale=posscale, rotscale=rotscale, pose_to_bone=pose_to_bone))

    def _textures(self):
        self.textures = []
        for i in range(self.numtextures):
            o = self.textureindex + i * 64
            self.textures.append(cstr(self.mdl, o + struct.unpack_from("<i", self.mdl, o)[0]))
        self.cdtextures = [cstr(self.mdl, struct.unpack_from("<i", self.mdl, self.cdtextureindex + 4 * i)[0])
                           for i in range(self.numcdtextures)]
        self.skins = []
        for f in range(self.numskinfamilies):
            o = self.skinindex + f * self.numskinref * 2
            self.skins.append(list(struct.unpack_from(f"<{self.numskinref}h", self.mdl, o)))

    def _attachments(self):
        self.attachments = []
        for i in range(self.numattach):
            o = self.attachindex + i * 92
            nameoff, flags, bone = struct.unpack_from("<iii", self.mdl, o)
            m = np.array(struct.unpack_from("<12f", self.mdl, o + 12), dtype=np.float64).reshape(3, 4)
            self.attachments.append(dict(name=cstr(self.mdl, o + nameoff), bone=bone, local=m))

    # --- mesh -----------------------------------------------------------------------------------
    def _mesh(self, vvd, vtx):
        ident, ver, _ck, numlods = struct.unpack_from("<4siii", vvd, 0)
        lodverts = struct.unpack_from("<8i", vvd, 16)
        numfix, fixstart, vstart, _tstart = struct.unpack_from("<4i", vvd, 48)
        raw = np.frombuffer(vvd, dtype=np.uint8, count=lodverts[0] * 48 if numfix == 0 else -1, offset=vstart)
        allv = raw[: (len(raw) // 48) * 48].reshape(-1, 48)
        if numfix:
            rows = []
            for i in range(numfix):
                lod, src, n = struct.unpack_from("<3i", vvd, fixstart + 12 * i)
                if lod >= 0:
                    rows.append(allv[src:src + n])
            allv = np.concatenate(rows)
        allv = np.ascontiguousarray(allv)
        self.weights = allv[:, 0:12].copy().view("<f4").reshape(-1, 3)
        self.weight_bones = allv[:, 12:15].astype(np.int32)
        self.weight_count = allv[:, 15].astype(np.int32)
        self.positions = allv[:, 16:28].copy().view("<f4").reshape(-1, 3).astype(np.float64)
        self.normals = allv[:, 28:40].copy().view("<f4").reshape(-1, 3).astype(np.float64)
        self.uvs = allv[:, 40:48].copy().view("<f4").reshape(-1, 2).astype(np.float64)

        # VTX: strip groups in Portal 2 era files carry topology fields (33/35-byte headers).
        tver, = struct.unpack_from("<i", vtx, 0)
        nbp, bpoff = struct.unpack_from("<ii", vtx, 28)
        self.submeshes = []  # (body part name, model name, material index, triangles[N,3] global vertex ids)
        for ext in (True, False):
            try:
                self.submeshes = self._read_vtx(vtx, nbp, bpoff, ext)
                break
            except (IndexError, struct.error, ValueError):
                self.submeshes = []
        if not self.submeshes:
            raise ValueError("could not parse VTX")

    def _read_vtx(self, vtx, nbp, bpoff, ext):
        sg_size, strip_size = (33, 35) if ext else (25, 27)
        out = []
        for b in range(self.numbodyparts):
            mbp = self.bodypartindex + b * 16
            bpname = cstr(self.mdl, mbp + struct.unpack_from("<i", self.mdl, mbp)[0])
            nummodels, _base, modelindex = struct.unpack_from("<3i", self.mdl, mbp + 4)
            vbp = bpoff + b * 8
            vnm, vmoff = struct.unpack_from("<ii", vtx, vbp)
            for m in range(nummodels):
                mm = mbp + modelindex + m * 148
                mname = cstr(self.mdl, mm)
                nummeshes, meshindex, numverts, vertexindex = struct.unpack_from("<4i", self.mdl, mm + 72)
                vstart = vertexindex // 48
                vm = vbp + vmoff + m * 8
                nlods, lodoff = struct.unpack_from("<ii", vtx, vm)
                vl = vm + lodoff  # LOD 0
                vnmesh, vmeshoff = struct.unpack_from("<ii", vtx, vl)
                if vnmesh != nummeshes:
                    raise ValueError("mesh count mismatch")
                for k in range(nummeshes):
                    ms = mm + meshindex + k * 116
                    material, _mi, mnv, mvoff = struct.unpack_from("<4i", self.mdl, ms)
                    vme = vl + vmeshoff + k * 9
                    nsg, sgoff = struct.unpack_from("<ii", vtx, vme)
                    tris = []
                    for g in range(nsg):
                        sg = vme + sgoff + g * sg_size
                        nv, voff, ni, ioff, ns, soff = struct.unpack_from("<6i", vtx, sg)
                        if nv < 0 or ni < 0 or ni % 3 or nv > 65536 or ns > 4096:
                            raise ValueError("bad strip group")
                        vids = np.array([struct.unpack_from("<H", vtx, sg + voff + 9 * i + 4)[0]
                                         for i in range(nv)], dtype=np.int64)
                        idx = np.frombuffer(vtx, dtype="<u2", count=ni, offset=sg + ioff).astype(np.int64)
                        for s in range(ns):
                            st = sg + soff + s * strip_size
                            sni, sio, _snv, _svo = struct.unpack_from("<4i", vtx, st)
                            flags = vtx[st + 18]
                            seg = idx[sio:sio + sni]
                            if flags & 2:  # tristrip
                                t = []
                                for i in range(len(seg) - 2):
                                    a, bb, c = seg[i], seg[i + 1], seg[i + 2]
                                    t.append((a, bb, c) if i % 2 == 0 else (bb, a, c))
                                seg = np.array(t, dtype=np.int64).reshape(-1)
                            tri = vids[seg].reshape(-1, 3) + vstart + mvoff
                            if tri.max(initial=0) >= len(self.positions):
                                raise ValueError("vertex out of range")
                            tris.append(tri)
                    if tris:
                        out.append((bpname, mname, material, np.concatenate(tris)))
        return out

    # --- animation ------------------------------------------------------------------------------
    def _sequences(self):
        self.anims = []
        for i in range(self.numanim):
            o = self.animindex + i * 100
            (base, nameoff, fps, flags, numframes) = struct.unpack_from("<iifii", self.mdl, o)
            animblock, animindex = struct.unpack_from("<ii", self.mdl, o + 52)
            sectionindex, sectionframes = struct.unpack_from("<ii", self.mdl, o + 80)
            self.anims.append(dict(name=cstr(self.mdl, o + nameoff), fps=fps, flags=flags, numframes=numframes,
                                   offset=o, animblock=animblock, animindex=animindex,
                                   sectionindex=sectionindex, sectionframes=sectionframes))
        self.sequences = []
        for i in range(self.numseq):
            o = self.seqindex + i * 212
            label = cstr(self.mdl, o + struct.unpack_from("<i", self.mdl, o + 4)[0])
            act = cstr(self.mdl, o + struct.unpack_from("<i", self.mdl, o + 8)[0])
            flags, = struct.unpack_from("<i", self.mdl, o + 12)
            numevents, eventindex = struct.unpack_from("<ii", self.mdl, o + 24)
            animindexindex, = struct.unpack_from("<i", self.mdl, o + 60)
            anim, = struct.unpack_from("<h", self.mdl, o + animindexindex)
            events = []
            for e in range(numevents):
                eo = o + eventindex + e * 80
                cycle, event, etype = struct.unpack_from("<fii", self.mdl, eo)
                options = cstr(self.mdl, eo + 12)
                nameoff, = struct.unpack_from("<i", self.mdl, eo + 76)
                name = cstr(self.mdl, eo + nameoff) if nameoff else ""
                events.append(dict(cycle=cycle, event=event, type=etype, options=options, name=name))
            self.sequences.append(dict(name=label, activity=act, looping=bool(flags & 1), anim=anim,
                                       events=events))

    def anim_frames(self, a):
        """Local (pos, quat) per bone per frame for anim index `a`: arrays [F, B, 3] and [F, B, 4]."""
        ad = self.anims[a]
        nf, nb = ad["numframes"], self.numbones
        pos = np.zeros((nf, nb, 3))
        quat = np.zeros((nf, nb, 4))
        for f in range(nf):
            if ad["animblock"] != 0:
                raise ValueError(f"{ad['name']}: data lives in an .ani block")
            if ad["sectionframes"]:
                sec = f // ad["sectionframes"]
                local = f - sec * ad["sectionframes"]
                blk, aidx = struct.unpack_from("<ii", self.mdl, ad["offset"] + ad["sectionindex"] + 8 * sec)
                start = ad["offset"] + aidx
            else:
                local = f
                start = ad["offset"] + ad["animindex"]
            seen = set()
            p = start
            while True:
                bone, flags, nxt = struct.unpack_from("<BBh", self.mdl, p)
                b = self.bones[bone]
                d = p + 4
                delta = flags & ANIM_DELTA
                if flags & ANIM_RAWROT:
                    q = quat48(self.mdl[d:d + 6])
                elif flags & ANIM_RAWROT2:
                    q = quat64(self.mdl[d:d + 8])
                elif flags & ANIM_ANIMROT:
                    e = []
                    for c in range(3):
                        off, = struct.unpack_from("<h", self.mdl, d + 2 * c)
                        v = anim_value(self.mdl, d + off, local) * b["rotscale"][c] if off else 0.0
                        e.append(v + (0 if delta else b["rot"][c]))
                    q = euler_to_quat(*e)
                else:
                    q = (0, 0, 0, 1) if delta else b["quat"]
                if flags & ANIM_RAWPOS:
                    po = d + (6 if flags & ANIM_RAWROT else 0) + (8 if flags & ANIM_RAWROT2 else 0)
                    v = vec48(self.mdl[po:po + 6])
                elif flags & ANIM_ANIMPOS:
                    pv = d + (6 if flags & ANIM_ANIMROT else 0)
                    v = []
                    for c in range(3):
                        off, = struct.unpack_from("<h", self.mdl, pv + 2 * c)
                        v.append((anim_value(self.mdl, pv + off, local) * b["posscale"][c] if off else 0.0)
                                 + (0 if delta else b["pos"][c]))
                else:
                    v = (0, 0, 0) if delta else b["pos"]
                pos[f, bone] = v
                quat[f, bone] = q
                seen.add(bone)
                if nxt == 0:
                    break
                p += nxt
            for i in range(nb):
                if i not in seen:
                    pos[f, i] = self.bones[i]["pos"]
                    quat[f, i] = self.bones[i]["quat"]
        return pos, quat
