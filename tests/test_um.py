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


def test_steam_root_from_registry(tmp_path, monkeypatch):
    # Steam installed outside Program Files (e.g. C:\Steam): its libraryfolders.vdf, and every library in it, was never read
    root = tmp_path / "Steam"
    (root / "steamapps").mkdir(parents=True)
    monkeypatch.setattr(scan, "steam_registry_root", lambda: root)
    assert root.resolve() in scan.steam_roots()

def test_known_game_longest_key_wins(tmp_path):
    # "grand theft auto v" is a substring of "grand theft auto v enhanced";
    # the more specific entry must win, not whichever lands first in the dict
    d = tmp_path / "Grand Theft Auto V Enhanced"
    d.mkdir()
    for i in range(6):
        (d / f"f{i}.txt").write_text("x")
    r = scan.scan(str(d))
    assert r["routes"][0]["route"] == scan.KNOWN["grand theft auto v enhanced"][0]


def test_record_encodes_and_tags_bt709(tmp_path, monkeypatch):
    # RGB frames -> yuv420p used the BT.601 matrix untagged; browsers read HD video as BT.709 and shift colours
    from um import win
    seen = {}
    monkeypatch.setattr(win, "is_wsl", lambda: False)   # under WSL, Recorder calls wslpath through the patched Popen

    class FakePopen:
        def __init__(self, cmd, **kw):
            seen["cmd"] = cmd
    monkeypatch.setattr(win, "ffmpeg_win", lambda *a, **k: "ffmpeg")
    monkeypatch.setattr(win, "encoder", lambda: "libx264")
    monkeypatch.setattr(win.subprocess, "Popen", FakePopen)
    win.Recorder(exe="Game.exe", out=str(tmp_path / "take"), audio=False).start()
    cmd = seen["cmd"]
    assert "out_color_matrix=bt709" in cmd[cmd.index("-vf") + 1]
    assert cmd[cmd.index("-colorspace") + 1] == "bt709" and cmd[cmd.index("-color_range") + 1] == "tv"


def test_auto_hdr_detection(monkeypatch):
    # Auto HDR on an HDR display washes out captures of SDR games; um warns from the registry setting
    from um import win
    prefs = {"DirectXUserGlobalSettings": "AutoHDREnable=0;SwapEffectUpgradeEnable=1;",
             r"E:\Games\Foo\Foo.exe": "AppStatus=1;AutoHDREnable=2097;",
             r"E:\Games\Bar\Bar.exe": "AppStatus=1;AutoHDREnable=2096;"}
    monkeypatch.setattr(win, "_gpu_prefs", lambda: prefs)
    assert win.auto_hdr_on("Foo.exe") and win.auto_hdr_on("foo")
    assert not win.auto_hdr_on("Bar.exe") and not win.auto_hdr_on("Other.exe") and not win.auto_hdr_on()
    prefs["DirectXUserGlobalSettings"] = "AutoHDREnable=1;"
    assert win.auto_hdr_on("Other.exe") and not win.auto_hdr_on("Bar.exe")


def test_slay_the_spire_2_is_not_sts1(tmp_path):
    # StS2 is Godot + C#; the StS1 entry (ModTheSpire, Java) must not match it
    d = tmp_path / "Slay the Spire 2"
    d.mkdir()
    for i in range(6):
        (d / f"f{i}.txt").write_text("x")
    route = scan.scan(str(d))["routes"][0]["route"]
    assert route == scan.KNOWN["slay the spire 2"][0] and "ModTheSpire" not in route


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


@pytest.mark.parametrize("alpha", [1, 64, 128, 192, 254, 255])
@pytest.mark.parametrize("operation", ["fit", "sheet", "squash"])
def test_sprite_placement_preserves_rgba(alpha, operation):
    # Placing a frame on a transparent canvas must not apply its alpha twice.
    im = Image.new("RGBA", (8, 8), (200, 100, 50, alpha))
    if operation == "fit":
        out = sprite.fit(im, 8, 8)
    elif operation == "sheet":
        out = sprite.slice_sheet(sprite.sheet([im]), 8, 8)[0]
    else:
        out = sprite.simple_frames(im, n=1, kind="squash")[0]
    assert out.tobytes() == im.tobytes()


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


def test_upload_uses_cdn_token_and_explains_big_failures(tmp_path, monkeypatch, capsys):
    # storage/upload/initiate?storage_type=gcs now answers 400 "Invalid storage type"; files over 8 MiB then failed silently
    calls = []
    monkeypatch.setattr(fal, "_req", lambda method, url, body=None, **k: calls.append(url) or {"token": "t", "token_type": "Bearer"})

    class Resp:
        def __init__(self, req):
            self.req = req

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"access_url": "https://v3.fal.media/files/x/a.png"}).encode()
    sent = []
    monkeypatch.setattr(fal.urllib.request, "urlopen", lambda req, timeout=None: sent.append(req) or Resp(req))
    f = tmp_path / "a.png"
    f.write_bytes(b"\x89PNG")
    assert fal.upload(f) == "https://v3.fal.media/files/x/a.png"
    assert "storage_type=fal-cdn-v3" in calls[0] and sent[0].full_url == fal.CDN + "/files/upload"
    assert sent[0].get_header("Authorization") == "Bearer t" and sent[0].get_header("X-fal-file-name") == "a.png"

    def fail(req, timeout=None):
        raise fal.urllib.error.URLError("boom")
    monkeypatch.setattr(fal.urllib.request, "urlopen", fail)
    assert fal.upload(f).startswith("data:image/png;base64,")              # small: inline fallback
    big = tmp_path / "big.mp4"
    big.write_bytes(b"\0" * ((8 << 20) + 1))
    with pytest.raises(SystemExit):
        fal.upload(big)
    assert "only covers files under 8 MiB" in capsys.readouterr().err  # big: says why instead of a bare exit 1


def test_failed_download_keeps_the_request_id(tmp_path, monkeypatch, capsys):
    # a finished (paid) job whose output URL 404s must not vanish: say which request to fetch again
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"ok"

    def urlopen(req, timeout=None):
        if req.full_url.endswith("big.mov"):
            raise fal.urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
        return Resp()
    monkeypatch.setattr(fal.urllib.request, "urlopen", urlopen)
    res = {"video": {"url": "https://v3b.fal.media/files/x/big.mov"}, "thumb": {"url": "https://v3b.fal.media/files/x/t.png"},
           "_request_id": "req-123", "_endpoint": "fal-ai/some-model"}
    with pytest.raises(SystemExit):
        fal.download_outputs(res, tmp_path, "clip")
    err = capsys.readouterr().err
    assert "big.mov" in err and "um fal result fal-ai/some-model req-123" in err
    assert (tmp_path / "clip_thumb.png").read_bytes() == b"ok"   # the other outputs still saved


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


@pytest.mark.parametrize("label,key", [
    # assembled at runtime so this file doesn't trip the toolkit's own publish check
    ("OpenAI key", "sk-" + "proj-" + "Ab3_dE-f" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0" * 4),
    ("OpenAI key", "sk-" + "svcacct-" + "Ab3_dE-f" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0" * 4),
    ("OpenAI key", "sk-" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0" * 2),
    ("GitHub token", "github" + "_pat_" + "11ABCDEFG0123456789abc" + "_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5bC7dE9fG1hJ3kL5mN7pQ9rS1t"),
    ("GitHub token", "gh" + "p_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3z"),
])
def test_secret_patterns_catch_current_key_formats(label, key):
    rx = dict(publish.SECRET_PATTERNS)[label]
    assert rx.search(f"key = {key}\n"), key


def test_secret_patterns_ignore_ordinary_text():
    text = "sk-learn-style-kebab-case-identifiers-are-not-keys and github_pat_ alone"
    assert not [label for label, rx in publish.SECRET_PATTERNS if rx.search(text)]


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


def test_kb_impossible_date_is_reported_not_raised(tmp_path):
    # YAML turns an unquoted YYYY-MM-DD into a date; a day that doesn't exist raises ValueError, not YAMLError
    root = tmp_path / "knowledge"
    (root / "techniques").mkdir(parents=True)
    note = root / "techniques" / "t.md"
    note.write_text("---\nkind: technique\ntitle: t\ntags: [x]\ndate: 2026-09-31\nagents: [a]\n---\n# t\n", encoding="utf-8")
    fails, _ = kb.check_note(note, root)
    assert any("front matter is not valid YAML" in f for f in fails), fails   # the date error's wording varies by Python
    kb.search(root, ["t"])                                             # one bad note must not break search or index
    kb.build_index(root)


@pytest.mark.parametrize("url", ["https://github.com/alice/universal-modder.git", "https://github.com/alice/universal-modder",
                                 "git@github.com:alice/universal-modder.git", "ssh://git@github.com/alice/universal-modder.git"])
def test_pr_head_from_fork(url):
    # gh looks a bare --head branch up in the base repo; a PR from a fork needs "<owner>:<branch>"
    assert kb.pr_head("kb/a-b", url) == "alice:kb/a-b"


def test_pr_head_same_repo():
    assert kb.pr_head("kb/a-b", None) == "kb/a-b"


# --------------------------------------------------------------------------- powershell

def test_ps_exe_falls_back_to_full_path(tmp_path, monkeypatch):
    # an agent's PATH often lacks System32\WindowsPowerShell\v1.0; bare "powershell" then raises WinError 2
    from um import common
    exe = tmp_path / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(common, "is_wsl", lambda: False)
    monkeypatch.setattr(common.shutil, "which", lambda name: None)
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    assert common.ps_exe() == str(exe)
    monkeypatch.setattr(common.shutil, "which", lambda name: "/on/path/" + name)
    assert common.ps_exe() == "/on/path/powershell"


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


def test_backup_diff_and_restore_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "_root", lambda name: (tmp_path / "snaps" / name).mkdir(parents=True, exist_ok=True)
                        or tmp_path / "snaps" / name)
    src = tmp_path / "src"
    make(src, {"save.dat": "v1", "sub/cfg.ini": "a=1"})
    backup.create(str(src), name="t")
    (src / "save.dat").write_text("v2")
    (src / "sub" / "cfg.ini").unlink()
    make(src, {"extra.log": "new"})
    d = backup.diff("t", str(src))
    assert (d["changed"], d["removed"], d["added"]) == (["save.dat"], ["sub/cfg.ini"], ["extra.log"])
    with pytest.raises(SystemExit):  # no --yes: report only, touch nothing
        backup.restore("t", str(src))
    assert (src / "save.dat").read_text() == "v2"
    backup.restore("t", str(src), clean=True, yes=True)
    assert (src / "save.dat").read_text() == "v1"
    assert (src / "sub" / "cfg.ini").read_text() == "a=1"
    assert not (src / "extra.log").exists()
    assert backup.snapshots("t-pre-restore")  # the state before the restore was kept


# --------------------------------------------------------------------------- comfy

from um import comfy  # noqa: E402


@pytest.fixture
def fake_comfy():
    """A stand-in for ComfyUI's HTTP API: /system_stats, /models, /object_info, /prompt, /history, /view."""
    import io
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    state = {"prompts": [], "polls": 0, "models_route": True}
    png = io.BytesIO()
    im = Image.new("RGBA", (16, 16), (255, 255, 255, 255))      # a red square on a white background
    im.paste((200, 30, 30, 255), (4, 4, 12, 12))
    im.save(png, "PNG")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body: bytes, code=200, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/system_stats":
                self._send(json.dumps({"system": {"comfyui_version": "0.9.0", "pytorch_version": "2.9.0"},
                                       "devices": [{"name": "fake", "type": "cpu"}]}).encode())
            elif u.path == "/models/checkpoints" and state["models_route"]:
                self._send(json.dumps(["sd15.safetensors", "sdxl_base.safetensors"]).encode())
            elif u.path == "/object_info/CheckpointLoaderSimple":
                spec = ["COMBO", {"options": ["v3.safetensors"]}]
                self._send(json.dumps({"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": spec}}}}).encode())
            elif u.path == "/history/p1":
                state["polls"] += 1                                  # the first poll finds it still running
                done = {"p1": {"status": {"status_str": "success", "completed": True},
                               "outputs": {"9": {"images": [{"filename": "um_00001_.png", "subfolder": "", "type": "output"}]}}}}
                self._send(json.dumps(done if state["polls"] > 1 else {}).encode())
            elif u.path == "/view" and parse_qs(u.query).get("filename") == ["um_00001_.png"]:
                self._send(png.getvalue(), ctype="image/png")
            else:
                self._send(b"404: Not Found", 404, "text/plain")

        def do_POST(self):
            wf = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["prompt"]
            state["prompts"].append(wf)
            if wf.get("4", {}).get("inputs", {}).get("ckpt_name") == "missing.safetensors":
                err = {"error": {"message": "Prompt outputs failed validation", "details": ""},
                       "node_errors": {"4": {"class_type": "CheckpointLoaderSimple", "errors": [
                           {"message": "Value not in list", "details": "ckpt_name: 'missing.safetensors' not in [...]"}]}}}
                self._send(json.dumps(err).encode(), 400)
            else:
                self._send(json.dumps({"prompt_id": "p1", "number": 0, "node_errors": {}}).encode())

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{srv.server_address[1]}"
    yield state
    srv.shutdown()


def test_comfy_image_sprite(fake_comfy, tmp_path, monkeypatch):
    from um import cli
    monkeypatch.setattr(comfy.time, "sleep", lambda s: None)
    out = tmp_path / "gen"
    cli.main(["comfy", "image", "a red potion", "--url", fake_comfy["url"], "--out", str(out), "--seed", "7", "--sprite"])
    wf = fake_comfy["prompts"][-1]
    assert wf["4"]["inputs"]["ckpt_name"] == "sd15.safetensors"               # the first checkpoint listed
    assert (wf["5"]["inputs"]["width"], wf["3"]["inputs"]["seed"]) == (512, 7)  # SD 1.5 size, the given seed
    assert "plain flat white background" in wf["6"]["inputs"]["text"]
    assert Image.open(out / "a_red_potion.png").size == (16, 16)
    cut = Image.open(out / "a_red_potion_cut.png")                           # cut out and trimmed locally
    assert cut.size == (8, 8) and cut.getpixel((0, 0)) == (200, 30, 30, 255)
    rec = json.loads((out / "comfy_manifest.jsonl").read_text().splitlines()[-1])
    assert rec["prompt_id"] == "p1" and rec["seed"] == 7 and rec["workflow"]["9"]["class_type"] == "SaveImage"


def test_comfy_run_set_and_errors(fake_comfy, tmp_path, monkeypatch):
    monkeypatch.setattr(comfy.time, "sleep", lambda s: None)
    wf = comfy.txt2img("x", "sd15.safetensors")
    wf["6"]["_meta"] = {"title": "Positive"}
    (tmp_path / "wf.json").write_text(json.dumps(wf))
    wf = comfy.apply_set(comfy.load_workflow(tmp_path / "wf.json"), ["Positive.text=a v1.5 sword=sharp", "3.seed:=42"])
    assert (wf["6"]["inputs"]["text"], wf["3"]["inputs"]["seed"]) == ("a v1.5 sword=sharp", 42)
    assert [Path(f).name for f in comfy.generate(fake_comfy["url"], wf, tmp_path / "o", "sword")] == ["sword.png"]
    (tmp_path / "ui.json").write_text(json.dumps({"nodes": [], "links": []}))
    with pytest.raises(SystemExit):
        comfy.load_workflow(tmp_path / "ui.json")                            # UI format: needs Export (API)
    with pytest.raises(SystemExit):
        comfy.queue(fake_comfy["url"], comfy.txt2img("x", "missing.safetensors"))   # validation error reported
    fake_comfy["models_route"] = False
    assert comfy.checkpoints(fake_comfy["url"]) == ["v3.safetensors"]        # older servers: /object_info
    assert comfy.status(fake_comfy["url"])["version"] == "0.9.0"


def test_skill_copies_match():
    # .agents/skills and .claude/skills are real copies of skills/ (Windows clones turn symlinks into text files)
    root = Path(__file__).resolve().parents[1]
    def tree(d):
        return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}
    src = tree(root / "skills")
    for copy in (".agents/skills", ".claude/skills"):
        assert not (root / copy).is_symlink(), f"{copy} must be a folder, not a symlink"
        assert tree(root / copy) == src, (f"{copy} differs from skills/: rm -rf .agents/skills .claude/skills && "
                                          "cp -r skills .agents/skills && cp -r skills .claude/skills")
    assert not any((root / d).exists() for d in (".gemini/skills", ".github/skills")), "agents read .agents/skills"


# --------------------------------------------------------------------------- hooks

@pytest.mark.skipif(not shutil.which("cygpath"), reason="Git Bash / MSYS only")
def test_path_hook_writes_a_posix_root(tmp_path):
    # Claude Code passes ${CLAUDE_PLUGIN_ROOT} as C:/...; written as is, bash splits PATH at the drive colon
    import os
    root = tmp_path / "um root"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "um").write_text("#!/bin/sh\n")
    env_file = tmp_path / "env.sh"
    bash = str(Path(shutil.which("cygpath")).with_name("bash.exe"))
    hook = Path(__file__).resolve().parents[1] / "hooks" / "add-to-path.sh"
    subprocess.run([bash, str(hook), root.as_posix()], env={**os.environ, "CLAUDE_ENV_FILE": str(env_file)}, check=True)
    value = env_file.read_text().split('"')[1]
    prefix = value[:value.index("/bin:$PATH")]
    assert prefix.startswith("/") and ":" not in prefix, value
