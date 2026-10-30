"""Minimal reader for Valve VPK v1/v2 archives (`*_dir.vpk` + `*_NNN.vpk`).

Only what the converter needs: list entries and read one file's bytes.
"""
import os
import struct


class VPK:
    def __init__(self, dir_path):
        self.dir_path = dir_path
        self.base = dir_path[: -len("_dir.vpk")]
        self.entries = {}
        with open(dir_path, "rb") as f:
            data = f.read()
        sig, version, tree_size = struct.unpack_from("<III", data, 0)
        if sig != 0x55AA1234:
            raise ValueError(f"{dir_path}: not a VPK")
        header = 12 if version == 1 else 28
        self.data_offset = header + tree_size  # embedded data (archive index 0x7fff)
        self._dir_data = data
        p = header

        def cstr():
            nonlocal p
            e = data.index(b"\0", p)
            s = data[p:e].decode("latin-1")
            p = e + 1
            return s

        while True:
            ext = cstr()
            if not ext:
                break
            while True:
                path = cstr()
                if not path:
                    break
                while True:
                    name = cstr()
                    if not name:
                        break
                    crc, preload, arch, off, length, term = struct.unpack_from("<IHHIIH", data, p)
                    p += 18
                    pre = data[p:p + preload]
                    p += preload
                    full = (f"{path}/" if path != " " else "") + f"{name}.{ext}" if ext != " " else name
                    self.entries[full.lower()] = (arch, off, length, pre)

    def __contains__(self, path):
        return path.lower() in self.entries

    def read(self, path):
        arch, off, length, pre = self.entries[path.lower()]
        if length == 0:
            return pre
        if arch == 0x7FFF:
            body = self._dir_data[self.data_offset + off: self.data_offset + off + length]
        else:
            with open(f"{self.base}_{arch:03d}.vpk", "rb") as f:
                f.seek(off)
                body = f.read(length)
        return pre + body


class SourceFS:
    """Search path over loose folders and VPKs, first match wins (like gameinfo.txt)."""

    def __init__(self, roots):
        self.layers = []
        for r in roots:
            if r.endswith("_dir.vpk"):
                if os.path.exists(r):
                    self.layers.append(VPK(r))
            elif os.path.isdir(r):
                self.layers.append(r)

    def read(self, path):
        path = path.replace("\\", "/").lower()
        for layer in self.layers:
            if isinstance(layer, VPK):
                if path in layer:
                    return layer.read(path)
            else:
                full = os.path.join(layer, path)
                if os.path.exists(full):
                    with open(full, "rb") as f:
                        return f.read()
        return None

    def find(self, needle):
        out = []
        for layer in self.layers:
            if isinstance(layer, VPK):
                out += [k for k in layer.entries if needle in k]
        return sorted(set(out))
