"""Template records for the writers, taken from the user's own Native module at run time.

Two writers start from an existing record and patch it: clips (tpac.write_clip) and materials (tpac.write_material).
Nothing is shipped: the records are read from the game install (config.NATIVE) and kept in memory only.

  clip_template()            a plain Native clip record: no sound, voice, facial, partner, follow-up or combat
                             parameter, no flag or parameter lists (the shape the editor writes for a new clip).
                             The scan looks at the metadata of Native's animation packages only.
  material_template(skinned) a pbr_shading record: no material flags, opaque, the vertex layout empty (or only
                             "skinning"), shader flags use_specular + do_not_use_vertex_color_as_occlusion, no textures.
                             Head, parameters and alpha reference come from a Native pbr_shading record.

Both accept an explicit file (a package written by the editor or by this SDK) that wins over Native:
  clip_template(path=...), material_template(skinned, path=...); the CLI exposes it as --template <file>.

  python templates.py        print which Native records were picked
"""
import collections, glob, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, tpac, tw_formats

_clip_cache = {}
_mtl_cache = {}


def _native_items(sub_dirs, type_guid):
    """(package path, item) of every item of one type in Native packages (metadata only, no data blobs)."""
    config.require_game()
    for sub in sub_dirs:
        for p in sorted(glob.glob(os.path.join(config.NATIVE, sub, "**", "*.tpac"), recursive=True)):
            try:
                items = tw_formats.read_package_index(p)
            except Exception:
                continue
            for it in items:
                if it["type"] == type_guid:
                    yield p, it


def _plain_clip(rec):
    """True for a clip record in the editor's default shape (144 bytes, empty strings and lists, no parameters)."""
    if len(rec) != 144 or struct.unpack_from("<Q", rec, 0)[0] != 0x88:
        return False
    try:
        r = tpac.parse_clip(rec, 0)
    except Exception:
        return False
    if r["sound"] or r["voice"] or r["facial"] or r["blends_with"] or r["continue_with"] or r["combat"] or r["anim2"]:
        return False
    f = r["fixed"]
    return (r["lists"] == bytes(8) and struct.unpack_from("<I", f, 8)[0] == 6 and bytes(f[24:40]) == bytes(16)
            and struct.unpack_from("<4f", f, 56) == (-1.0, -1.0, -1.0, -1.0))


def clip_template(path=None):
    """{"record": bytes, "source": str}: the 144-byte clip record writers patch."""
    key = path or ""
    if key in _clip_cache:
        return _clip_cache[key]
    if path:
        items = tw_formats.walk_package(open(path, "rb").read())
        clips = [i for i in items if i["type"] == tpac.CLIP_TYPE]
        if len(clips) != 1:
            sys.exit("%s: expected one clip, found %d" % (path, len(clips)))
        rec = bytes(clips[0]["record"])
        if not _plain_clip(rec):
            sys.exit("%s: not a plain clip record (empty strings and lists, 144 bytes); pick a clip written with default settings" % path)
        out = {"record": rec, "source": path}
    else:
        # the editor's default clip is the most common shape among plain Native clips (blend time, unknown bytes, int pair)
        found = []
        for p, it in _native_items(["EmAssetPackages/animations"], tpac.CLIP_TYPE):
            if _plain_clip(it["record"]):
                r = tpac.parse_clip(bytes(it["record"]), 0)
                found.append(((r["ints"], r["blend"], r["misc"]), it["name"], bytes(it["record"]), p))
        if not found:
            sys.exit("no plain clip record found in Native's animation packages: pass --template <clip package> "
                     "(a clip written by the Modding Kit with default settings)")
        shape = collections.Counter(f[0] for f in found).most_common(1)[0][0]
        best = min((f[1:] for f in found if f[0] == shape), key=lambda f: f[0])
        out = {"record": best[1], "source": "Native clip %s (%s)" % (best[0], os.path.relpath(best[2], config.NATIVE))}
    _clip_cache[key] = out
    return out


def material_template(skinned=False, path=None):
    """(parsed material record, source description). parse_mtl fields; tex is empty."""
    key = (bool(skinned), path or "")
    if key in _mtl_cache:
        return _mtl_cache[key]
    if path:   # an explicit template is used as it is (flags, blend mode, textures), only the skinning layout follows `skinned`
        r = tpac.read_mtl_file(path)
        t = dict(r, vlayout=[v for v in r["vlayout"] if v != "skinning"] + (["skinning"] if skinned else []))
        _mtl_cache[key] = (t, path)
        return _mtl_cache[key]
    else:
        sg = tpac.find_shader("pbr_shading")
        best = None
        for p, it in _native_items(["EmAssetPackages", "AssetPackages"], tpac.MTL_TYPE):
            try:
                r, _ = tpac.parse_mtl(bytes(it["record"]) + bytes(8), 0)
            except Exception:
                continue
            if r["shader"] != sg or r["mflags"] or r["vlayout"] or r["blend"] != "no_alpha_blend" or "use_specular" not in r["sflags"]:
                continue
            score = (len(r["sflags"]), len(r["tex"]) != 2, it["name"])   # the plainest: fewest shader flags, diffuse + specular only
            if best is None or score < best[0]:
                best = (score, r, "Native material %s (%s)" % (it["name"], os.path.relpath(p, config.NATIVE)))
        if best is None:
            sys.exit("no pbr_shading material found in Native: pass --template <material package>")
        r, src = best[1], best[2]
    t = dict(r, mflags=[], vlayout=["skinning"] if skinned else [], blend="no_alpha_blend", tex=[], alpha_ref=0.0,
             sflags=["use_specular", "do_not_use_vertex_color_as_occlusion"])
    out = (t, src)
    _mtl_cache[key] = out
    return out


if __name__ == "__main__":
    print("clip:", clip_template()["source"])
    for sk in (False, True):
        r, src = material_template(sk)
        print("material (%s): %s | vertex layout %s, shader flags %s" % ("skinned" if sk else "static", src, r["vlayout"], r["sflags"]))
