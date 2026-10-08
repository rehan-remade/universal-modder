# Pack a module's per-asset packages into a few large ones, as Native ships them.
#   python tpac_pack.py scan                      what the loose set holds (packages, items, caches, duplicates)
#   python tpac_pack.py pack [--target-mb 256] [--full]   merge into <SDK_STAGE_DIR>/packed (incremental: only groups whose
#                                                 members changed are rewritten; --full rewrites all)
#   python tpac_pack.py verify [--all]            parse every merged package/cache back and compare every item, data entry,
#                                                 dependency and cache entry byte for byte with the loose originals
#   python tpac_pack.py native-check [--split-mb 40] [names]   rebuild Native AssetPackages from their parsed parts
#                                                 (all 150 rebuild byte-identical on game v1.4.8), and split small ones into
#                                                 one-item packages and merge those back with the pack code
#   python tpac_pack.py status                    module packed or loose, stray loose packages in the module's Assets folder
#   python tpac_pack.py install [--dry]           game closed: first time moves Assets/<sub> to AssetsLoose/<sub>, then copies
#                                                 the stage's packages to Assets/<sub>_packed and caches to RuntimeDataCache
#                                                 (manifest in <SDK_BACKUP_DIR>/<stamp>/packed_manifest.json)
#   python tpac_pack.py unpack [--dry]            undo: remove the packed files, move the loose set back to Assets/<sub>
#   python tpac_pack.py repack                    pack + verify (changed groups) + install: run after any install into the
#                                                 loose set (install.py does it by itself while the module is packed)
#   python tpac_pack.py logcheck [rgl_log ...]    package read time and missing-asset counts from the game's logs
#
# Why (measured once): the game read the 34,269 one-asset packages of a custom module for 4 min 40 s on a cold file cache
# (20-43 s warm, same files), Native's 150 packages in about 1 s. Per package the client opens the .tpac (header +
# metadata) and, for a package in an Assets folder, its RuntimeDataCache/<package guid>.rdc (header + entry table), so
# about 63k file opens at startup. Blobs are read later, on demand, by offset.
#
# Format facts this relies on (client DLL, Win64_Shipping_Client):
# - Package: "TPAC", u32 version 2, package guid, u32 item count, u64 metadata size (bytes after the 0x24 header), then
#   per item: type guid, item guid, u32 flag, name, u64 record size + record, u64 record hash, u32 n + n x 69-byte data
#   entries (u64 absolute file offset, u64 raw, u64 stored, owner guid, data type guid, u64 hash, u32 type version,
#   u8 flag), u32 n + n x 48-byte dependencies (target item guid, two more guids). Blobs follow the metadata. The header
#   has no flag field: the package's "local" byte is zeroed by the reader, not read from the file.
# - Native AssetPackages (150 files, 40,808 items): items sorted by guid bytes, blobs contiguous in item/entry order up
#   to the end of the file. This writer does the same; native-check proves it rebuilds all 150 byte-identically.
# - A package's item list is only read in order; registration sorts ALL items of a folder by name first and resolves
#   guid duplicates there, so which package an item sits in does not change who wins.
# - Dependencies name the target ITEM guid (the loader searches every type's by-guid map), never a package guid.
# - The only per-package key is the cache file name: RuntimeDataCache/<package guid>.rdc (the guid formatted as
#   %08X-%04hX-%04hX-...). Entries are found by (owner item, data id, type) inside that package's cache only. So a
#   merged package gets ONE merged cache holding every entry of its members' caches (keys are item guids, which do
#   not change), sorted by (owner, id, type) as the engine's cache writer keeps them. Loose caches stay where they are:
#   the game opens only the caches of packages it loads.
# - Folder choice: Modules/X/Assets is loaded (with caches) when Assets and AssetSources both exist, else AssetPackages
#   (no caches, data inline). We keep the Assets route: the merged packages sit in Assets/<sub>_packed, the per-asset
#   originals move to AssetsLoose/<sub> (never read by the game) where every SDK tool keeps reading and writing them
#   (config.ASSETS follows the folder).
import glob, hashlib, json, os, shutil, struct, sys, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config, tpac

MODULE = config.MODULE
GAME_ASSETS = config.GAME_ASSETS                        # the folder the game scans (recursively, *.tpac)
ENGINE_LOOSE = config.ENGINE_LOOSE                      # where the per-asset packages sit while the module is loose
LOOSE = config.LOOSE                                    # ... and while it is packed
PACKED_SUB = config.PACKED_SUB
INSTALLED_PACKED = os.path.join(GAME_ASSETS, PACKED_SUB)
RDC = config.RDC_DIR
STAGE = os.path.join(config.SDK_STAGE_DIR, "packed")
STAGE_A = os.path.join(STAGE, "Assets", PACKED_SUB)
STAGE_R = os.path.join(STAGE, "RuntimeDataCache")
MANIFEST = os.path.join(STAGE, "packed_manifest.json")
BACKUPS = config.SDK_BACKUP_DIR
NS = uuid.UUID("6b1f6d1e-2b6a-4f0e-9a51-b12b0a5ce001")   # package guids = uuid5(NS, group name): stable across repacks
KINDS = ("anm", "geo", "tex", "mtl", "other")
PACK_PREFIX = "pack_"                                   # merged package names: pack_<kind>_<nn>

def loose_dir():
    """The per-asset package folder: AssetsLoose/<sub> once packed, else Assets/<sub>."""
    return LOOSE if os.path.isdir(LOOSE) else ENGINE_LOOSE

def is_packed(): return os.path.isdir(LOOSE)

def rdc_name(pkg_guid): return str(uuid.UUID(bytes_le=bytes(pkg_guid))).upper() + ".rdc"

def kind_of(fn):
    for k in KINDS[:-1]:
        if fn.endswith("_" + k + ".tpac"): return k
    return "other"

# ---------------------------------------------------------------- package parse / write
def _s(b, o):
    n = struct.unpack_from("<i", b, o)[0]
    if not 0 <= n < 1 << 16: raise ValueError("string length %d at %d" % (n, o))
    return bytes(b[o + 4:o + 4 + n]), o + 4 + n

def parse_package(b, size=None):
    """Metadata of a package (b = at least header + metadata). Items keep every field as bytes; entries keep their
    offset. Raises on anything the engine reader would not accept."""
    if b[:4] != b"TPAC": raise ValueError("not a package")
    ver, = struct.unpack_from("<I", b, 4)
    if ver >= 3: raise ValueError("version %d" % ver)
    n, = struct.unpack_from("<I", b, 0x18); meta, = struct.unpack_from("<Q", b, 0x1c)
    o = 0x24; items = []
    for _ in range(n):
        it = {"type": bytes(b[o:o + 16]), "guid": bytes(b[o + 16:o + 32])}; o += 32
        it["flag"] = struct.unpack_from("<I", b, o)[0] if ver > 1 else None
        if ver > 1: o += 4
        it["name"], o = _s(b, o)
        L, = struct.unpack_from("<Q", b, o); it["record"] = bytes(b[o:o + 8 + L]); o += 8 + L
        it["hash"] = bytes(b[o:o + 8]); o += 8
        k, = struct.unpack_from("<I", b, o); o += 4; it["entries"] = []
        for _ in range(k):
            off, raw, st = struct.unpack_from("<QQQ", b, o)
            it["entries"].append({"off": off, "raw": raw, "stored": st, "rest": bytes(b[o + 24:o + 69])}); o += 69
        k, = struct.unpack_from("<I", b, o); o += 4
        it["deps"] = [bytes(b[o + 48 * i:o + 48 * i + 48]) for i in range(k)]; o += 48 * k
        items.append(it)
    if o != 0x24 + meta: raise ValueError("metadata ends at %d, header says %d" % (o, 0x24 + meta))
    if size is not None:
        for it in items:
            for e in it["entries"]:
                if e["off"] < 0x24 + meta or e["off"] + e["stored"] > size: raise ValueError("entry outside the file")
    return {"version": ver, "guid": bytes(b[8:24]), "items": items, "meta": meta}

def read_package(path, data=True):
    """parse_package of a file; data=True also reads every entry's stored bytes into e["data"]."""
    with open(path, "rb") as f:
        b = f.read() if data else f.read(0x24)
        if not data:
            meta, = struct.unpack_from("<Q", b, 0x1c); b += f.read(meta)
    p = parse_package(b, os.path.getsize(path))
    if data:
        for it in p["items"]:
            for e in it["entries"]: e["data"] = b[e["off"]:e["off"] + e["stored"]]
    return p

def item_meta_size(it, ver=2):
    return 32 + (4 if ver > 1 else 0) + 4 + len(it["name"]) + len(it["record"]) + 8 + 4 + 69 * len(it["entries"]) + 4 + 48 * len(it["deps"])

def write_package(out, pkg_guid, items, read_blob, ver=2):
    """Write a package to the binary file object `out` (Native layout: items in the given order, blobs contiguous in
    item/entry order). read_blob(item, entry) returns the entry's stored bytes. Returns the number of bytes written."""
    meta = sum(item_meta_size(it, ver) for it in items)
    head = b"TPAC" + struct.pack("<I", ver) + bytes(pkg_guid) + struct.pack("<IQ", len(items), meta)
    md = bytearray(); pos = 0x24 + meta
    for it in items:
        md += it["type"] + it["guid"] + (struct.pack("<I", it["flag"]) if ver > 1 else b"")
        md += struct.pack("<i", len(it["name"])) + it["name"] + it["record"] + it["hash"] + struct.pack("<I", len(it["entries"]))
        for e in it["entries"]:
            md += struct.pack("<QQQ", pos, e["raw"], e["stored"]) + e["rest"]; pos += e["stored"]
        md += struct.pack("<I", len(it["deps"])) + b"".join(it["deps"])
    assert len(md) == meta
    out.write(head); out.write(md); n = 0x24 + meta
    for it in items:
        for e in it["entries"]:
            d = read_blob(it, e)
            if len(d) != e["stored"]: raise ValueError("blob size")
            out.write(d); n += len(d)
    return n

# ---------------------------------------------------------------- RDC parse / write
def parse_rdc(b):
    """[(key 48 bytes, table entry 145 bytes, stored blob)] of a cache file, checked like rdc_load_header."""
    if b[:4] != b"RDC0" or struct.unpack_from("<I", b, 4)[0] != 0: raise ValueError("not an RDC0 v0 file")
    cnt, = struct.unpack_from("<I", b, 8); tl, = struct.unpack_from("<Q", b, 12)
    if tl != 145 * cnt: raise ValueError("table size")
    out = []
    for k in range(cnt):
        o = 0x14 + 145 * k; t = bytes(b[o:o + 145])
        off, raw, st = struct.unpack_from("<QQQ", t, 48)
        if t[140:144] != b"\xfa" * 4: raise ValueError("entry marker")
        if off + st > len(b): raise ValueError("blob outside the file")
        out.append((t[:48], t, bytes(b[off:off + st])))
    return out

def write_rdc(out, entries):
    """entries [(key, 145-byte table entry, stored blob)] -> RDC0 file in key order (engine rule), offsets rewritten."""
    entries = sorted(entries, key=lambda e: e[0])
    pos = 0x14 + 145 * len(entries); table = bytearray()
    for key, t, d in entries:
        table += t[:48] + struct.pack("<Q", pos) + t[56:]; pos += len(d)
    out.write(b"RDC0" + struct.pack("<IIQ", 0, len(entries), 145 * len(entries))); out.write(table)
    for _, _, d in entries: out.write(d)
    return pos

# ---------------------------------------------------------------- the loose set
def loose_files(d=None):
    d = d or loose_dir()
    return sorted(f for f in os.listdir(d) if f.lower().endswith(".tpac"))

def file_sig(path):
    st = os.stat(path); return [st.st_size, st.st_mtime_ns]

def scan(d=None, verbose=True):
    """Index of the loose set: per file package guid, items, cache; duplicates and orphans."""
    d = d or loose_dir(); t0 = time.time()
    files = loose_files(d); rdcs = {f.upper(): f for f in os.listdir(RDC) if f.lower().endswith(".rdc")}
    info = {}; by_item = {}; by_pkg = {}; by_name = {}; bad = []
    for fn in files:
        p = os.path.join(d, fn)
        try: pk = read_package(p, data=False)
        except Exception as ex: bad.append((fn, str(ex))); continue
        rn = rdcs.get(rdc_name(pk["guid"]).upper())   # the file's own spelling
        info[fn] = {"guid": pk["guid"], "items": [(it["type"], it["guid"], it["name"]) for it in pk["items"]],
                    "rdc": rn, "size": os.path.getsize(p)}
        by_pkg.setdefault(pk["guid"], []).append(fn)
        for it in pk["items"]:
            by_item.setdefault(it["guid"], []).append(fn); by_name.setdefault((it["type"], it["name"].lower()), []).append(fn)
    used = {v["rdc"] for v in info.values() if v["rdc"]}
    r = {"files": len(files), "items": sum(len(v["items"]) for v in info.values()), "bad": bad,
         "dup_item_guid": {k.hex(): v for k, v in by_item.items() if len(v) > 1},
         "dup_pkg_guid": {k.hex(): v for k, v in by_pkg.items() if len(v) > 1},
         "dup_name": {"%s %s" % (k[0].hex()[:8], k[1].decode("latin-1")): v for k, v in by_name.items() if len(v) > 1},
         "rdc_used": len(used), "rdc_all": len(rdcs), "info": info, "seconds": time.time() - t0}
    if verbose:
        print("%d packages, %d items, %d unreadable, %d caches used of %d in RuntimeDataCache (%.0f s)"
              % (r["files"], r["items"], len(bad), len(used), len(rdcs), r["seconds"]))
        for k in KINDS:
            fs = [f for f in info if kind_of(f) == k]
            if fs: print("  %-5s %6d packages %8.1f MB, caches %6d %8.1f MB" % (k, len(fs), sum(info[f]["size"] for f in fs) / 1e6,
                         sum(1 for f in fs if info[f]["rdc"]), sum(os.path.getsize(os.path.join(RDC, info[f]["rdc"])) for f in fs if info[f]["rdc"]) / 1e6))
        print("duplicate item guids %d, duplicate package guids %d, duplicate (type, name) %d" % (len(r["dup_item_guid"]), len(r["dup_pkg_guid"]), len(r["dup_name"])))
        for name, v in list(r["dup_item_guid"].items())[:10]: print("  item guid", name, v)
        for name, v in list(r["dup_pkg_guid"].items())[:10]: print("  package guid", name, v)
        for name, v in list(r["dup_name"].items())[:10]: print("  name", name, v)
        for fn, ex in bad[:10]: print("  unreadable", fn, ex)
    return r

# ---------------------------------------------------------------- grouping
def plan_groups(info, target, old=None):
    """Groups per kind, alphabetical runs of about `target` bytes (package + cache). Boundaries of an earlier plan are
    kept (a new file joins the run its name falls into), so a repack after a small install rewrites few groups; a run
    that grew past 2 x target is split again."""
    sz = lambda f: info[f]["size"] + (os.path.getsize(os.path.join(RDC, info[f]["rdc"])) if info[f]["rdc"] else 0)
    groups = []
    for k in KINDS:
        fs = sorted(f for f in info if kind_of(f) == k)
        if not fs: continue
        starts = [s for s in (old or {}).get(k, [])] or None
        runs = []
        if starts:
            starts = sorted(starts); starts[0] = ""
            for f in fs:
                i = max(j for j, s in enumerate(starts) if f >= s)
                while len(runs) <= i: runs.append([])
                runs[i].append(f)
            runs = [r for r in runs if r]
        else:
            runs = [fs]
        final = []
        for r in runs:   # split runs that are too big (first plan: everything)
            if sum(sz(f) for f in r) <= (2 * target if starts else target): final.append(r); continue
            cur = []; acc = 0
            for f in r:
                if cur and acc + sz(f) > target: final.append(cur); cur = []; acc = 0
                cur.append(f); acc += sz(f)
            if cur: final.append(cur)
        for r in final: groups.append((k, r))
    out = []; count = {}
    for k, r in groups:
        i = count.get(k, 0); count[k] = i + 1
        out.append({"name": PACK_PREFIX + "%s_%02d" % (k, i), "kind": k, "members": r})
    return out

def group_sig(g, info, d):
    h = hashlib.sha1()
    for f in g["members"]:
        h.update(f.encode() + json.dumps(file_sig(os.path.join(d, f))).encode())
        if info[f]["rdc"]: h.update(info[f]["rdc"].encode() + json.dumps(file_sig(os.path.join(RDC, info[f]["rdc"]))).encode())
    return h.hexdigest()

# ---------------------------------------------------------------- pack
def pack_group(g, info, d, out_a, out_r):
    """Merge one group: package (items sorted by guid, as Native) + merged cache. Returns stats."""
    gid = uuid.uuid5(NS, g["name"]).bytes
    items = []; rdc_entries = {}; seen_rdc = set(); clash = []
    for f in g["members"]:
        pk = read_package(os.path.join(d, f))
        if pk["version"] != 2: raise ValueError("%s: version %d" % (f, pk["version"]))
        items += pk["items"]
        rn = info[f]["rdc"]
        if rn and rn not in seen_rdc:
            seen_rdc.add(rn)
            for key, t, blob in parse_rdc(open(os.path.join(RDC, rn), "rb").read()):
                if key in rdc_entries:
                    if rdc_entries[key][1][56:] != t[56:] or rdc_entries[key][2] != blob: clash.append((f, key.hex()))
                    continue
                rdc_entries[key] = (key, t, blob)
    if clash: raise ValueError("%s: %d cache keys with different data in two members, e.g. %s" % (g["name"], len(clash), clash[0]))
    items.sort(key=lambda it: it["guid"])
    pa = os.path.join(out_a, g["name"] + ".tpac"); tmp = pa + ".tmp"
    with open(tmp, "wb") as fo: n = write_package(fo, gid, items, lambda it, e: e["data"])
    os.replace(tmp, pa)
    rn = None; rsize = 0
    if rdc_entries:
        rn = rdc_name(gid); pr = os.path.join(out_r, rn); tmp = pr + ".tmp"
        with open(tmp, "wb") as fo: rsize = write_rdc(fo, list(rdc_entries.values()))
        os.replace(tmp, pr)
    return {"guid": str(uuid.UUID(bytes_le=gid)).upper(), "file": g["name"] + ".tpac", "rdc": rn, "size": n, "rdc_size": rsize,
            "items": len(items), "rdc_entries": len(rdc_entries), "caches": len(seen_rdc)}

def load_manifest(path=None):
    try: return json.load(open(path or MANIFEST))
    except (OSError, ValueError): return None

def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f: json.dump(obj, f, indent=1)
    for k in range(50):
        try: os.replace(tmp, path); return
        except PermissionError: time.sleep(0.1)
    os.replace(tmp, path)

def pack(target_mb=256, full=False, force=()):
    """force: loose file names (packages or caches) known to have changed: their groups are rewritten whatever the stat says."""
    d = loose_dir(); t0 = time.time()
    print("loose set:", d)
    sc = scan(d)
    if sc["bad"]: sys.exit("unreadable packages in the loose set, nothing packed")
    info = sc["info"]
    os.makedirs(STAGE_A, exist_ok=True); os.makedirs(STAGE_R, exist_ok=True)
    old = None if full else load_manifest()
    groups = plan_groups(info, target_mb << 20, old and old.get("starts"))
    prev = {g["name"]: g for g in (old or {}).get("groups", [])}
    man = {"made": time.strftime("%Y-%m-%d %H:%M:%S"), "loose": d, "target_mb": target_mb, "groups": [],
           "starts": {}, "scan": {k: sc[k] for k in ("files", "items", "rdc_used", "rdc_all")},
           "dup_item_guid": sc["dup_item_guid"], "dup_pkg_guid": sc["dup_pkg_guid"], "verified": None}
    written = 0
    for g in groups:
        man["starts"].setdefault(g["kind"], []).append(g["members"][0])
        sig = group_sig(g, info, d); p = prev.get(g["name"])
        touched = any(f in force or (info[f]["rdc"] or "").upper() in force for f in g["members"])
        same = not touched and p and p.get("sig") == sig and p.get("members") == [m for m in g["members"]] and os.path.exists(os.path.join(STAGE_A, p["file"])) \
            and (not p.get("rdc") or os.path.exists(os.path.join(STAGE_R, p["rdc"])))
        if same:
            rec = dict(p); rec["rewritten"] = False
        else:
            st = pack_group(g, info, d, STAGE_A, STAGE_R)
            rec = dict(st, name=g["name"], kind=g["kind"], members=g["members"], sig=sig, rewritten=True,
                       member_rdc={f: info[f]["rdc"] for f in g["members"] if info[f]["rdc"]})
            written += 1
            print("  %-18s %5d packages -> %6d items %7.1f MB, cache %6d entries %7.1f MB" % (g["name"], len(g["members"]),
                  st["items"], st["size"] / 1e6, st["rdc_entries"], st["rdc_size"] / 1e6), flush=True)
        man["groups"].append(rec)
    # stale outputs of groups that no longer exist
    keep_a = {g["file"] for g in man["groups"]}; keep_r = {g["rdc"] for g in man["groups"] if g.get("rdc")}
    for f in os.listdir(STAGE_A):
        if f not in keep_a: os.remove(os.path.join(STAGE_A, f)); print("  removed stale", f)
    for f in os.listdir(STAGE_R):
        if f not in keep_r: os.remove(os.path.join(STAGE_R, f)); print("  removed stale", f)
    save_json(MANIFEST, man)
    print("packed %d groups (%d rewritten) from %d packages in %.0f s -> %s" % (len(man["groups"]), written, sc["files"], time.time() - t0, STAGE))
    return man

# ---------------------------------------------------------------- verify
def verify(all_groups=True, quiet=False):
    """Every merged package and cache parsed back; every loose item, data entry (all fields but the offset, plus the
    stored bytes), dependency and cache entry found identical; counts equal; layout rules (guid order, contiguous blobs,
    sorted cache) hold. Records the result in the manifest."""
    man = load_manifest()
    if not man: sys.exit("no packed stage; run pack first")
    d = loose_dir()   # the stage's members by name; the set may have moved to AssetsLoose since (a rename keeps the files)
    tot = {"groups": 0, "packages": 0, "items": 0, "entries": 0, "deps": 0, "rdc_files": 0, "rdc_entries": 0, "bytes": 0}
    problems = []; notes = []; t0 = time.time()
    for g in man["groups"]:
        if not all_groups and not g.get("rewritten"): continue
        pa = os.path.join(STAGE_A, g["file"]); mb = open(pa, "rb").read()
        mp = parse_package(mb, len(mb)); tot["bytes"] += len(mb)
        P = lambda m: problems.append("%s: %s" % (g["name"], m))
        if str(uuid.UUID(bytes_le=mp["guid"])).upper() != g["guid"]: P("package guid")
        gs = [it["guid"] for it in mp["items"]]
        if gs != sorted(gs): P("items not in guid order")
        pos = 0x24 + mp["meta"]
        for it in mp["items"]:
            for e in it["entries"]:
                if e["off"] != pos: P("blobs not contiguous")
                pos = e["off"] + e["stored"]
        if pos != len(mb): P("file does not end after the last blob")
        merged = {}
        for it in mp["items"]: merged.setdefault(it["guid"], []).append(it)
        want = 0; own = {}
        for f in g["members"]:
            lp = read_package(os.path.join(d, f)); tot["packages"] += 1
            own[f] = {it["guid"] for it in lp["items"]}
            for it in lp["items"]:
                want += 1; tot["items"] += 1; tot["entries"] += len(it["entries"]); tot["deps"] += len(it["deps"])
                cands = merged.get(it["guid"], [])
                ok = False
                for m in cands:
                    if all(m[k] == it[k] for k in ("type", "flag", "name", "record", "hash", "deps")) and len(m["entries"]) == len(it["entries"]) \
                            and all(a["raw"] == b["raw"] and a["stored"] == b["stored"] and a["rest"] == b["rest"]
                                    and mb[a["off"]:a["off"] + a["stored"]] == b["data"] for a, b in zip(m["entries"], it["entries"])):
                        ok = True; cands.remove(m); break
                if not ok: P("%s item %s %s differs or is missing" % (f, it["guid"].hex(), it["name"].decode("latin-1")))
        if want != len(mp["items"]): P("item count %d, members hold %d" % (len(mp["items"]), want))
        # cache
        mr = g.get("member_rdc", {})
        if g.get("rdc"):
            rb = open(os.path.join(STAGE_R, g["rdc"]), "rb").read(); ents = parse_rdc(rb); tot["bytes"] += len(rb)
            keys = [k for k, _, _ in ents]
            if keys != sorted(keys): P("cache not sorted")
            if len(set(keys)) != len(keys): P("cache key twice")
            pos = 0x14 + 145 * len(ents)
            for k, t, blob in ents:
                if struct.unpack_from("<Q", t, 48)[0] != pos: P("cache blobs not contiguous")
                pos += len(blob)
            if pos != len(rb): P("cache file size")
            have = {k: (t, blob) for k, t, blob in ents}; n = 0; inherited = set()
            for f, rn in sorted(mr.items(), key=lambda x: x[1]):
                tot["rdc_files"] += 1
                for k, t, blob in parse_rdc(open(os.path.join(RDC, rn), "rb").read()):
                    n += 1; tot["rdc_entries"] += 1
                    if k[:16] not in own.get(f, ()): inherited.add(k)   # already unreachable in the loose cache
                    h = have.get(k)
                    if not h or h[0][:48] != t[:48] or h[0][56:] != t[56:] or h[1] != blob: P("cache %s entry %s differs or is missing" % (rn, k.hex()))
            if n != len(ents) and n < len(ents): P("cache holds %d entries, members %d" % (len(ents), n))
            owners = {it["guid"] for it in mp["items"]}
            foreign = [k for k in keys if k[:16] not in owners]
            if set(foreign) - inherited: P("%d cache entries owned by items outside the package" % len(set(foreign) - inherited))
            for k in sorted(set(foreign) & inherited):
                notes.append("%s: cache entry %s (owner %s) has no item in its loose package either: copied as is, never looked up" % (g["name"], k[32:48].hex()[:8], k[:16].hex()))
        elif mr: P("members have caches but the group has none")
        tot["groups"] += 1
        g["verified"] = None if any(x.startswith(g["name"] + ":") for x in problems) else _group_files_sig(g)
        if not quiet: print("  %-18s ok so far: %d problems" % (g["name"], len(problems)), flush=True)
    for p in notes[:20]: print("NOTE", p)
    for p in problems[:40]: print("PROBLEM", p)
    print("verified %d groups: %d packages, %d items, %d data entries, %d dependencies, %d caches with %d entries, %.2f GB read back; %d problems (%.0f s)"
          % (tot["groups"], tot["packages"], tot["items"], tot["entries"], tot["deps"], tot["rdc_files"], tot["rdc_entries"], tot["bytes"] / 1e9, len(problems), time.time() - t0))
    man["verified"] = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "problems": len(problems), "totals": tot, "all": all_groups, "notes": notes}
    save_json(MANIFEST, man)
    return not problems

# ---------------------------------------------------------------- Native proof
def native_check(names=None, split_mb=40):
    """1. Rebuild each Native AssetPackage from its parsed items with write_package and compare the bytes (sha1 of a
    stream, no temp file). 2. For packages up to split_mb: write every item as its own one-item package (the shape of
    our loose set), then merge those parts with the same merge path as pack (items sorted by guid) under the Native
    package guid, and compare with the original file."""
    root = os.path.join(tpac.NATIVE, "AssetPackages")
    files = sorted(glob.glob(os.path.join(root, "*.tpac")), key=os.path.getsize)
    if names: files = [f for f in files if os.path.splitext(os.path.basename(f))[0] in names]
    ok1 = ok2 = n2 = 0; items = 0; t0 = time.time(); tmp = os.path.join(config.SDK_STAGE_DIR, "_native_check")
    class H:
        def __init__(s): s.h = hashlib.sha1(); s.n = 0
        def write(s, b): s.h.update(b); s.n += len(b)
    for p in files:
        size = os.path.getsize(p)
        with open(p, "rb") as f:
            hd = f.read(0x24); meta, = struct.unpack_from("<Q", hd, 0x1c); pk = parse_package(hd + f.read(meta), size)
            items += len(pk["items"])
            orig = hashlib.sha1(); f.seek(0)
            for blk in iter(lambda: f.read(1 << 24), b""): orig.update(blk)
            def rb(it, e, f=f): f.seek(e["off"]); return f.read(e["stored"])
            h = H(); write_package(h, pk["guid"], pk["items"], rb, pk["version"])
        same = h.h.digest() == orig.digest() and h.n == size; ok1 += same
        line = "%-34s %8.1f MB %6d items rebuild %s" % (os.path.basename(p), size / 1e6, len(pk["items"]), "identical" if same else "DIFFERS")
        if size <= split_mb << 20:
            if os.path.isdir(tmp): shutil.rmtree(tmp)
            os.makedirs(tmp)
            full = open(p, "rb").read(); parts = []
            for i, it in enumerate(pk["items"]):   # one-item packages, fresh package guids, items in reverse file order
                q = os.path.join(tmp, "part_%06d.tpac" % (len(pk["items"]) - i))
                with open(q, "wb") as fo: write_package(fo, uuid.uuid4().bytes, [it], lambda it_, e: full[e["off"]:e["off"] + e["stored"]])
                parts.append(q)
            merged = []
            for q in sorted(parts):   # the pack path: read each part with its blobs, merge, sort by guid
                merged += read_package(q)["items"]
            merged.sort(key=lambda it: it["guid"])
            h2 = H(); write_package(h2, pk["guid"], merged, lambda it, e: e["data"])
            same2 = h2.h.digest() == orig.digest(); ok2 += same2; n2 += 1
            line += ", split into %d parts and merged back %s" % (len(parts), "identical" if same2 else "DIFFERS")
            shutil.rmtree(tmp)
        print(line, flush=True)
    print("Native: %d of %d packages rebuild byte-identical (%d items); %d of %d split + merged back byte-identical (%.0f s)"
          % (ok1, len(files), items, ok2, n2, time.time() - t0))
    return ok1 == len(files) and ok2 == n2

# ---------------------------------------------------------------- install / unpack
game_running = config.game_running
lock_refusal = config.lock_refusal

def status(verbose=True):
    stray = [f for f in os.listdir(ENGINE_LOOSE) if f.lower().endswith(".tpac")] if is_packed() and os.path.isdir(ENGINE_LOOSE) else []
    inst = sorted(os.listdir(INSTALLED_PACKED)) if os.path.isdir(INSTALLED_PACKED) else []
    if verbose:
        print("module:", MODULE)
        print("state: %s" % ("PACKED (loose set in AssetsLoose/%s, game loads Assets/%s)" % (config.MODULE_ASSET_SUB, PACKED_SUB) if is_packed() else "loose (game loads Assets/%s)" % config.MODULE_ASSET_SUB))
        print("loose packages: %d in %s" % (len(loose_files()), loose_dir()))
        print("installed packed packages: %d" % len([f for f in inst if f.endswith(".tpac")]))
        if stray: print("STRAY: %d loose packages in Assets/%s while packed (the game loads them too): %s" % (len(stray), config.MODULE_ASSET_SUB, stray[:5]))
        man = load_manifest()
        if man: print("stage: %d groups, made %s, verified %s" % (len(man["groups"]), man["made"], (man.get("verified") or {}).get("time")))
    return {"packed": is_packed(), "stray": stray, "installed": inst}

def _group_files_sig(g):
    return [file_sig(os.path.join(STAGE_A, g["file"])), file_sig(os.path.join(STAGE_R, g["rdc"])) if g.get("rdc") else None]

def _stage_verified(man):
    """Every group passed verify and its files did not change since."""
    for g in man["groups"]:
        try:
            if not g.get("verified") or g["verified"] != _group_files_sig(g): return False
        except OSError: return False
    return True

def install(dry=False, lock_check=True, owner=None):
    man = load_manifest()
    if not man: sys.exit("no packed stage; run pack and verify first")
    if not _stage_verified(man): sys.exit("a group of the stage is not verified (or changed since): run tpac_pack.py verify first")
    if not dry:
        if game_running(): sys.exit("Bannerlord (game or editor) is running: close it first")
        lk = lock_check and lock_refusal(owner)
        if lk: sys.exit(lk)
    first = not is_packed()
    if first and loose_dir() != ENGINE_LOOSE: sys.exit("unexpected layout")
    # the stage must describe the current loose set (nothing installed since pack)
    now = set(loose_files(LOOSE if not first else ENGINE_LOOSE))
    packed_members = {f for g in man["groups"] for f in g["members"]}
    if now != packed_members: sys.exit("the loose set changed since pack (%d new, %d gone): run tpac_pack.py repack" % (len(now - packed_members), len(packed_members - now)))
    src = ENGINE_LOOSE if first else LOOSE
    info = {f: {"rdc": g.get("member_rdc", {}).get(f)} for g in man["groups"] for f in g["members"]}
    changed = [g["name"] for g in man["groups"] if group_sig(g, info, src) != g["sig"]]
    if changed: sys.exit("loose packages or caches changed since pack (groups %s): run tpac_pack.py repack" % ", ".join(changed[:5]))
    stray = status(False)["stray"]
    if stray: sys.exit("%d loose packages in Assets/%s while packed: move them into %s (or install them with install.py) first" % (len(stray), config.MODULE_ASSET_SUB, LOOSE))
    plan = []
    for g in man["groups"]:
        plan.append((os.path.join(STAGE_A, g["file"]), os.path.join(INSTALLED_PACKED, g["file"])))
        if g.get("rdc"): plan.append((os.path.join(STAGE_R, g["rdc"]), os.path.join(RDC, g["rdc"])))
    keep = {os.path.normcase(dst) for _, dst in plan}
    old_packed = [os.path.join(INSTALLED_PACKED, f) for f in (os.listdir(INSTALLED_PACKED) if os.path.isdir(INSTALLED_PACKED) else [])]
    prev = _last_packed_manifest()
    old_rdc = [os.path.join(RDC, x) for x in (prev or {}).get("rdc_files", [])]
    remove = [p for p in old_packed + old_rdc if os.path.normcase(p) not in keep and os.path.exists(p)]
    todo = [(s, t) for s, t in plan if not (os.path.exists(t) and os.path.getsize(t) == os.path.getsize(s) and _sha1(t) == _sha1(s))]
    if dry:
        if first: print("would move %s -> %s (%d packages)" % (ENGINE_LOOSE, LOOSE, len(now)))
        for s, t in todo: print("would %s %s (%.1f MB)" % ("replace" if os.path.exists(t) else "add", t, os.path.getsize(s) / 1e6))
        for p in remove: print("would remove", p)
        print("dry run: %d files to copy (%.2f GB), %d to remove, %d already current" % (len(todo), sum(os.path.getsize(s) for s, _ in todo) / 1e9, len(remove), len(plan) - len(todo)))
        return
    os.makedirs(BACKUPS, exist_ok=True)
    k = 0
    while True:   # claimed atomically; two installs in one second (install + revert) get different folders
        stamp = "%s_packed_%d_%d" % (time.strftime("%Y%m%d_%H%M%S"), os.getpid(), k); bdir = os.path.join(BACKUPS, stamp)
        try: os.makedirs(bdir); break
        except FileExistsError: k += 1
    mp = os.path.join(bdir, "packed_manifest.json")
    rec = {"kind": "packed", "time": stamp, "started": time.time(), "complete": False, "first": first, "moved": None, "files": [], "removed": [],
           "rdc_files": [g["rdc"] for g in man["groups"] if g.get("rdc")], "groups": len(man["groups"])}
    save_json(mp, rec)
    if first:
        os.makedirs(os.path.dirname(LOOSE), exist_ok=True)
        try: os.rename(ENGINE_LOOSE, LOOSE)   # same volume: a rename, no copy; the game folder never has both sets
        except OSError as ex: sys.exit("could not rename %s (a file in it is open? close Explorer windows / the editor): %s; nothing changed" % (ENGINE_LOOSE, ex))
        rec["moved"] = [ENGINE_LOOSE, LOOSE]; save_json(mp, rec); print("moved", ENGINE_LOOSE, "->", LOOSE)
    os.makedirs(INSTALLED_PACKED, exist_ok=True)
    for s, t in todo:
        existed = os.path.exists(t)
        rec["files"].append({"dest": t, "existed": existed, "sha1": _sha1(s)}); save_json(mp, rec)
        shutil.copy2(s, t); print("%s %s" % ("replaced" if existed else "added", t), flush=True)
    for p in remove:
        os.remove(p); rec["removed"].append(p); print("removed", p)
    rec["complete"] = True; save_json(mp, rec)
    shutil.copy2(MANIFEST, os.path.join(MODULE, PACKED_SUB + ".json"))   # what is installed (the game ignores it)
    print("installed: %d groups, %d files copied, %d removed; manifest %s (undo: python tpac_pack.py unpack)" % (len(man["groups"]), len(todo), len(remove), mp))

def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    return h.hexdigest()

def _last_packed_manifest():
    ms = []
    for p in glob.glob(os.path.join(BACKUPS, "*", "packed_manifest.json")):
        try: m = json.load(open(p)); m["_path"] = p; ms.append(m)
        except (OSError, ValueError): pass
    ms.sort(key=lambda m: m.get("started", 0))
    return ms[-1] if ms else None

def unpack(dry=False, owner=None):
    """Back to the loose layout: remove Assets/<sub>_packed and the merged caches, move AssetsLoose/<sub> back."""
    if not is_packed(): sys.exit("the module is not packed")
    if not dry:
        if game_running(): sys.exit("Bannerlord (game or editor) is running: close it first")
        lk = lock_refusal(owner)
        if lk: sys.exit(lk)
    if os.path.isdir(ENGINE_LOOSE) and os.listdir(ENGINE_LOOSE): sys.exit("Assets/%s is not empty: move its files into %s first" % (config.MODULE_ASSET_SUB, LOOSE))
    rdcs = set()
    for p in glob.glob(os.path.join(BACKUPS, "*", "packed_manifest.json")):
        try: rdcs |= set(json.load(open(p)).get("rdc_files", []))
        except (OSError, ValueError): pass
    try:
        inst = json.load(open(os.path.join(MODULE, PACKED_SUB + ".json")))
        rdcs |= {g["rdc"] for g in inst["groups"] if g.get("rdc")}
    except (OSError, ValueError): pass
    files = [os.path.join(INSTALLED_PACKED, f) for f in (os.listdir(INSTALLED_PACKED) if os.path.isdir(INSTALLED_PACKED) else [])]
    files += [os.path.join(RDC, r) for r in sorted(rdcs) if os.path.exists(os.path.join(RDC, r))]
    if dry:
        for p in files: print("would remove", p)
        print("would move %s -> %s" % (LOOSE, ENGINE_LOOSE)); return
    for p in files: os.remove(p); print("removed", p)
    if os.path.isdir(INSTALLED_PACKED): os.rmdir(INSTALLED_PACKED)
    if os.path.isdir(ENGINE_LOOSE): os.rmdir(ENGINE_LOOSE)
    os.rename(LOOSE, ENGINE_LOOSE); print("moved", LOOSE, "->", ENGINE_LOOSE)
    try: os.rmdir(os.path.dirname(LOOSE))
    except OSError: pass
    try: os.remove(os.path.join(MODULE, PACKED_SUB + ".json"))
    except OSError: pass
    print("unpacked: the game loads Assets/%s again" % config.MODULE_ASSET_SUB)

def repack(full=False, lock_check=True, owner=None, changed=()):
    """After installs into the loose set: pack (changed groups), verify those, install. install.py install / revert call
    it with lock_check=False (their caller owns the game folder at that point, as for any install)."""
    if not lock_check or not lock_refusal(owner):
        if game_running(): sys.exit("Bannerlord (game or editor) is running: close it first (the loose set changed; run tpac_pack.py repack later)")
    else: sys.exit(lock_refusal(owner) + " (the loose set changed; run tpac_pack.py repack later)")
    old = load_manifest()
    force = {os.path.basename(x) for x in changed} | {os.path.basename(x).upper() for x in changed}
    pack(old["target_mb"] if old and not full else 256, full=full, force=force)
    if not verify(all_groups=False, quiet=True): sys.exit("verify failed: nothing installed (the module still has the previous packed set)")
    install(lock_check=lock_check, owner=owner)

# ---------------------------------------------------------------- rgl log check
LOGS = r"C:\ProgramData\Mount and Blade II Bannerlord\logs"
LOG_COUNTS = ["Unable to find data", "Cannot read render buffers", "Unable to find item to add dependency", "already added from package",
              "Unable to open file", "Unable to read file", "is already registered", "Unknown guid for asset package", "Overriding item",
              "Unable to find", "Missing shader", "Out of date RDC"]

def _t(line):
    import re
    m = re.match(r"\[(\d+):(\d+):(\d+\.\d+)\]", line)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None

def log_stats(path):
    L = open(path, encoding="utf-8", errors="replace").read().splitlines()
    r = {"log": os.path.basename(path)}
    for i, l in enumerate(L):
        if "Loading packages $BASE/Modules/" in l:
            mod = l.split("$BASE/Modules/")[1].split("/")[0]; t0 = _t(l)
            t1 = next((_t(x) for x in L[i + 1:i + 50000] if _t(x) is not None and "Overriding item" not in x and "Unable to find item" not in x), None)
            reg = next((_t(x) for x in L[i + 1:] if "Registering items" in x), None)
            r.setdefault("read", {})[mod] = (reg or t1 or t0) - t0
        if "Loading done" in l and "done" not in r: r["done"] = _t(l)
    first = next((_t(l) for l in L if _t(l) is not None), 0)
    if "done" in r: r["done"] -= first
    r["counts"] = {p: sum(1 for l in L if p in l) for p in LOG_COUNTS}
    return r

def logcheck(paths):
    """Package read time of the module (Loading packages ... to Registering items) and missing-asset line counts, per log."""
    if not paths:
        paths = sorted(glob.glob(os.path.join(LOGS, "rgl_log_*.txt")), key=os.path.getmtime)[-2:]
    rs = [log_stats(p) for p in paths]
    print("%-38s" % "" + "".join("%22s" % r["log"] for r in rs))
    for mod in ("Native", "SandBox", config.MODULE_NAME):
        print("%-38s" % ("package read+register %s (s)" % mod) + "".join("%22s" % ("%.1f" % r.get("read", {}).get(mod) if r.get("read", {}).get(mod) is not None else "-") for r in rs))
    print("%-38s" % "start to 'Loading done' (s)" + "".join("%22s" % ("%.1f" % r["done"] if "done" in r else "-") for r in rs))
    for p in LOG_COUNTS:
        print("%-38s" % p[:38] + "".join("%22d" % r["counts"][p] for r in rs))

def main():
    a = sys.argv[1:]
    if not a: print(open(__file__).read().split("\nimport ")[0]); return
    cmd = a[0]; opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if cmd in ("scan", "pack", "verify", "status", "install", "unpack", "repack"): config.require_module()
    elif cmd == "native-check": config.require_game()
    if cmd == "scan": scan()
    elif cmd == "pack": pack(int(opt("--target-mb", 256)), "--full" in a)
    elif cmd == "verify": sys.exit(0 if verify(True) else 1)
    elif cmd == "native-check": sys.exit(0 if native_check([x for x in a[1:] if not x.startswith("--") and x != opt("--split-mb")], int(opt("--split-mb", 40))) else 1)
    elif cmd == "status": status()
    elif cmd == "install": install("--dry" in a, owner=opt("--owner"))
    elif cmd == "unpack": unpack("--dry" in a, owner=opt("--owner"))
    elif cmd == "repack": repack("--full" in a, owner=opt("--owner"))
    elif cmd == "logcheck": logcheck(a[1:])
    else: sys.exit("unknown command " + cmd)

if __name__ == "__main__":
    main()
