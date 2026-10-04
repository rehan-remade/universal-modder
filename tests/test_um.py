"""Offline tests for the pieces that don't need a game, a GPU or a fal key.

    uv run --with pytest pytest -q
"""
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from um import backup, fal, publish, scan, sprite, video  # noqa: E402


# --------------------------------------------------------------------------- scan

def make(root: Path, files: dict):
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())


def engine_of(tmp_path, files):
    make(tmp_path, files)
    hits, _ = scan.detect(scan.Index(tmp_path))
    return hits[0][0], hits[0][3]


def test_unity_mono_and_version(tmp_path):
    key, det = engine_of(tmp_path, {
        "UnityPlayer.dll": b"MZ", "Game_Data/Managed/Assembly-CSharp.dll": b"MZ",
        "Game_Data/globalgamemanagers": b"\0" * 20 + b"2022.3.21f1\0" + b"\0" * 100,
        "Game_Data/app.info": "Studio\nCoolGame",
    })
    assert key == "unity-mono"
    assert det["version"] == "2022.3.21f1" and det["product"] == "CoolGame"


def test_unity_il2cpp(tmp_path):
    key, _ = engine_of(tmp_path, {"UnityPlayer.dll": b"MZ", "GameAssembly.dll": b"MZ",
                                  "Game_Data/il2cpp_data/Metadata/global-metadata.dat": b"\xaf\x1b\xb1\xfa"})
    assert key == "unity-il2cpp"


def test_unreal_version_from_exe(tmp_path):
    exe = b"MZ" + b"\0" * 5000 + "++UE5+Release-5.3".encode("utf-16-le") + b"\0" * 100
    key, det = engine_of(tmp_path, {"Proj/Binaries/Win64/Proj-Win64-Shipping.exe": exe, "Proj/Content/Paks/Proj-Windows.pak": b"x",
                                    "Proj/Content/Paks/Proj-Windows.utoc": b"x"})
    assert key == "unreal" and det["engine_version"] == "UE5+Release-5.3" and det["iostore"]


def test_godot_pck(tmp_path):
    key, det = engine_of(tmp_path, {"game.exe": b"MZ", "game.pck": b"GDPC" + struct.pack("<4I", 2, 4, 2, 1)})
    assert key == "godot" and det["version"].startswith("4.2.1")


def test_gamemaker_and_rpgmaker(tmp_path):
    assert engine_of(tmp_path / "a", {"data.win": b"FORM\0\0\0\0GEN8\0\0\0\0\0\x11"})[0] == "gamemaker"
    assert engine_of(tmp_path / "b", {"www/js/rpg_core.js": "//", "Game.exe": b"MZ"})[0] == "rpgmaker-mvmz"


def test_managed_pe(tmp_path):
    # minimal PE32 with a CLR header directory entry
    pe = bytearray(1024)
    pe[0:2] = b"MZ"
    struct.pack_into("<I", pe, 0x3C, 0x80)
    pe[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", pe, 0x84, 0x14C)
    opt = 0x80 + 24
    struct.pack_into("<H", pe, opt, 0x10B)
    struct.pack_into("<I", pe, opt + 96 + 14 * 8, 0x2000)
    p = tmp_path / "Game.exe"
    p.write_bytes(bytes(pe))
    assert scan.pe_info(p) == {"arch": "x86", "managed": True}


def test_vdf():
    d = scan._vdf('"AppState" { "appid" "105600" "name" "Terraria" "installdir" "Terraria" }')
    assert d["AppState"]["installdir"] == "Terraria"


@pytest.mark.parametrize("library_name,install_name,game_name", [
    ("SteamLibrary", "ExampleGame", "Example Game"),
    ("SteamLibrary", "ExampleGame", "Example Game\u2122"),
    ("SteamLibrary", "Jeu\u00e9", "Example Game"),
    ("Biblioth\u00e8que", "ExampleGame", "Example Game"),
])
def test_steam_games_utf8(tmp_path, monkeypatch, library_name, install_name, game_name):
    root = tmp_path / "Steam"
    library = tmp_path / library_name
    apps = library / "steamapps"
    game_path = apps / "common" / install_name
    game_path.mkdir(parents=True)
    (root / "steamapps").mkdir(parents=True)
    (root / "steamapps/libraryfolders.vdf").write_text(
        '"libraryfolders" { "0" { "path" "' + library.as_posix() + '" } }', encoding="utf-8",
    )
    (apps / "appmanifest_123.acf").write_text(
        f'"AppState" {{ "appid" "123" "name" "{game_name}" "installdir" "{install_name}" }}',
        encoding="utf-8",
    )
    monkeypatch.setattr(scan, "steam_roots", lambda: [root])

    # Emulate a non-UTF-8 Windows default on every test platform, using real files.
    original_read_text = Path.read_text

    def read_text(path, encoding=None, errors=None, **kwargs):
        return original_read_text(path, encoding=encoding or "cp1252", errors=errors, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)

    assert scan.steam_games() == [{
        "store": "steam", "appid": "123", "name": game_name,
        "path": str(game_path), "workshop": None,
    }]


# --------------------------------------------------------------------------- sprite

def sprite_on_white(w=64, h=48):
    im = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    for x in range(20, 40):
        for y in range(10, 30):
            im.putpixel((x, y), (200, 30, 30, 255))
    im.putpixel((30, 20), (255, 255, 255, 255))   # an interior white "eye" must survive
    return im


def test_cutout_keeps_interior_white():
    out = sprite.cutout(sprite_on_white())
    assert out.size == (20, 20)
    assert out.getpixel((10, 10))[3] == 255          # the interior white pixel is still opaque
    assert out.getpixel((0, 0))[:3] == (200, 30, 30)


def test_fit_and_hard_alpha():
    f = sprite.fit(sprite.cutout(sprite_on_white()), 10, 10, anchor="bottom")
    assert f.size == (10, 10) and f.getbbox()[3] == 10
    assert set(sprite.hard_alpha(f).getchannel("A").getdata()) <= {0, 255}


def test_sheet_slice_roundtrip():
    frames = [Image.new("RGBA", (8, 8), (i * 40, 0, 0, 255)) for i in range(5)]
    sh = sprite.sheet(frames, cols=3)
    assert sh.size == (24, 16)
    assert len(sprite.slice_sheet(sh, 8, 8)) == 5


def test_team_mask():
    im = Image.new("RGBA", (4, 1), (0, 0, 0, 255))
    im.putpixel((0, 0), (20, 60, 240, 255))            # saturated blue -> player colour
    im.putpixel((1, 0), (200, 200, 200, 255))          # grey stays
    rgb, mask = sprite.team_mask(im)
    assert mask.getpixel((0, 0)) > 200 and mask.getpixel((1, 0)) == 0


def test_seamless_edges_match():
    import numpy as np
    ramp = np.tile(np.linspace(0, 255, 64)[None, :, None], (64, 1, 4)).astype(np.uint8)   # huge seam at the wrap
    ramp[..., 3] = 255
    out = np.asarray(sprite.seamless(Image.fromarray(ramp))).astype(int)
    before = np.abs(ramp[:, 0, :3].astype(int) - ramp[:, -1, :3].astype(int)).mean()
    after = np.abs(out[:, 0, :3] - out[:, -1, :3]).mean()
    assert before > 200 and after < 12


# --------------------------------------------------------------------------- fal (offline parts)

def test_kv_and_urls(tmp_path):
    assert fal._kv(["prompt=a cat", "num_images:=2", "flag:=true"]) == {"prompt": "a cat", "num_images": 2, "flag": True}
    res = {"images": [{"url": "https://v3.fal.media/a.png", "content_type": "image/png"}, {"url": "https://v3.fal.media/b.png"}],
           "mask_image": {"url": "https://v3.fal.media/m.png"}}
    assert [u for _, u, _ in fal._urls_in(res)] == ["https://v3.fal.media/a.png", "https://v3.fal.media/b.png", "https://v3.fal.media/m.png"]


# --------------------------------------------------------------------------- publish

def test_publish_check(tmp_path, capsys):
    # fixtures assembled at runtime so this file doesn't trip the toolkit's own publish check
    fake_key = "FAL" + "_KEY=" + "abcdefghijklmnopqrstuvwxyz0123"
    ghidra_name = "FUN" + "_00401000"
    make(tmp_path / "mod", {"src/Mod.cs": f"int {ghidra_name}();\n// " + "Decompiled with ILSpy", "README.md": "My mod, built with dnSpy notes",
                            "config.txt": fake_key})
    make(tmp_path / "game", {"data/big.bin": b"x" * 4096})
    (tmp_path / "mod" / "copied.bin").write_bytes(b"x" * 4096)
    assert publish.check(str(tmp_path / "mod"), str(tmp_path / "game")) == 1
    out = capsys.readouterr().out
    assert "game file copied verbatim" in out and "FAL_KEY assignment" in out and "Ghidra auto-name" in out
    normalized = out.replace("\\", "/")
    assert "decompiler header x1 in src/Mod.cs" in normalized and "README.md" not in normalized.split("decompiler header")[-1].split("\n")[0]


# --------------------------------------------------------------------------- video

@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_compile_small_edl(tmp_path):
    for i, color in enumerate(["red", "blue"]):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=640x360:d=3:r=30", "-f", "lavfi", "-i", "sine=f=440:d=3",
                        "-shortest", str(tmp_path / f"c{i}.mp4")], check=True)
    edl = {"size": [640, 360], "fps": 30, "bpm": 120, "beat_lock": True, "transition": {"type": "cut"},
           "segments": [{"clip": "c0.mp4", "in": 0, "beats": 4, "hook": "Hello"},
                        {"clip": "c1.mp4", "in": 0.5, "beats": 4, "title": "A title", "credit": "@someone", "transition": {"type": "fade", "duration": 0.3}},
                        {"card": {"title": "The end"}, "dur": 1.5}]}
    (tmp_path / "edl.json").write_text(json.dumps(edl))
    video.compile_edl(tmp_path / "edl.json", str(tmp_path / "out.mp4"))
    info = video.probe(tmp_path / "out.mp4")
    assert abs(info["duration"] - (2 + 2 + 1.5)) < 0.15 and info["audio"]


# --------------------------------------------------------------------------- knowledge base

from um import kb  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def test_repo_knowledge_is_valid():
    root = REPO / "knowledge"
    for p, _, _ in kb.notes(root):
        fails, _ = kb.check_note(p, root)
        assert not fails, (p, fails)
    idx, rows = kb.build_index(root)
    assert (root / "INDEX.md").read_text(encoding="utf-8") == idx, "run `um kb index`"
    assert len(rows) >= 7


def test_kb_new_check_search(tmp_path):
    import shutil
    root = tmp_path / "knowledge"
    root.mkdir()
    shutil.copy(REPO / "knowledge" / "TEMPLATE.md", root / "TEMPLATE.md")
    p = kb.new_note(root, "Hades II", "A new boon god", agent="Codex (gpt-6)", route="loader-api")
    fails, _ = kb.check_note(p, root)
    assert any("unfilled template text" in f for f in fails)          # a fresh scaffold must not pass
    good = p.read_text(encoding="utf-8")
    good = good.replace("FILL IN: exact build", "1.0.1 (Steam)").replace("anti_cheat: FILL IN", "anti_cheat: none")
    good = good.replace("> Two to four sentences: what you built", "> Added a boon god via a Lua mod loader")
    good = good.replace("The most valuable section. Numbered; each one symptom → cause → fix.", "")
    good = good.replace("1. **Symptom.** What you saw. **Cause:** what it really was. **Fix:** what worked.",
                        "1. **Boons never offered.** **Cause:** pool cached at load. **Fix:** register before the run starts.")
    p.write_text(good, encoding="utf-8")
    fails, _ = kb.check_note(p, root)
    assert not fails, fails
    res = kb.search(root, ["boon"])
    assert res and res[0]["path"].endswith("a-new-boon-god.md")
    assert kb.search(root, ["boon"], route="native-hook") == []


def test_kb_check_rejects_secrets_and_dumps(tmp_path):
    note = tmp_path / "n.md"
    code = "\n".join(f"int x{i} = {i};" for i in range(160))
    note.write_text("---\nkind: technique\ntitle: t\ntags: [x]\ndate: 2026-09-30\nagents: [a]\n---\n# t\n"
                    f"```c\n{code}\n```\n" + "FAL" + "_KEY=abcdefghijklmnopqrstuvwxyz0123\n")
    fails, _ = kb.check_note(note)
    assert any("code block" in f for f in fails) and any("FAL_KEY" in f for f in fails)


@pytest.mark.parametrize("url", ["https://github.com/alice/universal-modder.git", "https://github.com/alice/universal-modder",
                                 "git@github.com:alice/universal-modder.git", "ssh://git@github.com/alice/universal-modder.git"])
def test_pr_head_from_fork(url):
    # gh looks a bare --head branch up in the base repo; a PR from a fork needs "<owner>:<branch>"
    assert kb.pr_head("kb/a-b", url) == "alice:kb/a-b"


def test_pr_head_same_repo():
    assert kb.pr_head("kb/a-b", None) == "kb/a-b"


# --------------------------------------------------------------------------- backup

def test_backup_handles_pre_1980_timestamps(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(backup, "_root", lambda name: (tmp_path / "snaps" / name).mkdir(parents=True, exist_ok=True)
                        or tmp_path / "snaps" / name)
    src = tmp_path / "src"
    make(src, {"old.txt": "from 1970", "new.txt": "fresh"})
    os.utime(src / "old.txt", (0, 0))
    zp = backup.create(str(src), name="t")
    assert set(backup._manifest(zp)["files"]) == {"old.txt", "new.txt"}
