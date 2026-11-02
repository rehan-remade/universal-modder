"""Set the Large Address Aware flag on the user's own collapse.exe (Collapse, 2008, Steam 289620).

Why: the engine's init_heap reserves all free address space below 0x70000000 before WinMain, leaving
~256 MB for the D3D driver, file mappings and DLLs. LAA gives the process 2 GB more above 0x80000000.

Changes exactly one bit (IMAGE_FILE_LARGE_ADDRESS_AWARE, 0x20 in the COFF Characteristics) and nothing
else. The PE checksum of this exe is 0 and stays 0 (the loader doesn't check it for .exe files).

    python laa_patch.py "D:\\...\\Collapse\\collapse.exe"            # backup to collapse.exe.bak, then patch
    python laa_patch.py "D:\\...\\Collapse\\collapse.exe" --dry-run  # only report
    python laa_patch.py "D:\\...\\Collapse\\collapse.exe" --restore  # put the backup back

Steam's "Verify integrity of game files" also restores the original exe.
"""
import argparse, hashlib, os, shutil, struct, sys

KNOWN = {  # sha256 -> build
    '3003600f506e4c1e9388716cc395fb958ef2d729ec8d291138b3f57f3bded283': 'Steam 289620 (PE 2008-10-13)',
}
LAA = 0x20

def sha(data): return hashlib.sha256(data).hexdigest()

def char_offset(data):
    if data[:2] != b'MZ': raise SystemExit('not an MZ executable')
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    if data[pe:pe + 4] != b'PE\0\0': raise SystemExit('no PE signature')
    if struct.unpack_from('<H', data, pe + 4)[0] != 0x14C: raise SystemExit('not an x86 (i386) image')
    return pe + 4 + 18  # COFF header: Machine, NumberOfSections, TimeDateStamp, PtrSym, NumSym, SizeOptHdr

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('exe'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--restore', action='store_true')
    a = ap.parse_args()
    exe, bak = a.exe, a.exe + '.bak'

    if a.restore:
        if not os.path.exists(bak): raise SystemExit('no backup at %s' % bak)
        b = open(bak, 'rb').read()
        if sha(b) not in KNOWN: raise SystemExit('backup hash is not a known original, refusing: %s' % sha(b))
        if not a.dry_run: shutil.copy2(bak, exe)
        print('restored %s from %s (%s)' % (exe, bak, KNOWN[sha(b)])); return

    data = bytearray(open(exe, 'rb').read())
    off = char_offset(data)
    ch = struct.unpack_from('<H', data, off)[0]
    if ch & LAA:
        print('already Large Address Aware (Characteristics=%#06x), nothing to do' % ch); return
    h = sha(data)
    if h not in KNOWN:
        raise SystemExit('unknown collapse.exe (sha256 %s); only known builds are patched' % h)
    print('%s: %s, Characteristics %#06x -> %#06x' % (exe, KNOWN[h], ch, ch | LAA))
    if a.dry_run: return

    if os.path.exists(bak):
        if sha(open(bak, 'rb').read()) != h: raise SystemExit('%s exists and differs from this exe; not overwriting it' % bak)
    else:
        shutil.copy2(exe, bak)
    struct.pack_into('<H', data, off, ch | LAA)
    tmp = exe + '.laa_tmp'
    with open(tmp, 'wb') as f: f.write(data)
    shutil.copystat(exe, tmp)
    os.replace(tmp, exe)
    print('patched; backup at %s; new sha256 %s' % (bak, sha(data)))

if __name__ == '__main__':
    main()
