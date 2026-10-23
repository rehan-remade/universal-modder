"""Offline tests for `um cp77` (archive parsing, layout, install/uninstall, conflicts) and `um nexus` (parsing,
file picking, key storage). No network, no real game: a fake install folder and a synthetic .archive.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from um import cp77, nexus  # noqa: E402


# --------------------------------------------------------------------------- helpers

def write_archive(path: Path, hashes: list[int]):
    """A minimal REDengine 4 .archive: 40-byte header, padding, then an index with one entry per hash."""
    entries = b"".join(struct.pack("<QQIIIII20s", h, 0, 0, 0, 1, 0, 0, b"\0" * 20) for h in hashes)
    index = struct.pack("<IIQIII", 8, len(entries) + 20, 0, len(hashes), len(hashes), 0) + entries
    data = b"\xd9" * 64  # where file payloads would be
    index_pos = 40 + len(data)
    head = struct.pack("<4sIQIQIQ", b"RDAR", 12, index_pos, len(index), 0, 0, index_pos + len(index))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(head + data + index)


@pytest.fixture
def game(tmp_path, monkeypatch):
    """A fake Cyberpunk install, and UM_HOME pointed at a scratch state folder."""
    g = tmp_path / "Cyberpunk 2077"
    (g / "bin" / "x64").mkdir(parents=True)
    (g / "bin" / "x64" / "Cyberpunk2077.exe").write_bytes(b"MZ")
    (g / "archive" / "pc" / "mod").mkdir(parents=True)
    (g / "archive" / "pc" / "content").mkdir(parents=True)
    (g / "r6" / "config").mkdir(parents=True)
    (g / "r6" / "config" / "inputUserMappings.xml").write_text("<vanilla/>")
    monkeypatch.setenv("UM_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(cp77, "wolvenkit_cli", lambda: None)
    cp77._save("config.json", {"game": str(g)})
    return g


def make_zip(path: Path, files: dict[str, bytes]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)


def archive_bytes(hashes: list[int]) -> bytes:
    p = Path(os.environ.get("TMP", "/tmp")) / f"_um_{os.getpid()}_{hashes[0] if hashes else 0}.archive"
    write_archive(p, hashes)
    b = p.read_bytes()
    p.unlink()
    return b


# --------------------------------------------------------------------------- archives and hashes

def test_fnv1a64_known_values():
    assert cp77.fnv1a64("") == 0xCBF29CE484222325
    assert cp77.fnv1a64("a") == 0xAF63DC4C8601EC8C


def test_archive_hashes_round_trip(tmp_path):
    hs = [cp77.fnv1a64("base/characters/a.mesh"), cp77.fnv1a64("base/characters/b.xbm"), 7]
    p = tmp_path / "x.archive"
    write_archive(p, hs)
    assert cp77.archive_hashes(p) == hs
    (tmp_path / "bad.archive").write_bytes(b"PK\x03\x04" + b"\0" * 60)
    with pytest.raises(cp77.Cp77Error):
        cp77.archive_hashes(tmp_path / "bad.archive")


def test_nexus_stem_strips_ids():
    assert cp77.nexus_stem("Better Trees-1234-2-0-1700000000") == "Better Trees"
    assert cp77.nexus_stem("HD Reworked-5678-1-0-1-1690000000") == "HD Reworked"
    assert cp77.nexus_stem("plain_name") == "plain_name"


# --------------------------------------------------------------------------- layout

def test_plan_layout_known_roots_loose_files_and_cet(tmp_path):
    root = tmp_path / "x"
    files = {
        "MyMod/archive/pc/mod/a.archive": b"", "MyMod/archive/pc/mod/a.archive.xl": b"",
        "MyMod/r6/tweaks/mymod/t.yaml": b"", "loose.archive": b"", "notes/readme.txt": b"",
        "MyCET/init.lua": b"", "MyCET/lib/util.lua": b"", "fix.reds": b"", "tweak.yaml": b"",
        "mods/RedThing/info.json": b"{}", "mods/RedThing/archives/r.archive": b"",
        "preview.png": b"", "mystery.bin": b"",
    }
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    placed, skipped, unplaced = cp77.plan_layout(root, "Demo")
    dests = {src.relative_to(root).as_posix(): d for src, d in placed}
    assert dests["MyMod/archive/pc/mod/a.archive"] == "archive/pc/mod/a.archive"
    assert dests["MyMod/archive/pc/mod/a.archive.xl"] == "archive/pc/mod/a.archive.xl"
    assert dests["MyMod/r6/tweaks/mymod/t.yaml"] == "r6/tweaks/mymod/t.yaml"
    assert dests["loose.archive"] == "archive/pc/mod/loose.archive"
    assert dests["MyCET/init.lua"] == "bin/x64/plugins/cyber_engine_tweaks/mods/MyCET/init.lua"
    assert dests["MyCET/lib/util.lua"] == "bin/x64/plugins/cyber_engine_tweaks/mods/MyCET/lib/util.lua"
    assert dests["fix.reds"] == "r6/scripts/Demo/fix.reds"
    assert dests["tweak.yaml"] == "r6/tweaks/Demo/tweak.yaml"
    assert dests["mods/RedThing/info.json"] == "mods/RedThing/info.json"
    assert dests["mods/RedThing/archives/r.archive"] == "mods/RedThing/archives/r.archive"
    assert sorted(skipped) == ["notes/readme.txt", "preview.png"]
    assert unplaced == ["mystery.bin"]


def test_plan_layout_cet_at_root_and_pick(tmp_path):
    root = tmp_path / "x"
    for rel in ("init.lua", "Vanilla/body.archive", "Lush/body.archive"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(b"")
    placed, _, _ = cp77.plan_layout(root, "Demo")
    dests = {src.relative_to(root).as_posix(): d for src, d in placed}
    assert dests["init.lua"] == "bin/x64/plugins/cyber_engine_tweaks/mods/Demo/init.lua"
    assert dests["Vanilla/body.archive"] == dests["Lush/body.archive"] == "archive/pc/mod/body.archive"
    placed, _, _ = cp77.plan_layout(root, "Demo", pick="lush")
    assert [d for _, d in placed] == ["archive/pc/mod/body.archive"]
    with pytest.raises(cp77.Cp77Error):
        cp77.plan_layout(root, "Demo", pick="nope")


# --------------------------------------------------------------------------- install, conflicts, uninstall

def test_install_conflicts_uninstall(game, tmp_path, capsys):
    shared = cp77.fnv1a64("base/env/road.xbm")
    a_zip = tmp_path / "Road Textures-100-1-0-1700000000.zip"
    make_zip(a_zip, {"archive/pc/mod/zz_road.archive": archive_bytes([shared, 11]), "readme.txt": b"hi"})
    b_zip = tmp_path / "b.zip"
    make_zip(b_zip, {"!!aa_road.archive": archive_bytes([shared, 22]), "fix.reds": b"// x"})
    (a_zip.parent / (a_zip.name + ".nexus.json")).write_text(json.dumps(
        {"game": "cyberpunk2077", "mod_id": 100, "file_id": 5, "mod_name": "Road Textures", "file_version": "1.0"}))

    cp77.install_paths([a_zip])
    cp77.install_paths([b_zip], name="Other Road")
    man = cp77.manifest()
    assert set(man["mods"]) == {"Road Textures", "Other Road"}
    assert man["mods"]["Road Textures"]["nexus"]["mod_id"] == 100
    assert (game / "archive/pc/mod/zz_road.archive").exists()
    assert (game / "r6/scripts/Other Road/fix.reds").exists()
    assert man["mods"]["Road Textures"]["archives"]["archive/pc/mod/zz_road.archive"] == [shared, 11]

    # the same mod again is refused; --replace reinstalls
    with pytest.raises(cp77.Cp77Error):
        cp77.install_paths([a_zip])
    cp77.install_paths([a_zip], replace=True)

    # a file another mod owns is refused
    c_zip = tmp_path / "c.zip"
    make_zip(c_zip, {"archive/pc/mod/zz_road.archive": archive_bytes([33])})
    with pytest.raises(cp77.Cp77Error, match="belong to other mods"):
        cp77.install_paths([c_zip], name="Clash")

    # load order: '!!aa' sorts first and wins the shared path
    assert cp77.load_order(game) == ["!!aa_road.archive", "zz_road.archive"]
    (game / "archive/pc/mod/modlist.txt").write_text("zz_road.archive\n")
    assert cp77.load_order(game) == ["zz_road.archive", "!!aa_road.archive"]
    capsys.readouterr()
    cp77.report_conflicts(game, cp77.manifest())
    out = capsys.readouterr().out
    assert "1 shared path(s), zz_road.archive wins" in out

    # overwriting an unowned (vanilla) file needs --overwrite, is backed up, and comes back on uninstall
    d_zip = tmp_path / "d.zip"
    make_zip(d_zip, {"r6/config/inputUserMappings.xml": b"<modded/>"})
    with pytest.raises(cp77.Cp77Error, match="no mod owns them"):
        cp77.install_paths([d_zip], name="Keys")
    cp77.install_paths([d_zip], name="Keys", overwrite=True)
    assert (game / "r6/config/inputUserMappings.xml").read_text() == "<modded/>"
    cp77.uninstall("Keys")
    assert (game / "r6/config/inputUserMappings.xml").read_text() == "<vanilla/>"

    # a changed file is kept unless --force
    (game / "r6/scripts/Other Road/fix.reds").write_text("// edited")
    cp77.uninstall("Other Road")
    assert (game / "r6/scripts/Other Road/fix.reds").exists()
    assert not (game / "archive/pc/mod/!!aa_road.archive").exists()
    cp77.uninstall("Other Road", force=True)
    assert not (game / "r6/scripts/Other Road").exists()
    assert "Other Road" not in cp77.manifest()["mods"]

    # check: a stray archive nobody recorded
    write_archive(game / "archive/pc/mod/stray.archive", [44])
    capsys.readouterr()
    cp77.check(game, cp77.manifest())
    assert "archive/pc/mod/stray.archive" in capsys.readouterr().out


def test_variants_need_pick(game, tmp_path):
    z = tmp_path / "v.zip"
    make_zip(z, {"Vanilla/body.archive": archive_bytes([1]), "Lush/body.archive": archive_bytes([2])})
    with pytest.raises(cp77.Cp77Error, match="--pick"):
        cp77.install_paths([z], name="Body")
    cp77.install_paths([z], name="Body", pick="Lush")
    assert cp77.manifest()["mods"]["Body"]["archives"]["archive/pc/mod/body.archive"] == [2]


def test_vanilla_index(game):
    write_archive(game / "archive/pc/content/basegame_1.archive", [100, 200, 300])
    assert cp77.vanilla_overrides([100]) is None
    assert cp77.build_vanilla_index(game) == 3
    assert cp77.vanilla_overrides([100, 300, 999]) == 2


# --------------------------------------------------------------------------- nexus

def test_parse_nxm():
    d = nexus.parse_nxm("nxm://cyberpunk2077/mods/1234/files/5678?key=abc&expires=1700000000&user_id=9")
    assert d == dict(game="cyberpunk2077", mod_id=1234, file_id=5678, key="abc", expires="1700000000", user_id="9")
    for bad in ("https://www.nexusmods.com/cyberpunk2077/mods/1234", "nxm://cyberpunk2077/mods/1234"):
        with pytest.raises(nexus.NexusError):
            nexus.parse_nxm(bad)


def test_pick_file():
    files = [dict(file_id=1, category_name="MAIN", is_primary=False, name="A", version="1", size_kb=1),
             dict(file_id=2, category_name="OPTIONAL", is_primary=False, name="B", version="1", size_kb=1)]
    assert nexus.pick_file(files)["file_id"] == 1
    assert nexus.pick_file(files, 2)["file_id"] == 2
    with pytest.raises(nexus.NexusError):
        nexus.pick_file(files, 3)
    files.append(dict(file_id=3, category_name="MAIN", is_primary=False, name="C", version="2", size_kb=1))
    with pytest.raises(nexus.NexusError, match="2 main files"):
        nexus.pick_file(files)
    files[2]["is_primary"] = True
    assert nexus.pick_file(files)["file_id"] == 3


def test_key_sources(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXUS_API_KEY", raising=False)
    monkeypatch.setenv("UM_NEXUS_KEY_FILE", str(tmp_path / "k"))
    assert nexus.key_sources() == []
    assert nexus.nexus_key(required=False) is None
    (tmp_path / "k").write_text("filekey\n")
    assert [k for _, k in nexus.key_sources()] == ["filekey"]
    monkeypatch.setenv("NEXUS_API_KEY", "envkey")
    assert nexus.nexus_key() == "envkey"
