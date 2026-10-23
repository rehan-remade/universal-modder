"""Recover Blitz3D symbol names hashed by an obfuscating runtime (SCP: Containment Breach 2's uerm.exe).

CB2's linker (the runtime's symbol resolver, found from its "Can't find symbol" string) names every
function, type and builtin import by hashing its lower-case identifier:
    h = 0;  for each byte c (signed):  h = (h + c) * 0x401;  h ^= h >> 6     (int32, arithmetic shift)
    h = h * 9 ^ (h * 9 >> 11);  v = h * 0x8001  (int32)  -> decimal string, '-' when negative
    each char: kept if even and not first, else chr(ord % 26 + 'A')   ('-' -> 'T', '1' -> 'X', ...)
    symbol = "_f" + that string            e.g. Rnd -> _fC2XZZBF6Z (the module calls _builtIn_fC2XZZBF6Z)
The hash can't be inverted, so names come back by hashing candidate identifiers: every word of related
open sources (the game's ancestors) plus the runtime's command signatures.

Usage:
  python -I b3dnames.py obf Rand                     # one name -> symbol
  python -I b3dnames.py recover DISASM_DIR OUT.json --sources SRC_DIR [SRC_DIR ...] [--sigs EXTRA_SIGS.txt]
                                                   [--stub SYMBOL=Name ...]
      DISASM_DIR = B3DDecomp's <exe>_disasm folder. Hashes every identifier in *.bb / *.decls under the
      source dirs, the runtime's BuiltInSymbols.txt, Libs/*.txt and EXTRA_SIGS (one signature per line,
      e.g. "%Rand%from%to=1"), writes {symbol: name} and prints how many builtins / functions / types the
      disassembly now resolves. --stub names a symbol no candidate hashes to (give it a matching zero-arg
      signature in EXTRA_SIGS so the decompiler accepts the call).
"""
import argparse
import glob
import json
import os
import re
import sys


def s32(x):
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x


def obf(name):
    h = 0
    for ch in name.lower().encode("latin-1"):
        c = ch - 256 if ch > 127 else ch
        h = s32((c + h) * 0x401)
        h = s32(h ^ (h >> 6))
    h9 = s32(h * 9)
    h = s32(h9 ^ (h9 >> 11))
    digits = str(s32(h * 0x8001))
    return "_f" + "".join(ch if (ord(ch) & 1) == 0 and i > 0 else chr(ord(ch) % 26 + 0x41)
                          for i, ch in enumerate(digits))


def bare(sig):
    # "%Rand%from%to=1" -> "Rand", "!Foo#x" -> "Foo"
    s = sig.strip().lstrip("!")
    if s and not s[0].isalnum():
        s = s[1:]
    m = re.match(r"[A-Za-z0-9_]+", s)
    return m.group(0) if m else s


def recover(a):
    names = set()
    for d in a.sources:
        for path in glob.glob(os.path.join(d, "**", "*"), recursive=True):
            if path.lower().endswith((".bb", ".decls")):
                names |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", open(path, encoding="latin-1").read()))
    sym_file = os.path.join(a.disasm, "BuiltInSymbols.txt")
    for line in open(sym_file, encoding="latin-1"):
        if line.strip() and not line.startswith("*"):
            names.add(bare(line))
    for path in glob.glob(os.path.join(a.disasm, "Libs", "*.txt")):
        names |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", open(path, encoding="latin-1").read()))
    if a.sigs:
        for line in open(a.sigs, encoding="latin-1"):
            if line.strip():
                names.add(bare(line))
    table = {}
    for n in sorted(names):
        table.setdefault(obf(n), n)
    for stub in a.stub:
        sym, name = stub.split("=", 1)
        table[sym] = name
    json.dump(table, open(a.out, "w"), indent=0)

    text = open(os.path.join(a.disasm, "BuiltIn", "BuiltIn.txt"), encoding="latin-1").read()
    imports = {"_" + x for x in re.findall(r"_builtIn_(f[A-Z0-9]{6,})", text)}
    funcs = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(a.disasm, "Code", "_f*.txt"))]
    types = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(a.disasm, "Type", "_t*.txt"))]
    print("%d candidate names" % len(table))
    print("builtins  %d / %d" % (sum(i in table for i in imports), len(imports)))
    print("functions %d / %d" % (sum(f in table for f in funcs), len(funcs)))
    print("types     %d / %d" % (sum("_f" + t[2:] in table for t in types), len(types)))
    missing = sorted(i for i in imports if i not in table)
    if missing:
        print("unresolved builtins (add their signatures with --sigs, or stub them):", " ".join(missing[:30]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("obf")
    o.add_argument("name")
    r = sub.add_parser("recover")
    r.add_argument("disasm")
    r.add_argument("out")
    r.add_argument("--sources", nargs="+", default=[])
    r.add_argument("--sigs")
    r.add_argument("--stub", nargs="*", default=[])
    a = ap.parse_args()
    if a.cmd == "obf":
        print(obf(a.name))
    else:
        recover(a)


if __name__ == "__main__":
    sys.exit(main())
