"""Symbolically run the B3DDecomp disassembly of CB2's weapon-init function and dump, per weapon, every
constant stored into the weapon template's fields. Output: JSON {weapon_id: {"path":..., "stores": [...]}}.

Usage: python -I weapon_table.py Code/_fTXZD02FB0ZX.txt Strings.txt OUT.json
"""
import json
import re
import struct
import sys

INS = re.compile(r"^\s+@([0-9A-F]+): (?:[0-9A-F]{2} )+\s*(\w+)\s*(.*)$")

strings = {}
lines = open(sys.argv[2], encoding="latin-1").read().splitlines()
for i, l in enumerate(lines):
    m = re.match(r"@[0-9A-F]+: (StringConstant_\w+)", l)
    if m and i + 1 < len(lines):
        strings[m.group(1)] = lines[i + 1].strip().rsplit(" 00", 1)[0].strip('"')


def imm(s):
    s = s.strip()
    if s.startswith("0x"):
        return int(s, 16)
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return None


def as_float(v):
    if isinstance(v, int):
        return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]
    return None


def fmt(v):
    if v is None:
        return "?"
    k = v[0]
    if k == "imm":
        x = v[1]
        f = as_float(x)
        if x in (0, 0x80000000) or abs(x) < 100000:
            return str(x) if x != 0x80000000 else "-0.0"
        return "%.6gf" % f
    if k == "strc":
        return json.dumps(strings.get(v[1], v[1]))
    if k == "call":
        return "%s(%s)" % (v[1], ", ".join(fmt(a) for a in v[2]))
    if k == "field":
        return "F[0x%x]" % v[1]
    if k == "deref":
        return "*" + fmt(v[1])
    if k == "add":
        return "(%s+0x%x)" % (fmt(v[1]), v[2])
    return str(v)


def target(v):
    # F[off] / F[off][k]
    if v and v[0] == "field":
        return "0x%02x" % v[1]
    if v and v[0] == "deref" and v[1][0] == "field":
        return "0x%02x[0]" % v[1][1]
    if v and v[0] == "add" and v[1][0] == "deref" and v[1][1][0] == "field":
        return "0x%02x[%d]" % (v[1][1][1], v[2] // 4)
    return fmt(v)


regs, loc, stack = {}, {}, {}
weapons, cur = {}, None
for line in open(sys.argv[1], encoding="latin-1"):
    m = INS.match(line)
    if not m:
        continue
    addr, op, args = m.groups()
    a = [x.strip() for x in args.split(",")] if args else []
    if op == "mov" and len(a) == 2:
        dst, src = a
        dst = dst.replace("dword ", "")
        sm = re.fullmatch(r"\[esp(?:\+(0x[0-9a-f]+))?\]", dst)
        if sm:
            off = int(sm.group(1), 16) if sm.group(1) else 0
            stack[off] = ("imm", imm(src)) if imm(src) is not None else regs.get(src)
            continue
        lm = re.fullmatch(r"\[ebp-(0x[0-9a-f]+)\]", dst)
        if lm:
            loc[lm.group(1)] = regs.get(src)
            continue
        dm = re.fullmatch(r"\[(\w+)\]", dst)
        if dm:
            if cur is not None:
                weapons[cur]["stores"].append([target(regs.get(dm.group(1))), fmt(regs.get(src)), addr])
            continue
        if src.startswith("@StringConstant"):
            regs[dst] = ("strc", src[1:])
        elif imm(src) is not None:
            regs[dst] = ("imm", imm(src))
        elif re.fullmatch(r"\[ebp-(0x[0-9a-f]+)\]", src):
            regs[dst] = loc.get(src[5:-1])
        elif re.fullmatch(r"\[(\w+)\]", src):
            regs[dst] = ("deref", regs.get(src[1:-1]))
        elif src in ("eax", "ebx", "ecx", "edx", "esi", "edi"):
            regs[dst] = regs.get(src)
        else:
            regs[dst] = None
    elif op == "add" and len(a) == 2 and a[0] != "esp" and imm(a[1]) is not None:
        regs[a[0]] = ("add", regs.get(a[0]) or ("?",), imm(a[1]))
    elif op == "lea":
        regs[a[0]] = ("local", a[1])
    elif op == "call":
        name = a[0].lstrip("@")
        args_ = [stack[k] for k in sorted(stack)]
        if name == "_builtIn__bbFieldPtrAdd":
            regs["eax"] = ("field", stack.get(4, ("imm", -1))[1])
        elif name == "_builtIn__bbStrConst":
            regs["eax"] = stack.get(0)
        elif name == "_builtIn__bbStrStore":
            if cur is not None:
                weapons[cur]["stores"].append([target(stack.get(0)), fmt(stack.get(4)), addr])
        elif name == "_builtIn__bbObjLoad":
            regs["eax"] = ("obj",)
        else:
            res = ("call", name, args_)
            regs["eax"] = res
            if name == "_fTXDDB62DBZ" and args_ and args_[0][0] == "imm":
                cur = args_[0][1]
                weapons[cur] = {"path": fmt(args_[1]) if len(args_) > 1 else "?", "args": [fmt(x) for x in args_],
                                "stores": [], "calls": []}
            elif cur is not None and name != "_builtIn__bbObjStore":
                weapons[cur]["calls"].append([fmt(res), addr])
        stack = {}
json.dump(weapons, open(sys.argv[3], "w"), indent=1)
for wid, w in weapons.items():
    print(wid, w["path"], len(w["stores"]), "stores")
