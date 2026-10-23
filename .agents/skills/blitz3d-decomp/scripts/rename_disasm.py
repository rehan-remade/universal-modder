"""Make an obfuscated B3DDecomp disassembly decompilable: recovered names in, CB2-isms out.

Copies SRC_disasm to OUT_disasm (B3DDecomp only takes folders ending in "_disasm/") and
  - replaces hashed symbols with recovered names (NAMES.json from b3dnames.py), lower case as the stock
    compiler writes them: _builtIn_f<hash> -> _builtIn_f<name>, _f<hash> -> _f<name>, _t<hash> -> _t<name>,
    file names included;
  - rewrites userlib calls compiled as `mov reg, [@f__LIBS]` ... `call reg` into `call @f__LIBS`;
  - turns real function-pointer calls (`call reg` with no lib load) into calls to stand-in lib functions
    @_findirectcallN__LIBS, one per site (a shared stand-in breaks the parameter-count solver);
  - types the dynamic-vector fields whose descriptor B3DDecomp misreads as a string constant as int;
  - appends runtime command signatures B3DDecomp's symbol scan missed (EXTRA_SIGS, one per line) to
    BuiltInSymbols.txt, so those builtins get parameter lists.

Usage:
  python -I rename_disasm.py uerm_disasm NAMES.json uerm_named_disasm [--extra-sigs SIGS.txt]
"""
import argparse
import json
import os
import re
import shutil

TOK = re.compile(r"(_builtIn_f|_f|_t)([A-Z0-9]{6,})(?![A-Za-z0-9])")
LIBLOAD = re.compile(r"^(\s+@[0-9A-F]+: [0-9A-F ]+?\s+)mov (e[a-d]x|esi|edi), \[(@\w+__LIBS)\]\s*$")
CALLREG = re.compile(r"^(\s+@[0-9A-F]+: [0-9A-F ]+?\s+)call (e[a-d]x|esi|edi)\s*$")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("names")
    ap.add_argument("dst")
    ap.add_argument("--extra-sigs")
    a = ap.parse_args()
    src, dst = a.src.rstrip("/\\"), a.dst.rstrip("/\\")
    assert dst.endswith("_disasm"), "B3DDecomp only reads folders named *_disasm"
    table = json.load(open(a.names))
    count = {}

    def bump(k):
        count[k] = count.get(k, 0) + 1

    def sub(m):
        pre, body = m.group(1), m.group(2)
        name = table.get("_f" + body)
        if not name:
            return m.group(0)
        bump({"_builtIn_f": "builtin", "_f": "function", "_t": "type"}[pre])
        return pre + name.lower()

    def direct_lib_calls(text):
        out, pending = [], {}
        for line in text.split("\n"):
            m = LIBLOAD.match(line)
            if m:
                pending[m.group(2)] = m.group(3)
                out.append(m.group(1) + "mov %s, 0x0" % m.group(2))
                continue
            m = CALLREG.match(line)
            if m and m.group(2) in pending:
                out.append(m.group(1) + "call " + pending.pop(m.group(2)))
                bump("libcall")
                continue
            if m:
                out.append(m.group(1) + "call @_findirectcall%d__LIBS" % count.get("indirect", 0))
                bump("indirect")
                continue
            out.append(line)
        return "\n".join(out)

    shutil.rmtree(dst, ignore_errors=True)
    for root, _, files in os.walk(src):
        out_root = dst + root[len(src):]
        os.makedirs(out_root, exist_ok=True)
        for f in files:
            text = open(os.path.join(root, f), encoding="latin-1").read()
            name = TOK.sub(sub, f[:-4]) + ".txt" if f.endswith(".txt") else f
            text = TOK.sub(sub, text)
            if os.path.basename(root) == "Type":
                text = re.sub(r"(Field \d+: )StringConstant_\w*", r"\1_builtIn__bbIntType", text)
            if os.path.basename(root) == "Code":
                text = direct_lib_calls(text)
            open(os.path.join(out_root, name), "w", encoding="latin-1", newline="").write(text)
    if a.extra_sigs:
        have = set(open(os.path.join(src, "BuiltInSymbols.txt"), encoding="latin-1").read().splitlines())
        extra = open(a.extra_sigs, encoding="latin-1").read().splitlines()
        with open(os.path.join(dst, "BuiltInSymbols.txt"), "a", encoding="latin-1") as fh:
            fh.write("".join(line + "\n" for line in extra if line and line not in have))
    print(count)


if __name__ == "__main__":
    main()
