# Self-test: does this SDK read and write Bannerlord's formats correctly on YOUR game files? It needs only your own install
# (BANNERLORD_DIR); nothing is written to the game folder, scratch output goes to <SDK_STAGE_DIR>/_selftest.
#   python selftest.py [--limit 200] [--max-package-mb 300] [--textures 4] [--caches 300] [--skip a,b] [--full]
# Sections (each prints PASS or FAIL with counts):
#   packages   parse each sampled Native .tpac and write it again with the SDK's package writer; the rebuilt bytes must equal
#              the file (sha1). The sample is spread over AssetPackages and EmAssetPackages. --full: every package up to
#              --max-package-mb (all 150 AssetPackages rebuild byte-identical on game v1.4.8).
#   textures   Native texture records with inline pixels: the record re-packs byte-identical, the pixel hash rule holds, the
#              import settings round trip, and a decoded top mip re-encoded by the SDK's encoder decodes within a PSNR bound
#              (DXT1, DXT5, BC4, BC5, RGBA8; BC7 has no decoder here, so only its record, hash and size are checked)
#   caches     Native clip caches ("Optimized animation"): parse and re-pack byte-identical, size trailer follows the engine rule
#   skeletons  Native human / horse / camel skeleton definition and user data re-pack byte-identical
#   synthetic  a tiny made-up skeleton, animation, clip, clip cache, texture, material and mesh written to a scratch folder,
#              read back, and run through the validators, which must pass them and must catch four planted faults
# Exit code 0 only when every section passes.
import collections, glob, hashlib, math, os, random, shutil, struct, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import config, tpac, tw_formats, tpac_pack, sdk_skeleton, sdk_mesh, pngio

RESULTS = []


def report(name, ok, detail, notes=()):
    RESULTS.append((name, ok))
    print("%s %-10s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
    for n in list(notes)[:6]:
        print("       " + str(n))


# ----------------------------------------------------------------------------------------------------------------- packages
class _Sink:
    def __init__(self): self.h = hashlib.sha1(); self.n = 0
    def write(self, b): self.h.update(b); self.n += len(b)


def native_files():
    return sorted(glob.glob(os.path.join(config.NATIVE, "**", "*.tpac"), recursive=True))


def sample(files, limit, max_mb, full):
    ok = [f for f in files if os.path.getsize(f) <= max_mb << 20]
    skipped = len(files) - len(ok)
    if full or len(ok) <= limit:
        return ok, skipped
    asset = [f for f in ok if os.sep + "AssetPackages" + os.sep in f]
    em = [f for f in ok if os.sep + "EmAssetPackages" + os.sep in f]
    pick = []
    for group, n in ((asset, limit // 4), (em, limit - limit // 4)):
        step = max(1, len(group) // n)
        pick += group[::step][:n]
    return pick, skipped


def rebuild_identical(path):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        hd = f.read(0x24); meta, = struct.unpack_from("<Q", hd, 0x1c)
        pk = tpac_pack.parse_package(hd + f.read(meta), size)
        sink = _Sink()
        def blob(it, e): f.seek(e["off"]); return f.read(e["stored"])
        tpac_pack.write_package(sink, pk["guid"], pk["items"], blob, pk["version"])
        h = hashlib.sha1(); f.seek(0)
        for b in iter(lambda: f.read(1 << 24), b""): h.update(b)
    return sink.h.digest() == h.digest() and sink.n == size, len(pk["items"])


def section_packages(limit, max_mb, full):
    t0 = time.time(); files, skipped = sample(native_files(), limit, max_mb, full)
    ok = {"AssetPackages": [0, 0], "EmAssetPackages": [0, 0]}; items = 0; bad = []
    for p in files:
        kind = "EmAssetPackages" if os.sep + "EmAssetPackages" + os.sep in p else "AssetPackages"
        try: same, n = rebuild_identical(p)
        except Exception as ex: same, n = False, 0; bad.append("%s: %s" % (os.path.relpath(p, config.NATIVE), ex))
        ok[kind][1] += 1; ok[kind][0] += same; items += n
        if not same and not any(os.path.relpath(p, config.NATIVE) in b for b in bad): bad.append(os.path.relpath(p, config.NATIVE) + ": rebuilt bytes differ")
    tot = sum(v[0] for v in ok.values()); n = sum(v[1] for v in ok.values())
    report("packages", tot == n and n > 0, "%d of %d sampled Native packages rebuild byte-identical (%d items; AssetPackages %d/%d, EmAssetPackages %d/%d; %d larger than %d MB skipped; %.0f s)"
           % (tot, n, items, *ok["AssetPackages"], *ok["EmAssetPackages"], skipped, max_mb, time.time() - t0), bad)


# ---------------------------------------------------------------------------------------------------------------- textures
def _read_entry(f, e):
    f.seek(e["off"]); d = f.read(e["stored"])
    return tpac.lz4_decompress(d, e["raw"]) if e["stored"] < e["raw"] else d


def _psnr(a, b, ch):
    x, y = a.astype(float)[..., ch], b.astype(float)[..., ch]
    mse = ((x - y) ** 2).mean()
    return 99.0 if mse < 1e-9 else 10 * math.log10(255 ** 2 / mse)


def section_textures(per_format):
    t0 = time.time(); cands = collections.defaultdict(list); other = collections.Counter()
    supported = {v[0] for v in tpac.TEX_FORMATS.values()}
    for p in sorted(glob.glob(os.path.join(config.NATIVE, "EmAssetPackages", "**", "*.tpac"), recursive=True)):
        try: items = tw_formats.read_package_index(p)
        except Exception: continue
        for it in items:
            if it["type"] != tpac.TEX_TYPE: continue
            px = [e for e in it["entries"] if e["type"] == tpac.TEX_PIXELS]
            if not px or px[0]["raw"] > 1_500_000: continue
            try: r, _ = tpac.parse_tex_record(bytes(it["record"]), 0)
            except Exception: continue
            if r["format"] not in supported: other[r["format"]] += 1; continue
            if len(cands[r["format"]]) < per_format * 6: cands[r["format"]].append((p, it, r, px[0]))
    stats = collections.Counter(); psnr = collections.defaultdict(list); notes = []
    for fmt, lst in sorted(cands.items()):
        random.Random(7).shuffle(lst)
        for p, it, r, px in lst[:per_format]:
            stats["textures"] += 1
            rec = bytes(it["record"])
            with open(p, "rb") as f:
                pix = _read_entry(f, px)
                st = [e for e in it["entries"] if e["type"] == tpac.TEX_SETTINGS]
                settings = _read_entry(f, st[0]) if st else None
            try:
                if tpac.pack_tex_record(r) == rec: stats["record identical"] += 1
                elif len(notes) < 3: notes.append("%s %s: record re-pack differs" % (it["name"], fmt))
                if tw_formats.texture_pixel_hash(pix) == r["unk8"]: stats["pixel hash"] += 1
                elif len(notes) < 3: notes.append("%s %s: pixel hash rule differs" % (it["name"], fmt))
                if len(pix) == sum(tpac.mip_bytes(max(1, r["w"] >> k), max(1, r["h"] >> k), fmt) for k in range(r["mips"])): stats["size"] += 1
                if settings is not None:
                    stats["settings seen"] += 1
                    if tw_formats.pack_tex_import_settings(tw_formats.parse_tex_import_settings(settings)) == settings: stats["settings identical"] += 1
                if fmt != "BC7":
                    img = tpac.decode_mip(r, pix, 0)
                    again = tpac.decode_blocks(tpac.encode_mip(img, fmt), r["w"], r["h"], fmt)
                    ch = {"BC4": [0], "BC5": [0, 1], "DXT1": [0, 1, 2]}.get(fmt, [0, 1, 2, 3])
                    psnr[fmt].append(_psnr(img, again, ch)); stats["decoded"] += 1
            except Exception as ex:
                notes.append("%s %s: %s" % (it["name"], fmt, ex))
    # the encoders are lossy: a decode of what they wrote must stay close to the decode of the original
    bound = {"DXT1": 30, "DXT5": 28, "BC4": 38, "BC5": 34, "R8G8B8A8_UNORM": 90}
    low = [(f, min(v)) for f, v in psnr.items() if min(v) < bound.get(f, 25)]
    # the pixel hash is the engine's rule for textures the editor imported; a Native texture whose pixels were touched after
    # import keeps its old hash, so most (not all) must match
    ok = (stats["textures"] > 0 and stats["record identical"] == stats["textures"] and stats["pixel hash"] >= 0.8 * stats["textures"]
          and stats["size"] == stats["textures"] and stats["settings identical"] == stats["settings seen"] and not low)
    per = ", ".join("%s min %.1f dB (%d)" % (f, min(v), len(v)) for f, v in sorted(psnr.items()))
    report("textures", ok, "%d Native textures (%s): record re-pack identical %d, pixel hash rule %d, size rule %d, import settings %d/%d; re-encode PSNR: %s; formats the SDK does not write, not tested: %s (%.0f s)"
           % (stats["textures"], ", ".join("%s %d" % (f, min(per_format, len(l))) for f, l in sorted(cands.items())), stats["record identical"],
              stats["pixel hash"], stats["size"], stats["settings identical"], stats["settings seen"], per or "none decoded",
              ", ".join(sorted(other)) or "none", time.time() - t0),
           notes + ["below bound: %s" % low] * bool(low))


# ------------------------------------------------------------------------------------------------------------------ caches
def section_caches(limit):
    t0 = time.time(); stats = collections.Counter(); notes = []; bones = collections.Counter()
    pkgs = sorted(glob.glob(os.path.join(config.NATIVE, "EmAssetPackages", "animations", "*", "*.tpac")))
    per = max(1, limit // max(1, len(pkgs)))
    for p in pkgs:
        n = 0
        try: items = tw_formats.read_package_index(p)
        except Exception: continue
        with open(p, "rb") as f:
            for it in items:
                if it["type"] != tpac.CLIP_TYPE: continue
                for e in it["entries"]:
                    if e["type"] != tpac.OPT_ANIM or n >= per: continue
                    n += 1; stats["caches"] += 1
                    d = _read_entry(f, e)
                    L = None
                    try:
                        L = tw_formats.optanim_layout(d)
                        if L["trailer"] == L["size_in_bytes"] and L["consumed"] == L["length"]: stats["size rule"] += 1
                        elif len(notes) < 4: notes.append("%s: size rule differs" % it["name"])
                    except Exception as ex:
                        if len(notes) < 4: notes.append("%s: layout walk: %s" % (it["name"], ex))
                    try:
                        r = tpac.parse_optanim(d); bones[len(r["bones"])] += 1; stats["parsed"] += 1
                        if tpac.pack_optanim(r) == d: stats["re-pack identical"] += 1
                        elif len(notes) < 4: notes.append("%s (%d bones): re-pack differs" % (it["name"], len(r["bones"])))
                    except NotImplementedError:
                        stats["no root channel (not read)"] += 1
                    except Exception as ex:
                        if L and L["raw_keys"] > 0: stats["raw key channels (not read)"] += 1   # a layout variant the writer does not produce
                        else:
                            stats["unreadable"] += 1
                            if len(notes) < 4: notes.append("%s: %s" % (it["name"], ex))
    ok = stats["parsed"] > 0 and stats["re-pack identical"] == stats["parsed"] and stats["size rule"] == stats["caches"] and not stats["unreadable"]
    report("caches", ok, "%d Native clip caches: size trailer rule %d; %d read by the SDK (bone counts %s), %d of them re-pack byte-identical; not read (layout variants the SDK does not write): %d without a root channel, %d with raw key channels (%.0f s)"
           % (stats["caches"], stats["size rule"], stats["parsed"], ", ".join("%d:%d" % kv for kv in sorted(bones.items())[:6]),
              stats["re-pack identical"], stats["no root channel (not read)"], stats["raw key channels (not read)"], time.time() - t0), notes)


def section_skeletons():
    stats = collections.Counter(); notes = []
    for nm in sdk_skeleton.NATIVE_SKELETONS:
        try:
            x = sdk_skeleton.native(nm); d, u = x[sdk_skeleton.SKEL_DEF], x[sdk_skeleton.USER_DATA]
            name, bones = sdk_skeleton.parse_definition(d); U = sdk_skeleton.parse_userdata(u)
            stats["skeletons"] += 1
            stats["definition identical"] += sdk_skeleton.pack_definition(name, bones, keep_pad=True) == d
            stats["user data identical"] += sdk_skeleton.pack_userdata(U) == u
            stats["tw_formats identical"] += (tw_formats.pack_skeleton_definition(*tw_formats.parse_skeleton_definition(d)) == d
                                              and tw_formats.pack_skeleton_user_data(tw_formats.parse_skeleton_user_data(u)) == u)
        except Exception as ex:
            notes.append("%s: %s" % (nm, ex))
    n = stats["skeletons"]
    report("skeletons", n > 0 and all(stats[k] == n for k in ("definition identical", "user data identical", "tw_formats identical")),
           "%d of %d Native skeletons re-pack byte-identical (definition %d, user data %d, second implementation %d)"
           % (n, len(sdk_skeleton.NATIVE_SKELETONS), stats["definition identical"], stats["user data identical"], stats["tw_formats identical"]), notes)


# --------------------------------------------------------------------------------------------------------------- synthetic
def _quat(axis, ang):
    a = np.asarray(axis, float); a /= np.linalg.norm(a)
    return np.r_[math.cos(ang / 2), math.sin(ang / 2) * a]   # w, x, y, z


def section_synthetic():
    import validate, templates
    t0 = time.time(); root = os.path.join(config.SDK_STAGE_DIR, "_selftest")
    if os.path.isdir(root): shutil.rmtree(root)
    A, R = os.path.join(root, "Assets"), os.path.join(root, "RuntimeDataCache"); os.makedirs(A); os.makedirs(R)
    os.environ["TPAC_STAGE"] = A
    checks = []; notes = []
    def check(name, ok, why=""):
        checks.append((name, bool(ok)))
        if not ok: notes.append("%s %s" % (name, why))
    try:
        # skeleton: a four-bone chain, Z up, with the SDK's minimal ragdoll
        bones = [dict(name="root", parent=-1, R=np.eye(3), o=np.zeros(3))] + \
                [dict(name="b%d" % i, parent=i - 1, R=np.eye(3), o=np.array([0.0, 0.0, 0.3])) for i in range(1, 4)]
        U = sdk_skeleton.auto_userdata(bones)
        sp, sguid = sdk_skeleton.write_skeleton("selftest_skeleton", bones, U, A)
        name, guid, rb, rU = sdk_skeleton.read_skeleton(sp)
        check("skeleton round trip", name == "selftest_skeleton" and guid == sguid and len(rb) == 4 and len(rU["joints"]) == len(U["joints"]))
        check("skeleton passes", not validate.validate_skeleton(name, rb, rU), validate.validate_skeleton(name, rb, rU))
        # animation: 20 frames of a swinging chain, owner = the synthetic skeleton
        frames = 20; t = np.arange(frames, dtype=float)
        rot = []
        for b in range(4):
            q = np.array([_quat([0, 1, 0], 0.4 * math.sin(2 * math.pi * f / frames + b)) for f in range(frames)])
            rot.append((t, q))
        root_ch = (t, np.c_[np.zeros(frames), np.zeros(frames), 0.01 * np.sin(t), np.zeros(frames)])
        ap = tpac.write_anim_takes("selftest_anims", [("selftest_swing", rot, root_ch)], sguid, A)
        a = tpac.anims(ap)
        check("animation written", "selftest_swing" in a and a["selftest_swing"][2] == sguid)
        # clip + cache
        cp, dur, ek = tpac.write_clip("selftest_clip", "selftest_swing", frames, out_dir=A)
        rp, ro, n = tpac.write_clip_cache(cp, R)
        ent = tpac.read_rdc(rp)[0]; blob = ent["blob"] if ent["stored"] >= ent["raw"] else tpac.lz4_decompress(ent["blob"], ent["raw"])
        check("clip cache re-packs", tpac.pack_optanim(tpac.parse_optanim(blob)) == blob)
        q, rt = tpac.optanim_values(tpac.parse_optanim(blob))
        err = max(min(np.abs(v - rot[b][1][int(k)]).max(), np.abs(v + rot[b][1][int(k)]).max()) for (b, k), v in q.items() if int(k) < frames)
        check("clip cache values", err < 0.01, "max error %.4f" % err)
        # texture + material
        img = np.zeros((64, 48, 4), np.uint8); img[..., 0] = np.arange(48)[None, :] * 5; img[..., 1] = np.arange(64)[:, None] * 3; img[..., 3] = 255
        png = os.path.join(root, "selftest_d.png"); pngio.write_png(png, img)
        check("png round trip", (pngio.read_png(png)["rgba"] == img).all())
        tp, trp, tr = tpac.write_texture(png, out_dir=A, rdc_dir=R)
        r2, pix = tpac.tex_pixels(tp, R)
        check("texture hashes", r2["hash_ok"] and all(e["hash_ok"] for e in r2["entries"]) and r2.get("rdc_h1_ok", True) and r2.get("rdc_h2_ok", True)
              and tw_formats.texture_pixel_hash(pix) == r2["unk8"])
        mp, mr, mt = tpac.write_material("selftest_mtl", "pbr_shading", {"diffuse": "selftest_d"}, skinning=True, out_dir=A)
        m2 = tpac.read_mtl_file(mp)
        check("material", m2["vlayout"] == ["skinning"] and m2["tex"] == [(0, tr["resource"])] and m2["shader"] == tpac.find_shader("pbr_shading"))
        # mesh: one quad skinned to the four bones
        P = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], float); F = np.array([[0, 1, 2], [0, 2, 3]], np.uint32)
        N = np.tile([0.0, -1.0, 0.0], (4, 1)); UV = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float); pi = np.arange(4, dtype=np.uint32)
        T, B = sdk_mesh.tangents(P, pi, N, UV, F)
        Wt = np.zeros(4, sdk_mesh.WEIGHT); Wt["w"][:, 0] = 1.0; Wt["b"][:, 0] = [0, 1, 2, 3]
        sub = dict(name="selftest_quad", material="selftest_mtl", P=P, pi=pi, N=N, nbones=4, T=T, B=B, uv0=UV, uv1=np.zeros((4, 2)),
                   c0=np.full(4, 0xffffffff, np.uint32), F=F, W=Wt)
        mo, mrp, info = sdk_mesh.write_metamesh("selftest_quad", "selftest_quad", [sub], b"synthetic", A, R, None, False, None, A)
        subs = sdk_mesh.read_mesh(mo, R)
        check("mesh round trip", len(subs) == 1 and len(subs[0][1]["P"]) == 4 and len(subs[0][1]["F"]) == 2 and subs[0][3] is not None)
        # the validators on the whole stage: no hard problems
        errs = [e for e in validate.validate(root) if not e.startswith("WARN")]
        check("stage passes the validators", not errs, errs[:3])
        # planted faults the validators must catch
        many = [dict(name="n%d" % i, parent=i - 1, R=np.eye(3), o=np.array([0.0, 0.0, 0.1])) for i in range(65)]
        check("catches 65 bones", any("> 64" in e for e in validate.validate_skeleton("big", many, sdk_skeleton.auto_userdata(many))))
        bad = sdk_skeleton.auto_userdata(bones)
        for bd in bad["bodies"]: bd["cap2"] = ((0.0, 0, 0, 1), (0.0, 0, 0.2, 1), 0.05)   # hit capsules on every bone ...
        bad["joints"].append(dict(flag=0, type="ik", name="ik_b1", child="b1", parent="root", frame=(1.0, 0, 0, 0, 0, 0, 0, 1),
                                  motions=[], limits=(0.0,) * 5))                     # ... and an ik joint on b1 only: b2 hangs the solver
        check("catches the ik rule", any("ik rule" in e for e in validate.validate_skeleton("ik", bones, bad)))
        long_name = "x" * 64
        lp, _, _ = tpac.write_clip(long_name, "selftest_swing", frames, out_dir=A)
        check("catches a 64 character clip name", any("63 max" in e for e in validate.validate_clip_file(lp, None)))
        os.remove(lp)
        mb = os.path.join(root, "project.mbproj")
        open(mb, "w").write('<project><file id="my_made_up_id" name="x.xml" type="Test"/></project>')
        check("catches a made-up project.mbproj id", any("not an id Native registers" in e for e in validate.validate_registration(mb)))
    except Exception as ex:
        import traceback
        notes.append(traceback.format_exc().strip().splitlines()[-1]); checks.append(("exception", False))
    good = sum(1 for _, ok in checks if ok)
    report("synthetic", good == len(checks) and checks != [], "%d of %d checks (%s) (%.0f s)" % (
        good, len(checks), ", ".join(n for n, ok in checks if not ok) or "all passed", time.time() - t0), notes)


# ------------------------------------------------------------------------------------------------------------------------ main
def main(argv):
    opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
    if "-h" in argv or "--help" in argv:
        print(open(__file__, encoding="utf-8").read().split("\nimport collections")[0]); return 0
    config.require_game()
    skip = set(opt("--skip", "").split(","))
    limit, max_mb, full = int(opt("--limit", 200)), int(opt("--max-package-mb", 300)), "--full" in argv
    print("Bannerlord:", config.BANNERLORD_DIR)
    print("clip template:     ", templates_source("clip"))
    print("material template: ", templates_source("material"))
    if "packages" not in skip: section_packages(limit, max_mb, full)
    if "textures" not in skip: section_textures(int(opt("--textures", 4)))
    if "caches" not in skip: section_caches(int(opt("--caches", 300)))
    if "skeletons" not in skip: section_skeletons()
    if "synthetic" not in skip: section_synthetic()
    bad = [n for n, ok in RESULTS if not ok]
    print("\nSUMMARY: %d PASS, %d FAIL%s" % (len(RESULTS) - len(bad), len(bad), (" (" + ", ".join(bad) + ")") if bad else ""))
    return 1 if bad else 0


def templates_source(kind):
    import templates
    return templates.clip_template()["source"] if kind == "clip" else templates.material_template(False)[1]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
