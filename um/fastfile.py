"""Call of Duty FastFile (.ff) inspector and script/rawfile extractor.

    um fastfile list zone/english/patch.ff
    um fastfile dump zone/english/patch.ff -o extracted/
    um fastfile dump zone/english/nazi_zombie_factory.ff -o extracted/

Decompresses retail Call of Duty: World at War (T4) and Call of Duty 4 (IW 3.0)
FastFiles and extracts all embedded RawFiles (GSC scripts, CSC client scripts,
menu files, CSV string/sound tables, arena files, and configs). In these titles,
GSC/CSC gameplay scripts are stored as 100% human-readable plain text source.

Read-only: it reads unsigned PC zones (IWffu100) and never writes, repacks or signs
one. Signed zones (IWff0100) are refused. RawFiles are found by scanning the zone
for their serialized layout, not by a full zone parser, so treat a missing file as
"not found by the scan". The dump is the game's own code from your install: keep it
outside any repo and never publish it.
"""
from __future__ import annotations

import os
import re
import struct
import sys
import zlib
from pathlib import Path

from um.common import die


RAWFILE_PATTERN = re.compile(
    rb"\xff\xff\xff\xff(.{4})\xff\xff\xff\xff([a-zA-Z0-9_/\\.-]+(?:\.[a-zA-Z0-9_]+))\x00",
    re.DOTALL,
)


# PC zone versions (the uint32 after the magic), as in OpenAssetTools' IW3 and T4 zone constants
SUPPORTED_VERSIONS = {
    387: "Call of Duty: World at War (Treyarch T4)",
    5: "Call of Duty 4: Modern Warfare (IW 3.0)",
}

MAGIC_UNSIGNED = b"IWffu100"
MAGIC_SIGNED = b"IWff0100"


def decompress_fastfile(path: str | Path) -> tuple[int, bytes]:
    """Decompress a Call of Duty FastFile, returning (version, decompressed_bytes)."""
    p = Path(path)
    if not p.is_file():
        die(f"FastFile not found: {p}")

    with open(p, "rb") as f:
        magic = f.read(8)
        if magic == MAGIC_SIGNED:
            die(f"{p.name} is a signed fastfile (IWff0100). um fastfile reads unsigned PC zones (IWffu100) only "
                "and never touches signatures.")
        if magic != MAGIC_UNSIGNED:
            die(f"unrecognized FastFile header magic: {magic!r} in {p.name}")
        version = struct.unpack("<I", f.read(4))[0]
        compressed_data = f.read()

    if version not in SUPPORTED_VERSIONS:
        print(
            f"WARNING: FastFile version {version} detected in {p.name}.\n"
            f"  This extractor targets World at War PC (v387) and Call of Duty 4 PC (v5).\n"
            f"  Other titles lay out zones and RawFiles differently (MW2 zlib-compresses them,\n"
            f"  Black Ops II compiles GSC to bytecode), so the scan may miss or misread files.",
            file=sys.stderr,
        )

    try:
        decompressed = zlib.decompress(compressed_data)
    except zlib.error as e:
        die(f"failed to decompress {p.name}: {e}")

    return version, decompressed


def extract_rawfiles(data: bytes) -> dict[str, bytes]:
    """Scan decompressed FastFile payload for serialized RawFile assets."""
    rawfiles = {}
    for m in RAWFILE_PATTERN.finditer(data):
        length = struct.unpack("<I", m.group(1))[0]
        name = m.group(2).decode("utf-8", errors="ignore").replace("\\", "/")
        start = m.end()

        # Sanity checks on length and file payload boundary
        if 0 < length <= (len(data) - start):
            payload = data[start : start + length]
            # Verify payload doesn't span out-of-bounds
            if len(payload) == length:
                rawfiles[name] = payload

    return rawfiles


def list_fastfile(path: str | Path):
    """List all embedded RawFiles within a FastFile."""
    version, data = decompress_fastfile(path)
    p = Path(path)
    files = extract_rawfiles(data)

    print(f"FastFile: {p.name} (version {version}, decompressed {len(data):,} bytes)")
    if not files:
        print("  no RawFiles (.gsc, .csc, .menu, .csv, .cfg) found in this FastFile.")
        return

    print(f"  found {len(files)} RawFiles:")
    total_bytes = 0
    for name, payload in sorted(files.items()):
        total_bytes += len(payload)
        print(f"    {len(payload):8,} B  {name}")
    print(f"  total raw content: {total_bytes:,} bytes across {len(files)} files.")


def dump_fastfile(path: str | Path, out_dir: str | Path | None = None):
    """Extract all embedded RawFiles to disk."""
    version, data = decompress_fastfile(path)
    p = Path(path)
    files = extract_rawfiles(data)

    target_dir = Path(out_dir) if out_dir else Path(p.stem + "_extracted")
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"Extracting {len(files)} files from {p.name} (version {version}) -> {target_dir}...")
    extracted_count = 0
    total_bytes = 0

    for name, payload in files.items():
        # Prevent directory traversal attacks
        clean_name = os.path.normpath(name).lstrip("/\\")
        if clean_name.startswith(".."):
            continue

        dest_file = target_dir / clean_name
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_bytes(payload)
        extracted_count += 1
        total_bytes += len(payload)

    print(f"Successfully extracted {extracted_count} files ({total_bytes:,} bytes) into {target_dir}/")


def main(a):
    if a.cmd == "list":
        list_fastfile(a.file)
    elif a.cmd == "dump":
        dump_fastfile(a.file, a.out)


def register(sub):
    import argparse

    p = sub.add_parser(
        "fastfile",
        help="inspect and extract Call of Duty FastFiles (.ff)",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")

    q = cs.add_parser("list", help="list GSCs, CSCs, menus, and raw assets inside a .ff file")
    q.add_argument("file", help="path to .ff FastFile")
    q.set_defaults(func=main)

    q = cs.add_parser("dump", help="extract all embedded scripts and rawfiles from a .ff file to disk")
    q.add_argument("file", help="path to .ff FastFile")
    q.add_argument("-o", "--out", help="destination directory (defaults to <name>_extracted/)")
    q.set_defaults(func=main)
