"""Rebuild a stored Garrison object (OfflineGarrison/<id>.agb) from a request decoded in OfflineMode.log.

Usage: python log_to_object.py <OfflineMode.log> <object id> <out dir> [type]
Takes the last 'POST objects/<type>' request in the log, re-encodes its JSON-like text as x-ag-binary the way
the stand-in stores objects (every integer int64, every float f64) and writes {id,type,owner_id,created_at,updated_at,data}.
"""
import json, re, struct, sys, time, os

OFFLINE_ID = "0ff11e000000000000000001"

def sized(base, n):
    if n <= 0xFF: return bytes([base, n])
    if n <= 0xFFFF: return bytes([base + 1]) + struct.pack(">H", n)
    return bytes([base + 2]) + struct.pack(">I", n)

def enc(v):
    if isinstance(v, bool): return b"\x02" if v else b"\x03"
    if isinstance(v, int): return b"\x16" + struct.pack(">q", v)
    if isinstance(v, float): return b"\x21" + struct.pack(">d", v)
    if isinstance(v, str):
        if re.fullmatch(r"@\d+", v): return b"\x40" + struct.pack(">I", int(v[1:]))
        # the log prints raw string bytes through the ANSI code page (cp1252), so map back to the original bytes
        try: b = v.encode("cp1252")
        except UnicodeEncodeError: b = v.encode("utf-8")
        return sized(0x30, len(b)) + b
    if isinstance(v, list): return sized(0x50, len(v)) + b"".join(enc(x) for x in v)
    if isinstance(v, dict): return sized(0x60, len(v)) + b"".join(enc(k) + enc(x) for k, x in v.items())
    raise ValueError(f"cannot encode {type(v)}")

def main():
    log, oid, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    otype = sys.argv[4] if len(sys.argv) > 4 else "user-garrison"
    lines = open(log, encoding="utf-8-sig", errors="replace").read().splitlines()
    body = None
    for i, ln in enumerate(lines):
        if re.search(rf" POST objects/{re.escape(otype)}\s", ln):
            m = re.search(r"request \(\d+ bytes\): (.*)$", lines[i + 1]) if i + 1 < len(lines) else None
            if m: body = m.group(1)
    if body is None: sys.exit("no POST objects/%s request found" % otype)
    # dates are logged as @123 (bare) - quote them so json can parse; '<n bytes>' blobs can't be recovered
    if re.search(r"<\d+ bytes>|<type 0x", body): sys.exit("request contains binary blobs or unknown types; cannot rebuild")
    body = re.sub(r'(?<=[:\[,])@(\d+)', r'"@\1"', body)
    req = json.loads(body, object_pairs_hook=dict)
    now = int(time.time())
    obj = {"id": oid, "type": otype, "owner_id": OFFLINE_ID, "created_at": f"@{now}", "updated_at": f"@{now}", "data": req["data"]}
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, oid + ".agb")
    open(path, "wb").write(enc(obj))
    print(f"wrote {path} ({os.path.getsize(path)} bytes); data keys: {list(req['data'].keys())}")

main()
