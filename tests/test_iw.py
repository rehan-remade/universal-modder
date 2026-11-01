"""Offline tests for `um fastfile`, `um iwi` and `um weapon` (Call of Duty 4 / World at War files), and the IW scan route.

No game files: every fastfile, texture and weapon file here is built by the test.

    uv run --with pytest pytest -q tests/test_iw.py
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from um import fastfile, iwi, scan, weapon  # noqa: E402


# --------------------------------------------------------------------------- fastfile

def _rawfile(name: str, payload: bytes) -> bytes:
    # a RawFile as a zone serializes it: inline name and buffer pointers (-1) around the length, then the data
    return (b"\xff\xff\xff\xff" + struct.pack("<I", len(payload)) + b"\xff\xff\xff\xff" + name.encode() + b"\x00"
            + payload + b"\x00")


def _zone(tmp_path: Path, records: list[bytes], magic=b"IWffu100", version=387, name="test.ff") -> Path:
    p = tmp_path / name
    body = b"\x00" * 64 + b"".join(records) + b"\x00" * 16
    p.write_bytes(magic + struct.pack("<I", version) + zlib.compress(body))
    return p


def test_fastfile_lists_and_dumps_rawfiles(tmp_path, capsys):
    gsc = b"main()\n{\n\tlevel thread foo();\n}\n"
    p = _zone(tmp_path, [_rawfile("maps/test.gsc", gsc), _rawfile("ui/menu.menu", b"{ menuDef {} }")])
    version, data = fastfile.decompress_fastfile(p)
    assert version == 387
    assert fastfile.extract_rawfiles(data) == {"maps/test.gsc": gsc, "ui/menu.menu": b"{ menuDef {} }"}
    fastfile.list_fastfile(p)
    assert "maps/test.gsc" in capsys.readouterr().out
    out = tmp_path / "out"
    fastfile.dump_fastfile(p, out)
    assert (out / "maps" / "test.gsc").read_bytes() == gsc


def test_fastfile_dump_stays_in_its_folder(tmp_path):
    p = _zone(tmp_path, [_rawfile("../../escape.gsc", b"x"), _rawfile("maps/ok.gsc", b"y")])
    out = tmp_path / "out"
    fastfile.dump_fastfile(p, out)
    assert sorted(f.relative_to(out).as_posix() for f in out.rglob("*") if f.is_file()) == ["maps/ok.gsc"]
    assert not (tmp_path / "escape.gsc").exists() and not (tmp_path.parent / "escape.gsc").exists()


def test_fastfile_reads_cod4_and_refuses_signed_zones(tmp_path):
    assert fastfile.decompress_fastfile(_zone(tmp_path, [], version=5, name="cod4.ff"))[0] == 5
    with pytest.raises(SystemExit):
        fastfile.decompress_fastfile(_zone(tmp_path, [], magic=b"IWff0100", version=5, name="signed.ff"))
    with pytest.raises(SystemExit):
        fastfile.decompress_fastfile(_zone(tmp_path, [], magic=b"NOTAZONE", name="junk.ff"))


# --------------------------------------------------------------------------- iwi

def _mip_sizes(w: int, h: int, block: int) -> list[int]:
    # whole chain down to 1x1 on the longer side, every level at least one 4x4 block (as OpenAssetTools counts it)
    sizes = []
    while True:
        sizes.append(((w + 3) // 4) * ((h + 3) // 4) * block)
        if max(w, h) == 1:
            return sizes
        w, h = max(1, w // 2), max(1, h // 2)


def test_iwi_header_is_width_first_with_the_whole_mip_chain(tmp_path):
    src = tmp_path / "in.png"
    Image.new("RGBA", (64, 16), (200, 40, 40, 255)).save(src)
    dst = tmp_path / "t.iwi"
    iwi.png_to_iwi(src, dst, "dxt1", True)
    data = dst.read_bytes()
    assert data[:4] == b"IWi\x06"
    fmt, flags, w, h, d = struct.unpack("<BBHHH", data[4:12])
    assert (fmt, flags, w, h, d) == (0x0B, 0x00, 64, 16, 1)
    sizes = _mip_sizes(64, 16, 8)
    assert len(sizes) == 7 and len(data) == 28 + sum(sizes)
    # fileSizeForPicmip[i]: everything up to and including level i (levels are stored smallest first)
    assert struct.unpack("<4I", data[12:28]) == tuple(28 + sum(sizes[i:]) for i in range(4))


def test_iwi_sizes_match_the_note(tmp_path):
    # the WaW notes give 131,100 bytes for a 512x512 DXT1 without mips and 174,804 with the whole chain
    assert 28 + _mip_sizes(512, 512, 8)[0] == 131_100 and 28 + sum(_mip_sizes(512, 512, 8)) == 174_804
    src = tmp_path / "in.png"
    Image.new("RGBA", (8, 8), (0, 0, 0, 255)).save(src)
    iwi.png_to_iwi(src, tmp_path / "one.iwi", "dxt1", False)
    data = (tmp_path / "one.iwi").read_bytes()
    assert data[5] == 0x03 and len(data) == 28 + 4 * 8
    assert struct.unpack("<4I", data[12:28]) == (len(data),) * 4


@pytest.mark.parametrize("fmt", ["dxt1", "dxt5"])
def test_iwi_round_trip_keeps_size_and_colours(tmp_path, fmt):
    # non-square, so swapped width and height would show; the colour split sits on a block edge
    im = Image.new("RGBA", (32, 8), (255, 0, 0, 255))
    im.paste((0, 0, 255, 255), (16, 0, 32, 8))
    if fmt == "dxt5":
        im.paste((0, 0, 255, 0), (28, 0, 30, 8))  # alpha 0 and 255 in one block
    src = tmp_path / "in.png"
    im.save(src)
    iwi.png_to_iwi(src, tmp_path / "t.iwi", fmt, True)
    iwi.iwi_to_png(tmp_path / "t.iwi", tmp_path / "out.png")
    out = Image.open(tmp_path / "out.png").convert("RGBA")
    assert out.size == (32, 8)
    assert out.getpixel((2, 2)) == (255, 0, 0, 255) and out.getpixel((20, 5)) == (0, 0, 255, 255)
    if fmt == "dxt5":
        assert out.getpixel((29, 3))[3] == 0 and out.getpixel((31, 3))[3] == 255


def _one_block_iwi(path: Path, fmt: int, block: bytes):
    path.write_bytes(b"IWi\x06" + struct.pack("<BBHHH4I", fmt, 0x03, 4, 4, 1, *(28 + len(block),) * 4) + block)


def test_iwi_dxt3_alpha_and_four_colour_blocks(tmp_path):
    # DXT3: explicit 4-bit alpha per pixel; its colour block always has four colours, even when c0 <= c1
    alpha = sum(i << (4 * i) for i in range(16)).to_bytes(8, "little")
    colour = struct.pack("<HHI", 0x001F, 0xF800, 0xFFFFFFFF)  # c0 blue < c1 red, every pixel index 3
    _one_block_iwi(tmp_path / "dxt3.iwi", 0x0C, alpha + colour)
    iwi.iwi_to_png(tmp_path / "dxt3.iwi", tmp_path / "dxt3.png")
    out = Image.open(tmp_path / "dxt3.png").convert("RGBA")
    assert [out.getpixel((i % 4, i // 4))[3] for i in range(16)] == [i * 17 for i in range(16)]
    assert out.getpixel((0, 0))[:3] == (170, 0, 85)  # (c0 + 2*c1) / 3, not DXT1's transparent black
    # the same colour block in DXT1 is three colours plus transparent black
    _one_block_iwi(tmp_path / "dxt1.iwi", 0x0B, colour)
    iwi.iwi_to_png(tmp_path / "dxt1.iwi", tmp_path / "dxt1.png")
    assert Image.open(tmp_path / "dxt1.png").convert("RGBA").getpixel((1, 1)) == (0, 0, 0, 0)


# --------------------------------------------------------------------------- weapon

WEAPON = "WEAPONFILE\\displayName\\WEAPON_TEST\\damage\\40\\clipSize\\8\\notetrackSoundMap\\a b\nc d\n"


def test_weapon_set_writes_a_copy_and_keeps_the_order(tmp_path):
    src = tmp_path / "test_gun"
    src.write_text(WEAPON, encoding="latin-1")
    with pytest.raises(SystemExit):
        weapon.set_weapon(src, ["damage=90"])  # neither -o nor --in-place
    out = tmp_path / "mod" / "weapons" / "sp" / "test_gun"
    weapon.set_weapon(src, ["damage=90", "newKey=1"], out)
    assert src.read_text(encoding="latin-1") == WEAPON
    header, props, keys = weapon.parse_weapon(out)
    assert header == "WEAPONFILE"
    assert keys == ["displayName", "damage", "clipSize", "notetrackSoundMap", "newKey"]
    assert props["damage"] == "90" and props["notetrackSoundMap"] == "a b\nc d"
    weapon.set_weapon(out, ["clipSize=14"], in_place=True)
    assert weapon.parse_weapon(out)[1]["clipSize"] == "14"


def test_weapon_keeps_non_utf8_bytes(tmp_path):
    src = tmp_path / "w"
    src.write_bytes(b"WEAPONFILE\\displayName\\Caf\xe9\\damage\\40")
    weapon.set_weapon(src, ["damage=41"], tmp_path / "w2")
    assert (tmp_path / "w2").read_bytes() == b"WEAPONFILE\\displayName\\Caf\xe9\\damage\\41\\"


def test_weapon_clone_and_diff(tmp_path, capsys):
    src = tmp_path / "test_gun"
    src.write_text(WEAPON, encoding="latin-1")
    dst = tmp_path / "test_gun_up"
    weapon.clone_weapon(src, dst, damage=300, clip=14, explosive=True)
    props = weapon.parse_weapon(dst)[1]
    assert (props["damage"], props["minDamage"], props["clipSize"], props["weaponType"]) == ("300", "100", "14", "projectile")
    capsys.readouterr()
    weapon.diff_weapons(src, dst)
    out = capsys.readouterr().out
    assert "damage" in out and "40" in out and "300" in out


# --------------------------------------------------------------------------- scan

def _pe() -> bytes:
    # a minimal x86 PE32 image, enough for scan's exe fingerprinting
    pe = bytearray(1024)
    pe[0:2] = b"MZ"
    struct.pack_into("<I", pe, 0x3C, 0x80)
    pe[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", pe, 0x84, 0x14C)
    struct.pack_into("<H", pe, 0x80 + 24, 0x10B)
    return bytes(pe)


@pytest.mark.parametrize("folder, exe", [("Call of Duty World at War", "CoDWaW.exe"), ("Call of Duty 4", "iw3sp.exe")])
def test_iw_engine_route_and_punkbuster(tmp_path, folder, exe):
    d = tmp_path / folder
    files = {exe: _pe(), "zone/english/common.ff": b"IWffu100", "main/iw_00.iwd": b"PK", "pb/pbcl.dll": b"MZ"}
    files.update({f"f{i}.txt": b"x" for i in range(6)})
    for rel, data in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_bytes(data)
    r = scan.scan(str(d))
    assert r["engine"]["key"] == "iw"
    assert r["routes"][0]["why"] == "known game" and r["routes"][0]["playbook"] == "iw-engine.md"
    assert "PunkBuster" in r["anti_cheat"]
