# The SDK's front door: FBX / PNG in, game-ready Bannerlord packages out, no Modding Kit editor.
# Every writer stages into <SDK_STAGE_DIR>/<stage>/{Assets,RuntimeDataCache[,ModuleData]} (default stage "work"); `install`
# copies a stage into the module with a backup and a manifest, `revert` puts the backup back, and both refuse while the game
# runs. Library code lives in tpac.py (textures, materials, animations, clips, clip caches), sdk_mesh.py (meshes) and
# sdk_skeleton.py (skeletons); validators in validate.py; layouts in their headers.
#   python install.py texture <png> [--name N] [--format bc1|bc3|bc4|bc5|bc7|rgba8] [--usage U] [--no-mips]
#   python install.py material <name> --diffuse T [--normal T] [--specular T] [--shader S] [--blend B] [--flags a,b]
#                              [--static|--skinned] [--template <mtl.tpac>]
#   python install.py retex <installed material> --diffuse T [--normal T] [--specular T]
#   python install.py mesh <fbx> [--name N] [--material A[,B]]    static or skinned (bip01_<name>_<index> bones)
#   python install.py anim <fbx> [...]                             single-take skeleton animations
#   python install.py skeleton <fbx|gltf> [--name N] [--type other|human|horse] [--no-physics] [--axes yup|umodel]
#                                                                  skeleton package (max 64 bones, minimal ragdoll)
#   python install.py clip <name> <anim name> <frames> [fps] [--template <clip.tpac>]
#   python install.py clip-cache "<clip glob>"                     caches for staged (else installed) clips
#   python install.py owner <file_anims_geo.tpac> [...] [--skeleton <guid hex>]   owner skeleton on imported animations (in place)
#   python install.py inspect <file.tpac> [out.png|out.obj]        fields + hash checks (texture, material, mesh, clip)
#   python install.py verify stage [name] [--sets FILE ...]       run validate.py on a stage (default "work")
#   python install.py verify registration <project.mbproj>        every project.mbproj id must be one Native registers
#   python install.py verify skeleton <skeleton_geo.tpac> [...]   skeleton rules (bone count, ik rule, ...)
#   python install.py verify meshes|textures|clips                 rebuild / re-check the module's editor-made assets
#   python install.py rdc-fix <file.rdc> [...]                     re-pack a cache with the engine's rules into the stage
#   python install.py selftest                                     selftest.py: round trips against your own Native files
#   python install.py list [--stage S]                             what a stage holds and where it would go
#   python install.py status                                       game, module, packed or loose, stages, last install
#   python install.py install [--stage S|DIR] [--dry] [--verify] [--owner NAME]   copy a stage into the module (backup + manifest)
#   python install.py revert [manifest] [--owner NAME]             undo one install (default: the newest, only if not yet reverted)
# A packed module (tpac_pack.py): Assets and RuntimeDataCache go into the loose set (AssetsLoose/<sub>, config.ASSETS follows
# it) and install / revert end with `tpac_pack.py repack` (changed groups re-merged, verified, installed). --no-repack (or
# SDK_NO_REPACK=1) skips that for a batch: run `python tpac_pack.py repack` before the next launch, the game shows the old
# packed set until then.
# Common options: --stage S (staging folder name), --force (rewrite a staged file).
# Safety: install and revert refuse while Bannerlord (any process whose image name starts with "Bannerlord" or
# "TaleWorlds.MountAndBlade") runs, and while SDK_LOCK_FILE names another owner.
import glob, hashlib, json, os, shutil, struct, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config, tpac

STAGES = config.SDK_STAGE_DIR
BACKUPS = config.SDK_BACKUP_DIR
MODULE_DATA = config.MODULE_DATA
# stage subfolder -> module folder (ModuleData: XML a generator staged; Module: module root files such as SubModule.xml)
TARGETS = (("Assets", tpac.ASSETS), ("RuntimeDataCache", tpac.RDC_DIR), ("ModuleData", MODULE_DATA),
           ("Module", config.MODULE),
           ("SceneObj", os.path.join(config.MODULE, "SceneObj")))   # SceneObj/<scene id>/<files>

game_running = config.game_running


def stage_dirs(name):
    s = os.path.join(STAGES, name); a, r = os.path.join(s, "Assets"), os.path.join(s, "RuntimeDataCache")
    os.makedirs(a, exist_ok=True); os.makedirs(r, exist_ok=True)
    os.environ["TPAC_STAGE"] = a   # staged packages are visible to texture / animation / material lookups
    return s, a, r


def refuse_if_busy(owner=None):
    """Exit when the game runs or somebody else holds the lock file."""
    if game_running():
        sys.exit("Bannerlord is running (%s): close it first" % ", ".join(config.game_processes()))
    lk = config.lock_refusal(owner)
    if lk: sys.exit(lk)


def file_sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    return h.hexdigest()


def write_manifest(path, man):
    # rewritten before every copy: Windows (indexer / virus scan) briefly locks the just-written manifest, so the
    # replace is retried (installs of 3000+ files failed with WinError 5 after about 3100 files)
    tmp = path + ".tmp"
    with open(tmp, "w") as f: json.dump(man, f, indent=1)
    for k in range(50):
        try: os.replace(tmp, path); return
        except PermissionError:
            if k == 49: raise
            time.sleep(0.1)


def manifests():
    """Every install manifest, oldest first (by seq; old manifests without one by their start time)."""
    out = []
    for p in glob.glob(os.path.join(BACKUPS, "*", "manifest.json")):
        try: m = json.load(open(p))
        except (OSError, ValueError): continue
        m["_path"] = p
        if "started" not in m:   # older manifests: the folder name's timestamp
            try: m["started"] = time.mktime(time.strptime(os.path.basename(os.path.dirname(p))[:15], "%Y%m%d_%H%M%S"))
            except ValueError: m["started"] = os.path.getmtime(p)
        out.append(m)
    return sorted(out, key=lambda m: (m.get("seq", 0), m["started"]))


def _stage_path(stage):
    return stage if os.path.isdir(stage) else os.path.join(STAGES, stage)   # a stage name or any folder with Assets/RuntimeDataCache


def plan_for(s):
    plan = []
    for sub, dest in TARGETS:
        if sub == "SceneObj":      # scene folders: every file under SceneObj/<id>/ keeps its relative path
            for root_, _dirs, files_ in sorted(os.walk(os.path.join(s, sub))):
                for fn in sorted(files_):
                    f = os.path.join(root_, fn); plan.append((f, os.path.join(dest, os.path.relpath(f, os.path.join(s, sub)))))
            continue
        for f in sorted(glob.glob(os.path.join(s, sub, "*"))):
            if os.path.isfile(f): plan.append((f, os.path.join(dest, os.path.basename(f))))
    return plan


def install(stage, dry=False, repack=True, verify=False, owner=None):
    config.require_module()
    s = _stage_path(stage)
    if not os.path.isdir(s): sys.exit("no stage " + s)
    if os.path.exists(os.path.join(s, "packed_manifest.json")): sys.exit("%s is the packed stage: install it with `python tpac_pack.py install`" % s)
    if not dry: refuse_if_busy(owner)
    plan = plan_for(s)
    if not plan: sys.exit("stage %s is empty" % stage)
    import validate
    # a stage that ships a project.mbproj must register only ids Native registers: the engine never merges any other id, and
    # a monster pointing at a set in such a file crashes natively
    mb = os.path.join(s, "ModuleData", "project.mbproj")
    if os.path.exists(mb):
        bad = validate.validate_registration(mb, [os.path.join(s, "ModuleData"), MODULE_DATA])
        if bad:
            for b in bad[:20]: print("  " + b)
            sys.exit("stage %s: %d engine-registration problems, nothing installed" % (stage, len(bad)))
    if verify:
        errs = [e for e in validate.validate(s) if not e.startswith("WARN")]
        if errs:
            for e in errs[:40]: print("  " + e)
            sys.exit("stage %s: %d validation problems, nothing installed" % (stage, len(errs)))
    if dry:
        for src, dst in plan: print("would %s %s -> %s" % ("replace" if os.path.exists(dst) else "add", os.path.basename(src), dst))
        return
    # one folder per install: the name carries the date, a sequence number and the pid, and is claimed atomically
    # (two installs in one second once shared a folder and its manifest)
    os.makedirs(BACKUPS, exist_ok=True)
    seq = max([m.get("seq", 0) for m in manifests()] + [0]) + 1
    while True:
        stamp = "%s_%04d_%d" % (time.strftime("%Y%m%d_%H%M%S"), seq, os.getpid())
        bdir = os.path.join(BACKUPS, stamp)
        try: os.makedirs(bdir); break
        except FileExistsError: seq += 1
    man = {"stage": stage, "time": stamp, "seq": seq, "started": time.time(), "complete": False, "files": []}
    mp = os.path.join(bdir, "manifest.json")
    # the manifest is written before each batch is copied (backups first), so an install that dies half way can still be
    # reverted. Once per file was quadratic: a 52k-file stage had copied 13k after 17 min, rewriting a growing manifest.
    for i in range(0, len(plan), 200):
        if i and game_running():
            sys.exit("Bannerlord started during the install: stopped after %d files (revert or install again)" % len(man["files"]))
        batch, todo = plan[i:i + 200], []
        for src, dst in batch:
            existed = os.path.exists(dst)
            # sha1 (C speed): the pure Python xxh64 took hours on a 3.8 GB mesh stage. A new file needs no hash (revert
            # removes it; the hash only feeds revert's "changed since" note).
            entry = {"dest": dst, "existed": existed, "backup": None, "sha1": file_sha1(src) if existed else None}
            # already identical (a rerun after a stopped install): no backup, no copy, nothing to revert
            if existed and os.path.getsize(dst) == os.path.getsize(src) and file_sha1(dst) == entry["sha1"]:
                continue
            todo.append((src, dst))
            if existed:
                b = os.path.join(bdir, os.path.basename(os.path.dirname(dst)), os.path.basename(dst)); os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copy2(dst, b); entry["backup"] = b
            man["files"].append(entry)
        write_manifest(mp, man)
        for src, dst in todo:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        print("copied %d of %d (%d already identical so far)" % (min(i + 200, len(plan)), len(plan), min(i + 200, len(plan)) - len(man["files"])))
    man["complete"] = True; write_manifest(mp, man)
    print("installed %d files; manifest %s (revert: python install.py revert)" % (len(man["files"]), mp))
    after_loose_change([e["dest"] for e in man["files"]], repack)


def after_loose_change(dests, repack=True):
    """Packed module: a change to the loose set reaches the game only through a repack (tpac_pack.py)."""
    if not tpac.PACKED: return
    loose = [d for d in dests if os.path.normcase(os.path.dirname(d)) in (os.path.normcase(tpac.ASSETS), os.path.normcase(tpac.RDC_DIR))]
    if not loose: return
    if not repack or os.environ.get("SDK_NO_REPACK"):
        print("PACKED MODULE: %d loose files changed, repack skipped: run `python tpac_pack.py repack` before the next launch" % len(loose)); return
    import tpac_pack
    print("packed module: repacking the groups these %d files belong to" % len(loose))
    tpac_pack.repack(lock_check=False, changed=loose)


def loose_dest(dest):
    """A manifest written before the module was packed names Assets/<sub>: while packed that set lives in
    AssetsLoose/<sub> (writing into the old folder would put loose packages back into the game's path)."""
    old = config.ENGINE_LOOSE
    if tpac.PACKED and os.path.normcase(os.path.dirname(dest)) == os.path.normcase(old): return os.path.join(tpac.ASSETS, os.path.basename(dest))
    return dest


def revert(manifest=None, owner=None, repack=True):
    """Undo one install: the given manifest, else the newest install. If the newest is already reverted, nothing
    older is touched (pass that install's manifest path to revert it)."""
    config.require_module()
    if manifest is None:
        ms = manifests()
        if not ms: sys.exit("nothing to revert")
        last = ms[-1]
        if last.get("reverted"):
            sys.exit("the last install (%s, stage %s) was already reverted at %s; to revert an older one pass its manifest path"
                     % (last["time"], last["stage"], last["reverted"]))
        manifest = last["_path"]
    refuse_if_busy(owner)
    man = json.load(open(manifest))
    if man.get("reverted"): sys.exit("%s was already reverted at %s" % (manifest, man["reverted"]))
    print("reverting install %s (stage %s, %d files)" % (man["time"], man["stage"], len(man["files"])))
    for e in reversed(man["files"]):
        e["dest"] = loose_dest(e["dest"])
        # a file a later install changed is still restored, but say so
        if os.path.exists(e["dest"]) and (e.get("sha1") and file_sha1(e["dest"]) != e["sha1"] or
                                          e.get("xxh64") and "%016x" % tpac.xxh64(open(e["dest"], "rb").read()) != e["xxh64"]):
            print("note: changed since this install:", e["dest"])
        if e["backup"]: shutil.copy2(e["backup"], e["dest"]); print("restored", e["dest"])
        elif os.path.exists(e["dest"]):
            os.remove(e["dest"]); print("removed", e["dest"])
            d = os.path.dirname(e["dest"])
            if os.path.basename(os.path.dirname(d)) == "SceneObj" and not os.listdir(d): os.rmdir(d)   # a scene folder this install created
    man["reverted"] = time.strftime("%Y%m%d_%H%M%S"); write_manifest(manifest, man)
    after_loose_change([e["dest"] for e in man["files"]], repack)


def status():
    print("game:   ", config.BANNERLORD_DIR or "NOT FOUND (set BANNERLORD_DIR)")
    print("module: ", config.BANNERLORD_MODULE_DIR or "not set (BANNERLORD_MODULE_DIR)", "(exists)" if os.path.isdir(config.MODULE) and config.BANNERLORD_MODULE_DIR else "")
    print("assets: ", tpac.ASSETS, "(loose set of a PACKED module)" if tpac.PACKED else "")
    n = len(glob.glob(os.path.join(tpac.ASSETS, "*.tpac"))) if os.path.isdir(tpac.ASSETS) else 0
    print("loose packages:", n, "| caches:", len(glob.glob(os.path.join(tpac.RDC_DIR, "*.rdc"))) if os.path.isdir(tpac.RDC_DIR) else 0)
    print("game running:", ", ".join(config.game_processes()) or "no", "| lock:", config.lock_refusal() or "free")
    if os.path.isdir(STAGES):
        for d in sorted(os.listdir(STAGES)):
            if d.startswith("_"): continue
            s = os.path.join(STAGES, d)
            print("stage %-16s %s" % (d, ", ".join("%s %d" % (sub, len(os.listdir(os.path.join(s, sub)))) for sub, _ in TARGETS if os.path.isdir(os.path.join(s, sub)))))
    ms = manifests()
    if ms:
        m = ms[-1]
        print("last install: %s stage %s, %d files, %s%s" % (m["time"], m["stage"], len(m["files"]), "complete" if m.get("complete") else "INCOMPLETE (revert it)",
                                                            ", reverted " + m["reverted"] if m.get("reverted") else ""))
    else:
        print("no installs yet")


def inspect(path, out=None):
    b = open(path, "rb").read(0x34)
    ty = b[0x24:0x34]
    sib = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))), "RuntimeDataCache")   # a stage's caches sit next to its Assets
    rdc = ["--rdc", sib] if os.path.isdir(sib) else []
    if ty == tpac.TEX_TYPE:
        tpac.main(["tpac.py", "tex", path] + ([out] if out else []) + rdc)
    elif ty == tpac.MTL_TYPE:
        r = tpac.read_mtl_file(path); print(r["name"]); tpac.show_mtl(r)
    elif ty == tpac.CLIP_TYPE:
        tpac.main(["tpac.py", "optanim", path] + rdc)
    else:
        import sdk_mesh
        res = sdk_mesh.walk(open(path, "rb").read())
        for r in res: print("%s %-36s %s flag %d, data %s" % (r["type"].hex()[:8], r["name"], r["guid"].hex(), r["flag"], [e["type"].hex()[:8] for e in r["ents"]]))
        if any(r["type"] == sdk_mesh.META_TYPE for r in res):
            for name, E, tris, S in sdk_mesh.read_mesh(path):
                print("  submesh %-28s positions %d vertices %d triangles %d weights %d stream %s" % (name, len(E["P"]), len(E["V"]), len(E["F"]), len(E["W"]), "yes" if S else "MISSING"))
            if out: sdk_mesh.to_obj(path, out); print("wrote", out)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help"):
        print(open(__file__, encoding="utf-8").read().split("\nimport glob")[0]); return 0 if a else 2
    cmd = a[0]; opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    stage = opt("--stage", "work"); force = "--force" in a
    if cmd == "install": return install(stage, "--dry" in a, "--no-repack" not in a, "--verify" in a, opt("--owner"))
    if cmd == "revert": return revert(a[1] if len(a) > 1 and not a[1].startswith("--") else None, opt("--owner"), "--no-repack" not in a)
    if cmd == "status": return status()
    if cmd == "list":
        s = _stage_path(stage)
        for sub, dest in TARGETS:
            for f in sorted(glob.glob(os.path.join(s, sub, "*"))):
                d = os.path.join(dest, os.path.basename(f))
                print("%-8s %-60s %s" % ("replace" if os.path.exists(d) else "new", os.path.basename(f), dest))
        return
    if cmd == "inspect": return inspect(a[1], a[2] if len(a) > 2 and not a[2].startswith("--") else None)
    if cmd == "selftest":
        import selftest; return selftest.main(a[1:])
    config.require_game()
    s, A, R = stage_dirs(stage)
    if cmd == "texture":
        out, rp, r = tpac.write_texture(a[1], opt("--name"), opt("--format"), opt("--usage"), "--no-mips" not in a,
                                        opt("--flags").split(",") if opt("--flags") else (), force, A, R)
        print("staged", out, "+", os.path.basename(rp), "(%s, %dx%d, usage %s)" % (r["format"], r["w"], r["h"], r["usage"]))
    elif cmd == "material":
        tex = {k: opt("--" + k) for k in tpac.SLOTS if opt("--" + k)}
        skin = False if "--static" in a else True if "--skinned" in a else None
        out, r, t = tpac.write_material(a[1], opt("--shader", "pbr_shading"), tex, opt("--blend"),
                                        opt("--flags").split(",") if opt("--flags") else None, skin,
                                        float(opt("--alpha-ref")) if opt("--alpha-ref") else None, force, A, opt("--template"))
        print("staged", out, "(template %s)" % t)
    elif cmd == "retex":
        tpac.main(["tpac.py", "retex", a[1]] + [x for k in tpac.SLOTS if opt("--" + k) for x in ("--" + k, opt("--" + k))] + ["--out", A, "--texdir", A])
    elif cmd == "mesh":
        import sdk_mesh
        mats = opt("--material").split(",") if opt("--material") else None
        for f in [x for x in a[1:] if x.lower().endswith(".fbx")]:
            out, rp, info = sdk_mesh.write_mesh(f, A, R, mats, force, name=opt("--name"))
            print("staged", out, "+", os.path.basename(rp))
            for x in info: print("  submesh %-28s material %-24s positions %d vertices %d triangles %d%s" % (x[0], x[1], x[2], x[3], x[4], " skinned" if x[5] else ""))
    elif cmd == "anim":
        for f in [x for x in a[1:] if x.lower().endswith(".fbx")]:
            out, take, nk = tpac.write_anim_package(f, A, force)
            print("staged %s (animation %s, %d keys)" % (out, take, nk))
    elif cmd == "skeleton":
        import sdk_skeleton
        p, g, bones, u = sdk_skeleton.skeleton_from_file(a[1], opt("--name"), A, force, "none" if "--no-physics" in a else "auto",
                                                         opt("--type", "other"), opt("--axes", "yup"))
        print("staged %s (skeleton guid %s, %d bones, %d bodies, %d joints)" % (p, g.hex(), len(bones),
              sum(b["cap1"][2] > 0 for b in u["bodies"]), len(u["joints"])))
    elif cmd == "clip":
        pos = [x for i, x in enumerate(a[1:]) if not x.startswith("--") and (i == 0 or a[i] not in ("--stage", "--template"))]
        out, dur, ek = tpac.write_clip(pos[0], pos[1], int(pos[2]), float(pos[3]) if len(pos) > 3 else 30.0, out_dir=A, template=opt("--template"))
        print("staged %s  duration %.3f s  keys 0..%d" % (out, dur, ek))
    elif cmd == "rdc-fix":
        import tw_formats
        for f in [x for x in a[1:] if x.lower().endswith(".rdc")]:
            es = tpac.read_rdc(f)
            ents = [(e["owner"], e["id"], e["type"], tpac.lz4_decompress(e["blob"], e["raw"]) if e["stored"] < e["raw"] else e["blob"],
                     [e["h1"], e["h2"]], e["stored"] < e["raw"]) for e in es]
            out = os.path.join(R, os.path.basename(f)); open(out, "wb").write(tw_formats.pack_rdc_exact(ents))
            print("staged %s (%d entries, sorted, type versions)" % (out, len(es)))
    elif cmd == "clip-cache":
        clips = A if glob.glob(os.path.join(A, a[1] + "_anm.tpac")) else tpac.ASSETS
        tpac.main(["tpac.py", "clip-cache", a[1], "--clips", clips, "--rdc", R])
    elif cmd == "owner":
        sk = bytes.fromhex(opt("--skeleton")) if opt("--skeleton") else tpac.HUMAN_SKELETON
        for p in a[1:]:
            if p.endswith(".tpac"): print(os.path.basename(p), "owners set:", tpac.set_owner(p, sk))
    elif cmd == "verify":
        what = a[1] if len(a) > 1 else "stage"
        if what == "stage":
            import validate
            sets = [a[i + 1] for i in range(len(a) - 1) if a[i] == "--sets"]
            name = a[2] if len(a) > 2 and not a[2].startswith("--") else stage
            errs = validate.validate(name, sets)
            for e in errs[:80]: print("  " + e)
            if [e for e in errs if not e.startswith("WARN")]: sys.exit(1)
        elif what in ("registration", "skeleton"):
            import validate; sys.exit(validate.main([what] + a[2:]))
        elif what == "meshes":
            import sdk_mesh
            tmp = os.path.join(STAGES, "_verify"); os.makedirs(tmp, exist_ok=True)
            sys.argv = ["sdk_mesh.py", "verify", "--tmp", tmp] + a[2:]
            import runpy; runpy.run_path(os.path.join(HERE, "sdk_mesh.py"), run_name="__main__")
        elif what == "clips":
            n = 0
            for f in sorted(glob.glob(os.path.join(tpac.ASSETS, "*_anm.tpac"))):
                pk = open(f, "rb").read(0x24); rp = tpac.rdc_path(pk[8:24])
                if not os.path.exists(rp): continue
                E = tpac.read_rdc(rp)[0]; d = tpac.lz4_decompress(E["blob"], E["raw"])
                ok = tpac.pack_optanim(tpac.parse_optanim(d)) == d; n += 1
                if not ok: print("re-pack differs:", os.path.basename(f))
            print("%d clip caches re-packed" % n)
        elif what == "textures":
            ok = bad = 0
            for f in sorted(glob.glob(os.path.join(tpac.ASSETS, "*_tex.tpac"))):
                b = open(f, "rb").read()
                if struct.unpack_from("<I", b, 0x18)[0] == 0: continue
                try: r, pix = tpac.tex_pixels(f)
                except Exception as ex: print("ERROR", os.path.basename(f), ex); bad += 1; continue
                good = r["hash_ok"] and all(e["hash_ok"] for e in r["entries"]) and r.get("rdc_h1_ok", True) and r.get("rdc_h2_ok", True) \
                    and len(pix) == sum(tpac.mip_bytes(max(1, r["w"] >> k), max(1, r["h"] >> k), r["format"]) for k in range(r["mips"]))
                ok += good; bad += not good
                if not good: print("check failed:", os.path.basename(f))
            print("%d textures consistent, %d not" % (ok, bad))
        else:
            sys.exit("verify stage|registration|skeleton|meshes|textures|clips")
    else:
        sys.exit("unknown command %s (python install.py --help)" % cmd)


if __name__ == "__main__":
    sys.exit(main())
