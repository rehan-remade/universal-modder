"""Offline tests for the pieces that don't need a game, a GPU or a fal key.

    uv run --with pytest pytest -q
"""
import io
import json
import os
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


def _pe(managed=True, arch=0x14C, pad=0, dirs=16):
    # minimal PE (x86 PE32 by default, PE32+ for arch=0x8664), optionally with a CLR header
    # directory entry, padded by `pad` bytes so tests can control file sizes. `dirs` is the
    # declared NumberOfRvaAndSizes; the section table begins right after the declared directories.
    pe = bytearray(1024 + pad)
    pe[0:2] = b"MZ"
    struct.pack_into("<I", pe, 0x3C, 0x80)
    pe[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", pe, 0x84, arch)
    opt = 0x80 + 24
    struct.pack_into("<H", pe, opt, 0x20B if arch == 0x8664 else 0x10B)
    struct.pack_into("<I", pe, opt + (108 if arch == 0x8664 else 92), dirs)
    if managed:
        struct.pack_into("<I", pe, opt + (112 if arch == 0x8664 else 96) + 14 * 8, 0x2000)
    return bytes(pe)


def test_managed_pe(tmp_path):
    p = tmp_path / "Game.exe"
    p.write_bytes(_pe())
    assert scan.pe_info(p) == {"arch": "x86", "managed": True}


def test_short_data_directory_pe_is_not_managed(tmp_path):
    # NumberOfRvaAndSizes may be fewer than 16; the section table then follows, and its
    # bytes must not read as a CLR directory RVA - a native exe took the .NET route (#441).
    # Bytes where the 15th slot would sit are section-table data, deliberately nonzero.
    pe = bytearray(_pe(managed=False, arch=0x8664, dirs=6))
    opt = 0x80 + 24
    struct.pack_into("<I", pe, opt + 112 + 14 * 8, 0xDEADBEEF)  # section bytes, not a CLR RVA
    p = tmp_path / "Game.exe"
    p.write_bytes(bytes(pe))
    assert scan.pe_info(p) == {"arch": "x64", "managed": False}


@pytest.mark.parametrize("bin_dir", ["Win64_Shipping_Client", "Gaming.Desktop.x64_Shipping_Client"])
@pytest.mark.parametrize("name", ["Mount & Blade II Bannerlord", "RenamedGame"])
def test_bannerlord_route_and_live_version(tmp_path, bin_dir, name):
    # Identify the module layout even when the folder is renamed; don't send it to generic .NET/native loaders.
    r = _named_game(tmp_path, name, {
        f"bin/{bin_dir}/Bannerlord.exe": _pe(arch=0x8664),
        f"bin/{bin_dir}/TaleWorlds.MountAndBlade.dll": _pe(arch=0x8664),
        f"bin/{bin_dir}/Version.xml": '<Version><Singleplayer Value="v1.4.8"/></Version>',
        "Modules/Native/SubModule.xml": '<Module><Id value="Native"/></Module>',
    })
    assert r["engine"]["key"] == "bannerlord" and r["engine"]["version"] == "v1.4.8"
    assert r["engine"]["version_file"] == f"bin/{bin_dir.lower()}/version.xml"
    assert r["routes"][0]["route"] == scan.BANNERLORD_ROUTE
    assert r["playbook"].endswith("bannerlord.md") and "modules" in r["mod_folders"]
    assert all(rt["playbook"] == "bannerlord.md" for rt in r["routes"])


@pytest.mark.parametrize("version_xml", [
    None, "<Version>", "<Version><Singleplayer/></Version>",
    '<?xml version="1.0" encoding="not-real"?><Version><Singleplayer Value="v1.4.8"/></Version>',
    '<?xml version="1.0" encoding="UTF-32"?><Version><Singleplayer Value="v1.4.8"/></Version>',
])
def test_bannerlord_missing_or_invalid_version(tmp_path, version_xml):
    files = {
        "bin/Win64_Shipping_Client/TaleWorlds.MountAndBlade.dll": _pe(arch=0x8664),
        "Modules/Native/SubModule.xml": "<Module/>",
    }
    if version_xml is not None:
        files["bin/Win64_Shipping_Client/Version.xml"] = version_xml
    key, det = engine_of(tmp_path, files)
    assert key == "bannerlord" and not det.get("version")


@pytest.mark.parametrize("bin_dir", ["Win64_Shipping_Client", "Gaming.Desktop.x64_Shipping_Client"])
def test_bannerlord_prefers_client_version_over_editor(tmp_path, bin_dir):
    key, det = engine_of(tmp_path, {
        f"bin/{bin_dir}/TaleWorlds.MountAndBlade.dll": _pe(),
        f"bin/{bin_dir}/Version.xml": '<Version><Singleplayer Value="v1.5.4"/></Version>',
        "bin/Win64_Shipping_wEditor/TaleWorlds.MountAndBlade.dll": _pe(),
        "bin/Win64_Shipping_wEditor/Version.xml": '<Version><Singleplayer Value="v1.4.8"/></Version>',
        "Modules/Native/SubModule.xml": "<Module/>",
    })
    assert key == "bannerlord" and det["version"] == "v1.5.4"


@pytest.mark.parametrize("bin_dir", ["Win64_Shipping_Client", "Gaming.Desktop.x64_Shipping_Client"])
def test_bannerlord_ignores_backup_binaries(tmp_path, bin_dir):
    key, det = engine_of(tmp_path, {
        f"bin/{bin_dir}/TaleWorlds.MountAndBlade.dll": _pe(),
        f"bin/{bin_dir}/Version.xml": '<Version><Singleplayer Value="v1.4.8"/></Version>',
        "bin/backup/Win64_Shipping_Client/TaleWorlds.MountAndBlade.dll": _pe(),
        "bin/backup/Win64_Shipping_Client/Version.xml": '<Version><Singleplayer Value="v1.0.0"/></Version>',
        "bin/backup/TaleWorlds.MountAndBlade.dll": _pe(),
        "bin/backup/Version.xml": '<Version><Singleplayer Value="v1.0.0"/></Version>',
        "bin/backup_Win64_Shipping_Client/TaleWorlds.MountAndBlade.dll": _pe(),
        "bin/backup_Win64_Shipping_Client/Version.xml": '<Version><Singleplayer Value="v1.0.0"/></Version>',
        "Modules/Native/SubModule.xml": "<Module/>",
    })
    assert key == "bannerlord" and det["version"] == "v1.4.8"
    assert det["version_file"] == f"bin/{bin_dir.lower()}/version.xml"


def test_copied_taleworlds_dll_is_not_a_bannerlord_install(tmp_path):
    key, _ = engine_of(tmp_path, {
        "Game.exe": _pe(),
        "bin/Win64_Shipping_Client/TaleWorlds.MountAndBlade.dll": _pe(),
    })
    assert key == "dotnet"


@pytest.mark.parametrize("bin_dir", ["backup", "backup_Win64_Shipping_Client", "Debug", "random"])
def test_bannerlord_copies_do_not_override_another_engine(tmp_path, bin_dir):
    key, _ = engine_of(tmp_path, {
        "UnityPlayer.dll": _pe(False),
        "Game_Data/Managed/Assembly-CSharp.dll": _pe(),
        f"bin/{bin_dir}/TaleWorlds.MountAndBlade.dll": _pe(),
        "Modules/Native/SubModule.xml": "<Module/>",
    })
    assert key == "unity-mono"


def test_bannerlord_utf16_version(tmp_path):
    key, det = engine_of(tmp_path, {
        "bin/Win64_Shipping_Client/TaleWorlds.MountAndBlade.dll": _pe(),
        "bin/Win64_Shipping_Client/Version.xml":
            '<?xml version="1.0" encoding="UTF-16"?><Version><Singleplayer Value="v1.4.8"/></Version>'.encode("utf-16"),
        "Modules/Native/SubModule.xml": "<Module/>",
    })
    assert key == "bannerlord" and det["version"] == "v1.4.8"


def test_bannerlord_version_on_the_root_element(tmp_path):
    # the other Version.xml shape builds have shipped: the Value sits on the root element
    key, det = engine_of(tmp_path, {
        "bin/Win64_Shipping_Client/TaleWorlds.MountAndBlade.dll": _pe(),
        "bin/Win64_Shipping_Client/Version.xml": '<Version Value="v1.2.12"/>',
        "Modules/Native/SubModule.xml": "<Module/>",
    })
    assert key == "bannerlord" and det["version"] == "v1.2.12"


@pytest.mark.parametrize("name", ["Mount & Blade II: Bannerlord", "Mount & Blade II Bannerlord", "RenamedGame"])
def test_bannerlord_save_folder_with_its_actual_name(tmp_path, monkeypatch, name):
    # Steam uses '&', while the real Documents folder uses 'and'; a renamed install needs the same hint.
    docs = tmp_path / "Documents"
    saves = docs / "Mount and Blade II Bannerlord" / "Game Saves"
    saves.mkdir(parents=True)
    monkeypatch.setattr(scan, "win_folders", lambda: {"documents": str(docs)})
    root = tmp_path / "install"
    # A store title can contain ':' on Windows; keep it in metadata rather than the folder name.
    monkeypatch.setattr(scan, "resolve_game", lambda query: dict(name=name, path=str(root)))
    make(root, {
        "bin/Win64_Shipping_Client/TaleWorlds.MountAndBlade.dll": _pe(),
        "Modules/Native/SubModule.xml": "<Module/>",
    })
    r = scan.scan(str(root))
    assert str(saves.parent) in r["saves"]


def test_other_engines_do_not_report_a_generic_modules_folder_as_mods(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "all_games", lambda: [])
    r = _named_game(tmp_path, "OtherGame", {
        "UnityPlayer.dll": _pe(False),
        "Game_Data/Managed/Assembly-CSharp.dll": _pe(),
        "Modules/Tool/helper.dll": _pe(),
    })
    assert "modules" not in r["mod_folders"]


def test_zengin_detected(tmp_path):
    key, _ = engine_of(tmp_path, {"system/Gothic2.exe": _pe(False), "Data/Textures.vdf": b"x"})
    assert key == "zengin"
    # volume layout alone (vdfs loader + Data/*.vdf) is enough
    key, _ = engine_of(tmp_path / "b", {"system/vdfs32g.dll": _pe(False), "Data/Worlds.vdf": b"x"})
    assert key == "zengin"


@pytest.mark.parametrize("files", [
    {"DDDA.exe": _pe(False), "nativePC/rom/game_main.arc": b"ARC\x00"},              # Dragon's Dogma: Dark Arisen
    {"RE5DX9.exe": _pe(False), "nativePC_MT/Image/Archive/s506.arc": b"ARC\x00"},    # Resident Evil 5
    {"DevilMayCry4SpecialEdition.exe": _pe(False), "nativeDX10/rom/player/costume.arc": b"ARC\x00"},
    {"DeadRising.exe": _pe(False, arch=0x8664), "nativeWin64/rom/ui.arc": b"ARC\x00"},
])
def test_mt_framework_detected(tmp_path, files):
    # the native* folder is named per port; the .arc archives under it are the signature
    key, _ = engine_of(tmp_path, files)
    assert key == "mt-framework"


def test_re_engine_natives_is_not_mt_framework(tmp_path):
    make(tmp_path, {"re2.exe": _pe(False, arch=0x8664), "re_chunk_000.pak": b"KPKA",
                    "natives/STM/streaming/x.tex.10": b"x"})
    hits, _ = scan.detect(scan.Index(tmp_path))
    assert hits[0][0] == "re-engine" and all(k != "mt-framework" for k, *_ in hits)


@pytest.mark.parametrize("files", [
    # Unleashed Recompiled: the installer copies the raw Xbox 360 files into game/ (split .ar + .arl lists)
    {"UnleashedRecomp.exe": _pe(False, arch=0x8664), "game/#ActD_Africa.ar.00": b"x", "game/#ActD_Africa.arl": b"x",
     "update/default.xexp": b"x", "patched/default.xex": b"x"},
    # Sonic Generations (Steam): the .ar archives live inside CRI .cpk packfiles, so only the exe tells
    {"SonicGenerations.exe": _pe(False), "disk/bb.cpk": b"CPK "},
    # Sonic Forces (HE2): the exe sits deep under build/
    {"build/main/projects/exec/Sonic Forces.exe": _pe(False, arch=0x8664)},
])
def test_hedgehog_detected(tmp_path, files):
    key, _ = engine_of(tmp_path, files)
    assert key == "hedgehog"


def test_lone_ar_archive_is_not_hedgehog(tmp_path):
    make(tmp_path, {"Game.exe": _pe(False), "lib/libgame.ar": b"!<arch>\n"})
    hits, _ = scan.detect(scan.Index(tmp_path))
    assert all(k != "hedgehog" for k, *_ in hits)


def test_blackrock_detected(tmp_path):
    # Split/Second layout: .shaderinst + .model assets, .ark level packs
    key, _ = engine_of(tmp_path, {"SplitSecond.exe": _pe(False),
                                  "data/docks.ark": b"x",
                                  "data/ve/car.model": b"x",
                                  "data/ve/car.shaderinst": b"x"})
    assert key == "blackrock"


def test_nested_exe_fingerprinted(tmp_path):
    # Gothic-style layout: the game exe lives one level down in system/
    make(tmp_path, {"system/Gothic2.exe": _pe(managed=False), "Data/worlds.vdf": b"x"})
    _, facts = scan.detect(scan.Index(tmp_path))
    assert facts["executables"]["system/gothic2.exe"] == {"arch": "x86", "managed": False}


def test_redist_exes_skipped(tmp_path):
    # installer/runtime folders (Steam _CommonRedist, GOG __redist/__support, EA __installer) and
    # uninstallers at any depth are not the game
    make(tmp_path, {"Game.exe": _pe(False), "_CommonRedist/vcredist/vc_redist.exe": _pe(False),
                    "__redist/dotnet/setup.exe": _pe(), "__support/app/helper.exe": _pe(),
                    "__installer/Touchup.exe": _pe(), "system/unins000.exe": _pe(),
                    "system/Gothic2.exe": _pe(False)})
    _, facts = scan.detect(scan.Index(tmp_path))
    assert list(facts["executables"]) == ["game.exe", "system/gothic2.exe"]
    assert scan._in_skip_dir("__redist/x.jar") and scan._in_skip_dir("a/_commonredist/b/x.exe")
    assert not scan._in_skip_dir("supporters/x.exe") and not scan._in_skip_dir("__redist.exe")


def _named_game(tmp_path, name, files):
    d = tmp_path / name
    make(d, dict({f"f{i}.txt": "x" for i in range(6)}, **files))
    return scan.scan(str(d))


def test_zengin_route_only_for_classic_gothic(tmp_path):
    # classic Gothic 1/2 get the ZenGin playbook from detection, with the exe-build check in the route
    r = _named_game(tmp_path, "Gothic II", {"system/Gothic2.exe": _pe(False), "Data/Worlds.vdf": b"x"})
    assert r["engine"]["key"] == "zengin" and r["playbook"].endswith("zengin.md")
    assert "exe build" in r["routes"][0]["route"]
    # Gothic 1 Remake (UE5) and Gothic III (Genome) contain "gothic 1"/"gothic ii" but aren't ZenGin
    for name, files in (("Gothic 1 Remake", {"Gothic1Remake/Content/Paks/a.pak": b"x"}),
                        ("Gothic III", {"Gothic3.exe": _pe(False), "Data/a.pak": b"x"})):
        r = _named_game(tmp_path, name, files)
        assert all(rt["playbook"] != "zengin.md" for rt in r["routes"]), name
        assert not r["playbook"].endswith("zengin.md"), name


def test_deep_tooling_jars_not_java_engine(tmp_path):
    # a Ghidra/SDK tree inside the game folder must not mislabel a native game as Java
    make(tmp_path, {"Game.exe": _pe(False),
                    "Dev Folder/tools/thirdparty/ghidra/support/launchsupport.jar": b"x",
                    "Dev Folder/tools/thirdparty/ghidra/gradle/gradle-wrapper.jar": b"x"})
    hits, _ = scan.detect(scan.Index(tmp_path))
    assert all(k != "java" for k, *_ in hits)
    # but a jar where the game ships it (root / one level down) still detects
    key, _ = engine_of(tmp_path / "b", {"game.jar": b"x", "jre/bin/java.exe": _pe(False)})
    assert key == "java"


def test_unicode_output_on_cp1252_console(tmp_path):
    # `um kb show` must not UnicodeEncodeError when stdout isn't UTF-8
    kb = tmp_path / "kb"
    (kb / "games/x").mkdir(parents=True)
    (kb / "games/x/n.md").write_text("---\ntitle: LÖVE → test\n---\n# LÖVE →\n", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="cp1252", UM_KB=str(kb),
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    r = subprocess.run([sys.executable, "-m", "um", "kb", "show", "n.md"],
                       capture_output=True, encoding="utf-8", env=env)
    assert r.returncode == 0 and "LÖVE →" in r.stdout


def test_cli_prints_text_a_legacy_console_cannot_encode(tmp_path, monkeypatch):
    # a Windows console defaults to cp1252, which has no "≥" or "→"; a note can hold anything
    root = tmp_path / "knowledge" / "games" / "x"
    root.mkdir(parents=True)
    (root / "a.md").write_text("---\nkind: game\ntitle: Boon\ngame: X\n---\n# Boon\n\nThe boon pool ≥ 3 → cached\n",
                               encoding="utf-8")
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)
    from um import cli
    cli.main(["kb", "search", "boon", "--root", str(tmp_path / "knowledge")])
    console.flush()
    assert "The boon pool ≥ 3 → cached" in raw.getvalue().decode("utf-8")


def test_tool_exe_does_not_set_dotnet_engine(tmp_path):
    # Kenshi shape: the only managed binary is a tool (Forgotten Construction
    # Set); the big game binary is native, so the engine must not be dotnet.
    # The mod manager bundle is deliberately bigger than the game exe: size
    # alone must not elect it as the game binary.
    make(tmp_path, {
        "kenshi_x64.exe": _pe(False, arch=0x8664, pad=40000),
        "forgotten construction set.exe": _pe(),
        "KenshiModTool.exe": _pe(False, arch=0x8664, pad=90000),
        "OgreMain_x64.dll": b"MZ",
        "Plugins_x64.cfg": "Plugin=RE_Kenshi",
    })
    hits, facts = scan.detect(scan.Index(tmp_path))
    assert hits[0][0] == "native"
    assert hits[0][2][0] == "kenshi_x64.exe"
    assert facts["executables"]["kenshi_x64.exe"] == {"arch": "x64", "managed": False}


def test_managed_game_exe_still_dotnet(tmp_path):
    # guard: a game whose own binary is managed keeps the dotnet engine even
    # when a tool-like launcher ships next to it
    assert engine_of(tmp_path, {
        "Game.exe": _pe(),
        "GameLauncher.exe": _pe(),
    })[0] == "dotnet"


def test_dotnet_apphost_game_exe_still_dotnet(tmp_path):
    # .NET 5+ shape: Game.exe is a native apphost next to Game.dll + Game.runtimeconfig.json,
    # so a small managed launcher must not demote the game to native
    key, _ = engine_of(tmp_path, {
        "Game.exe": _pe(False, arch=0x8664, pad=40000),
        "Game.dll": _pe(arch=0x8664),
        "Game.runtimeconfig.json": "{}",
        "Launcher.exe": _pe(),
    })
    assert key == "dotnet"


def test_tool_like_native_exe_never_game_binary(tmp_path):
    # when every native exe is tool-like there is no game binary to prefer: stay dotnet
    # rather than electing setup.exe
    make(tmp_path, {"Editor.exe": _pe(), "setup.exe": _pe(False, pad=40000)})
    hits, _ = scan.detect(scan.Index(tmp_path))
    assert hits[0][0] == "dotnet"
    assert all("setup.exe" not in ev for _, _, ev, _ in hits)


def test_kenshi_loaders_and_route(tmp_path):
    d = tmp_path / "Kenshi"
    make(d, {
        "kenshi_x64.exe": _pe(False, arch=0x8664, pad=40000),
        "forgotten construction set.exe": _pe(),
        "OgreMain_x64.dll": b"MZ",
        "RE_Kenshi.dll": b"MZ", "KenshiLib.dll": b"MZ",
        "KenshiModTool.exe": _pe(False, arch=0x8664, pad=100),
        "mods/readme.txt": "x",
    })
    r = scan.scan(str(d))
    assert r["engine"]["key"] == "native"
    assert "RE_Kenshi (Kenshi OGRE plugin)" in r["mod_loaders_installed"]
    assert "Kenshi Mod Manager" in r["mod_loaders_installed"]
    assert r["routes"][0]["why"] == "known game" and r["routes"][0]["playbook"] == "native.md"
    # a generic root masterlist.json is not a Kenshi Mod Manager install
    make(tmp_path / "Other", {"Game.exe": _pe(False), "masterlist.json": "[]"})
    assert "Kenshi Mod Manager" not in scan.scan(str(tmp_path / "Other"))["mod_loaders_installed"]


@pytest.mark.parametrize("name", ["Dwarf Fortress", "df_53_16"])
def test_dwarf_fortress_route_and_dfhack(tmp_path, name):
    # DF is native with no engine signature: the raws route must outrank the proxy-DLL one, also in a renamed folder
    r = _named_game(tmp_path, name, {"dwarfort": b"\x7fELF", "data/vanilla/vanilla_creatures_graphics/info.txt": "[ID:x]",
                                     "libdfhooks_dfhack.so": b"\x7fELF"})
    assert r["routes"][0]["route"] == scan.KNOWN["dwarf fortress"][0] and r["routes"][0]["why"] == "known game"
    assert "DFHack" in r["mod_loaders_installed"]


@pytest.mark.parametrize("name", ["Mindustry", "mdt"])
def test_mindustry_route(tmp_path, name):
    # the packaged game (Mindustry.exe + jre/desktop.jar) scans as Java; its own mod API comes first, not jar patching
    r = _named_game(tmp_path, name, {"Mindustry.exe": _pe(False), "Mindustry.json": "{}", "jre/desktop.jar": b"PK"})
    assert r["engine"]["key"] == "java"
    assert r["routes"][0]["route"] == scan.KNOWN["mindustry"][0] and "mod.hjson" in r["routes"][0]["route"]
    assert all(rt["route"] != scan.ENGINES["java"][2] for rt in r["routes"])


@pytest.mark.parametrize("name", ["The Binding of Isaac Rebirth", "isaac"])
def test_isaac_route(tmp_path, name):
    # the Steam folder has no colon, so the Lua route must come from isaac-ng.exe, ahead of the native proxy-DLL one
    r = _named_game(tmp_path, name, {"isaac-ng.exe": _pe(False), "resources/packed/graphics.a": b"x"})
    assert r["routes"][0]["route"] == scan.KNOWN["the binding of isaac: rebirth"][0]
    assert r["routes"][0]["playbook"] == "isaac.md" and r["routes"][0]["why"] == "known game"


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


def test_online_only_matches_whole_names():
    # a substring test told agents to stop on single-player games: Rusty Lake ("rust"), Battlefield 1942, MW2 (2009)
    for offline in ["Rusty Lake Paradise", "Rusted Warfare", "Battlefield 1942", "Call of Duty: Modern Warfare 2 (2009)",
                    "Deadlock: Planetary Conquest", "The Final Station", "Trusty Rusty"]:
        assert scan.online_only(offline) is None, offline
    for online in ["Rust", "Counter-Strike 2", "Call of Duty®", "Tom Clancy's Rainbow Six® Siege", "PUBG: BATTLEGROUNDS",
                   "Overwatch® 2", "Deadlock", "NARAKA: BLADEPOINT"]:
        assert scan.online_only(online), online


def test_scan_warns_only_for_online_games(tmp_path):
    for name, warned in [("Rust", True), ("Rusty Lake Paradise", False)]:
        d = tmp_path / name
        d.mkdir()
        for i in range(6):
            (d / f"f{i}.txt").write_text("x")
        assert any("online competitive" in w for w in scan.scan(str(d))["warnings"]) == warned, name


def _fake_host(monkeypatch, os_name, machine, wsl=False):
    import platform
    monkeypatch.setattr(scan, "is_mac", lambda: os_name == "macos")
    monkeypatch.setattr(scan, "is_windows", lambda: os_name == "windows")
    monkeypatch.setattr(scan, "is_wsl", lambda: wsl)
    monkeypatch.setattr(platform, "machine", lambda: machine)


def test_host_info_names_the_cpu_like_the_exes(monkeypatch):
    # the host's `arch` must compare directly with an exe's `arch` in the report (x86, x64, arm64)
    for machine, arch in [("x86_64", "x64"), ("AMD64", "x64"), ("arm64", "arm64"), ("aarch64", "arm64"),
                          ("i386", "x86"), ("i686", "x86"), ("riscv64", "riscv64")]:
        _fake_host(monkeypatch, "linux", machine)
        assert scan.host_info()["arch"] == arch, machine


def test_host_info_per_os_and_wsl(monkeypatch):
    import platform
    _fake_host(monkeypatch, "macos", "arm64")
    monkeypatch.setattr(platform, "mac_ver", lambda: ("26.5.1", ("", "", ""), "arm64"))
    h = scan.host_info()
    assert h == dict(os="macos", os_version="26.5.1", arch="arm64", wsl=False, translated=False)
    assert scan.host_line(h) == "macOS 26.5.1, arm64"

    _fake_host(monkeypatch, "windows", "AMD64")
    monkeypatch.setattr(platform, "version", lambda: "10.0.26100")
    h = scan.host_info()
    assert (h["os"], h["arch"], h["wsl"]) == ("windows", "x64", False)
    assert scan.host_line(h) == "Windows 10.0.26100, x64"

    _fake_host(monkeypatch, "linux", "x86_64")
    monkeypatch.setattr(platform, "freedesktop_os_release", lambda: {"PRETTY_NAME": "Ubuntu 24.04.1 LTS"})
    assert scan.host_line(scan.host_info()) == "Ubuntu 24.04.1 LTS, x64"
    monkeypatch.setattr(platform, "freedesktop_os_release", lambda: (_ for _ in ()).throw(OSError("no os-release")))
    monkeypatch.setattr(platform, "release", lambda: "6.8.0")
    assert scan.host_line(scan.host_info()) == "Linux 6.8.0, x64"

    # WSL is Linux to Python but a Windows host for games: the line must say so, and never suggest Proton territory
    _fake_host(monkeypatch, "linux", "x86_64", wsl=True)
    monkeypatch.setattr(platform, "freedesktop_os_release", lambda: {"PRETTY_NAME": "Ubuntu 22.04.5 LTS"})
    h = scan.host_info()
    assert h["wsl"] is True and scan.host_line(h) == "Windows via WSL (Ubuntu 22.04.5 LTS), x64"


def test_host_info_sees_through_rosetta(monkeypatch):
    import platform
    import subprocess
    monkeypatch.setattr(platform, "mac_ver", lambda: ("26.5.1", ("", "", ""), "x86_64"))

    def sysctl(out=None, error=None):
        def run(*a, **k):
            if error:
                raise error
            return subprocess.CompletedProcess(a, 0, stdout=out, stderr="")
        return run

    _fake_host(monkeypatch, "macos", "x86_64")
    monkeypatch.setattr(scan.subprocess, "run", sysctl("1\n"))
    h = scan.host_info()                      # x86_64 Python translated on an Apple Silicon Mac
    assert h["arch"] == "arm64" and h["translated"] is True
    assert scan.host_line(h) == "macOS 26.5.1, arm64 (Python runs under Rosetta)"
    for out, error in [("0\n", None), ("", None), (None, OSError("no sysctl"))]:   # a real Intel Mac, or no answer
        monkeypatch.setattr(scan.subprocess, "run", sysctl(out, error))
        h = scan.host_info()
        assert h["arch"] == "x64" and h["translated"] is False


def test_scan_report_starts_with_the_host(tmp_path):
    d = tmp_path / "Some Game"
    d.mkdir()
    for i in range(6):
        (d / f"f{i}.txt").write_text("x")
    r = scan.scan(str(d))
    assert set(r["host"]) == {"os", "os_version", "arch", "wsl", "translated"}   # the same keys on every host
    assert json.loads(json.dumps(r))["host"] == r["host"]           # machine-readable for agents
    lines = scan.format_report(r).splitlines()
    assert lines[1].startswith("  path:") and lines[2].startswith("  host:      ")


def test_scan_warns_when_windows_exes_meet_a_non_windows_host(tmp_path, monkeypatch):
    def folder(name, exe):
        d = tmp_path / name
        d.mkdir()
        for i in range(6):
            (d / f"f{i}.txt").write_text("x")
        (d / "game.exe" if exe else d / "game.x86_64").write_bytes(_pe(managed=False, arch=0x8664) if exe else b"\x7fELF")
        return d

    def host(os_name, wsl=False):
        return dict(os=os_name, os_version="1.2", arch="arm64", wsl=wsl, translated=False)

    def warning(h, d):
        monkeypatch.setattr(scan, "host_info", lambda: h)
        return next((w for w in scan.scan(str(d))["warnings"] if "not native" in w), None)

    pe, native = folder("Windows build", True), folder("Native build", False)
    for h in (host("macos"), host("linux")):
        w = warning(h, pe)
        assert w and scan.host_line(h) in w and "compatibility.md" in w, h       # one line, naming the host and where to read
        assert "\n" not in w
    assert warning(host("windows"), pe) is None
    assert warning(host("linux", wsl=True), pe) is None                          # WSL counts as Windows
    assert warning(host("macos"), native) is None                                # no PE exes: no claim


def test_ffmpeg_download_is_checksummed(tmp_path, monkeypatch):
    import hashlib, io
    from um import win
    payload = b"PK fake ffmpeg zip"
    good = hashlib.sha256(payload).hexdigest()
    sums = f"{'0' * 64}  ffmpeg-other.zip\n{good}  ffmpeg-master-latest-win64-gpl.zip\n".encode()
    monkeypatch.delenv("UM_FFMPEG_SHA256", raising=False)
    monkeypatch.setattr(win.urllib.request, "urlopen", lambda url, timeout=None: io.BytesIO(sums))
    assert win.ffmpeg_sha256() == good
    monkeypatch.setattr(win.urllib.request, "urlretrieve", lambda url, dst: Path(dst).write_bytes(payload))
    z = tmp_path / "ffmpeg.zip"
    win.download_ffmpeg(z)
    assert z.read_bytes() == payload
    monkeypatch.setenv("UM_FFMPEG_SHA256", "ab" * 32)        # a pin wins over the published sum
    with pytest.raises(SystemExit):
        win.download_ffmpeg(z)
    assert not z.exists()                                      # a bad download is deleted, never extracted


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


def test_publish_check_mod_inside_game(tmp_path, capsys):
    # a Dwarf Fortress mod in <install>/mods/<name> matched itself: every file "game file copied verbatim"
    game, mod = tmp_path / "game", tmp_path / "game" / "mods" / "mine"
    make(game, {"data/big.bin": b"x" * 4096, "mods/mine/README.md": "My mod", "mods/mine/graphics/page.png": b"y" * 4096})
    assert publish.check(str(mod), str(game)) == 0
    (mod / "copied.bin").write_bytes(b"x" * 4096)
    assert publish.check(str(mod), str(game)) == 1
    out = capsys.readouterr().out
    assert "copied.bin" in out and "page.png" not in out


def test_publish_check_mod_installed_in_loader_folder(tmp_path, capsys):
    # a UMM mod repo installed to <game>/Mods/<Id>/ (and a BepInEx build in plugins/<dll>/) matched its own copy
    info = '{"Id": "N7MassEffect", "AssemblyName": "N7MassEffect.dll"}'
    make(tmp_path / "mod", {"src/N7/Info.json": info + " " * 64, "src/N7/Assets/n7.png": b"i" * 4096,
                            "src/N7/bin/N7MassEffect.dll": b"d" * 4096, "README.md": "My mod"})
    make(tmp_path / "game", {"Data/big.bin": b"x" * 4096, "Mods/N7MassEffect/Info.json": info + " " * 64,
                             "Mods/N7MassEffect/Assets/n7.png": b"i" * 4096,
                             "BepInEx/plugins/N7MassEffect/N7MassEffect.dll": b"d" * 4096,
                             "Mods/SomeoneElse/theirs.bin": b"z" * 4096})
    assert publish.check(str(tmp_path / "mod"), str(tmp_path / "game")) == 0
    # genuine game files still fail, including another mod's files under Mods/
    (tmp_path / "mod" / "copied.bin").write_bytes(b"x" * 4096)
    (tmp_path / "mod" / "theirs.bin").write_bytes(b"z" * 4096)
    assert publish.check(str(tmp_path / "mod"), str(tmp_path / "game")) == 1
    out = capsys.readouterr().out.replace("\\", "/")
    assert "copied.bin" in out and "Mods/SomeoneElse/theirs.bin" in out and "n7.png" not in out and "N7MassEffect.dll" not in out
    assert "not compared, this mod's own installed copy: BepInEx/plugins/N7MassEffect/, Mods/N7MassEffect/" in out


def test_publish_check_own_installed_copy_is_named_by_metadata_only(tmp_path, capsys):
    # only the mod's own metadata names its installed folder; a DLL it merely bundles doesn't
    csproj = "<Project><PropertyGroup><AssemblyName>N7</AssemblyName></PropertyGroup></Project>"
    make(tmp_path / "mod", {"README.md": "My mod", "src/N7Plugin.csproj": csproj, "bin/N7.dll": b"n" * 4096,
                            "lib/ModMenu.dll": b"m" * 4096, "lib/Foo.dll": b"f" * 4096,
                            "lib/Assembly-CSharp.dll": b"g" * 4096})
    make(tmp_path / "game", {"BepInEx/plugins/N7.dll": b"n" * 4096,         # this mod, flat in plugins/
                             "BepInEx/plugins/N7/N7.dll": b"n" * 4096,      # this mod, in its own folder
                             "Mods/ModMenu/ModMenu.dll": b"m" * 4096,       # another mod it references
                             "Mods/Foo/Foo.dll": b"f" * 4096,               # a folder the game ships under Mods/
                             "Game_Data/Managed/Assembly-CSharp.dll": b"g" * 4096,
                             "BepInEx/plugins/N7/Assembly-CSharp.dll": b"g" * 4096})   # copied in by the build
    assert publish.check(str(tmp_path / "mod"), str(tmp_path / "game")) == 1
    out = capsys.readouterr().out.replace("\\", "/")
    fails = [ln for ln in out.splitlines() if ln.startswith("FAIL ")]
    assert len(fails) == 3 and not any("bin/N7.dll" in ln for ln in fails)
    assert "lib/ModMenu.dll  (== Mods/ModMenu/ModMenu.dll)" in out and "lib/Foo.dll  (== Mods/Foo/Foo.dll)" in out
    assert "lib/Assembly-CSharp.dll  (== Game_Data/Managed/Assembly-CSharp.dll)" in out
    assert publish._own_names([tmp_path / "mod" / "src/N7Plugin.csproj"]) == {"n7"}


@pytest.mark.parametrize("label,key", [
    # assembled at runtime so this file doesn't trip the toolkit's own publish check
    ("OpenAI key", "sk-" + "proj-" + "Ab3_dE-f" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0" * 4),
    ("OpenAI key", "sk-" + "svcacct-" + "Ab3_dE-f" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0" * 4),
    ("OpenAI key", "sk-" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0" * 2),
    ("GitHub token", "github" + "_pat_" + "11ABCDEFG0123456789abc" + "_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5bC7dE9fG1hJ3kL5mN7pQ9rS1t"),
    ("GitHub token", "gh" + "p_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3z"),
    ("Sprixen key", "spx_" + "live_" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0" * 2),
    ("Voidless key", "VOIDLESS_API_KEY=" + "void_" + "Gh1jK2lM3nO4pQ5rS6tU7vW8xY9z0"),
])
def test_secret_patterns_catch_current_key_formats(label, key):
    rx = dict(publish.SECRET_PATTERNS)[label]
    assert rx.search(f"key = {key}\n"), key


def test_secret_patterns_ignore_ordinary_text():
    text = ("sk-" + "learn-style-kebab-case-identifiers-are-not-keys and github_pat_ alone, "
            "static void " + "void_" + "callback_handler_with_a_long_descriptive_name(void);")
    assert not [label for label, rx in publish.SECRET_PATTERNS if rx.search(text)]


def test_video_theme_font_override(tmp_path):
    # Space Grotesk is Latin-only: an EDL theme's title_font replaces it, e.g. for Cyrillic titles
    video.FONT_OVERRIDES[video.TITLE_FONT] = str(video.MONO_FONT)
    try:
        assert video._font(video.TITLE_FONT, 20).path == str(video.MONO_FONT)
        video.hook_text("Привет, мир", 640, 360, {}, tmp_path / "hook.png")
        assert (tmp_path / "hook.png").exists()
    finally:
        video.FONT_OVERRIDES.clear()
    assert video._font(video.TITLE_FONT, 20).path == str(video.TITLE_FONT)


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


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_compile_preview_keeps_size_even(tmp_path):
    # 4:5 portrait: half of 1080x1350 is 540x675, and libx264 refuses an odd height in yuv420p
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1350:d=2:r=30", "-f", "lavfi", "-i", "sine=f=440:d=2",
                    "-shortest", str(tmp_path / "c.mp4")], check=True)
    edl = {"size": [1080, 1350], "fps": 30, "segments": [{"clip": "c.mp4", "dur": 1.0}, {"card": {"title": "The end"}, "dur": 1.0}]}
    (tmp_path / "edl.json").write_text(json.dumps(edl))
    video.compile_edl(tmp_path / "edl.json", str(tmp_path / "out.mp4"), preview=True)
    info = video.probe(tmp_path / "out.mp4")
    assert (info["width"], info["height"]) == (540, 674)

    (tmp_path / "edl.json").write_text(json.dumps(dict(edl, size=[1080, 1351])))
    with pytest.raises(SystemExit):
        video.compile_edl(tmp_path / "edl.json", str(tmp_path / "odd.mp4"))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_compile_cut_then_fade(tmp_path, monkeypatch):
    # a cut then a fade: xfade's first input is concat's output (AVTB), so every join input must end at AVTB.
    # FFmpeg 7.0/7.1's setpts marks the frame rate unknown (1/0), which xfade refuses, so each join input also
    # declares fps=. Newer FFmpeg passes without it, hence the graph check.
    calls, real_ff = [], video.ff

    def spy(*args, **kw):
        calls.append([str(a) for a in args])
        return real_ff(*args, **kw)

    monkeypatch.setattr(video, "ff", spy)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:d=2:r=24", "-f", "lavfi", "-i", "sine=f=440:d=2",
                    "-shortest", str(tmp_path / "c.mp4")], check=True)
    edl = {"size": [640, 360], "fps": 24, "transition": {"type": "cut"},
           "segments": [{"clip": "c.mp4", "dur": 1.0}, {"clip": "c.mp4", "in": 0.5, "dur": 1.0},
                        {"card": {"title": "The end"}, "dur": 1.0, "transition": {"type": "fade", "duration": 0.25}}]}
    (tmp_path / "edl.json").write_text(json.dumps(edl))
    video.compile_edl(tmp_path / "edl.json", str(tmp_path / "out.mp4"))
    graph = calls[-1][calls[-1].index("-filter_complex") + 1].split(";")
    assert all(any(g.startswith(f"[{k}:v]") and "fps=24" in g for g in graph) for k in range(3))
    assert abs(video.probe(tmp_path / "out.mp4")["duration"] - (1 + 1 + 1 - 0.25)) < 0.15


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


def test_kb_search_matches_word_starts(tmp_path):
    root = tmp_path / "knowledge" / "games" / "x"
    root.mkdir(parents=True)
    for name, title in [("a.md", "Trust and frustum culling"), ("b.md", "A Rust server plugin"), ("c.md", "Rusty Lake puzzles"),
                        ("d.md", "Patching plugin.esp")]:
        (root / name).write_text(f"---\nkind: game\ntitle: {title}\ngame: X\n---\n# {title}\n", encoding="utf-8")
    found = {r["title"] for r in kb.search(tmp_path / "knowledge", ["rust"])}
    assert found == {"A Rust server plugin", "Rusty Lake puzzles"}
    assert [r["title"] for r in kb.search(tmp_path / "knowledge", [".esp"])] == ["Patching plugin.esp"]   # punctuation-led terms match anywhere


def test_kb_check_warns_on_links_to_missing_notes(tmp_path):
    root = tmp_path / "knowledge"
    (root / "techniques").mkdir(parents=True)
    (root / "games" / "x").mkdir(parents=True)
    (root / "games" / "x" / "real.md").write_text("---\nkind: game\ntitle: Real\ngame: X\n---\n# Real\n", encoding="utf-8")
    note = root / "techniques" / "t.md"
    head = "---\nkind: technique\ntitle: t\ntags: [x]\ndate: 2026-10-10\nagents: [a]\n---\n# t\n"
    note.write_text(head + "See [real](../games/x/real.md), [its setup](../games/x/real.md#setup), "
                    "[a doc](https://example.com/docs/gone.md), `games/x/real.md` and `knowledge/games/x/real.md`.\n",
                    encoding="utf-8")
    _, warns = kb.check_note(note, root)
    assert not [w for w in warns if "does not exist" in w]
    note.write_text(head + "See [gone](../games/x/gone.md), [gone too](../games/x/gone.md#setup), "
                    "[root-relative](games/x/real.md) and `techniques/missing.md`.\n", encoding="utf-8")
    _, warns = kb.check_note(note, root)
    assert sum("does not exist" in w for w in warns) == 4
    # a note linking to the note next to it
    sib = root / "games" / "x" / "sib.md"
    sib.write_text(head + "Next to [real](real.md) and [gone](./gone.md).\n", encoding="utf-8")
    _, warns = kb.check_note(sib, root)
    assert [w for w in warns if "does not exist" in w] == [
        "link to a note that does not exist: ./gone.md (links are relative to this note's folder; "
        "if the file lives in another repo, link to it on GitHub instead)"]


def test_kb_check_counts_numbered_gotchas_written_as_subheadings(tmp_path):
    note = tmp_path / "n.md"
    head = ("---\nkind: game\ntitle: t\ngame: X\nengine: unity-mono\nroute: managed-patch\nstatus: working\n"
            "date: 2026-10-21\nagents: [a]\n---\n# t\n")
    note.write_text(head + "\n## Gotchas\n\n1. **Symptom.** **Cause:** **Fix:**\n", encoding="utf-8")
    _, warns = kb.check_note(note)
    assert not [w for w in warns if "Gotchas" in w]
    # a numbered subheading is a numbered item too
    note.write_text(head + "\n## Gotchas\n\n### 1. Symptom\n\nCause and fix.\n", encoding="utf-8")
    _, warns = kb.check_note(note)
    assert not [w for w in warns if "Gotchas" in w]
    # an unnumbered list still warns
    note.write_text(head + "\n## Gotchas\n\n- Symptom, cause, fix.\n", encoding="utf-8")
    _, warns = kb.check_note(note)
    assert [w for w in warns if "Gotchas" in w] == ["Gotchas section has no numbered items"]


def test_kb_check_rejects_secrets_and_dumps(tmp_path):
    note = tmp_path / "n.md"
    code = "\n".join(f"int x{i} = {i};" for i in range(160))
    note.write_text("---\nkind: technique\ntitle: t\ntags: [x]\ndate: 2026-09-30\nagents: [a]\n---\n# t\n"
                    f"```c\n{code}\n```\n" + "FAL" + "_KEY=abcdefghijklmnopqrstuvwxyz0123\n")
    fails, _ = kb.check_note(note)
    assert any("code block" in f for f in fails) and any("FAL_KEY" in f for f in fails)


def test_kb_without_pyyaml_says_what_to_install(tmp_path, monkeypatch, capsys):
    # run from a clone without `pip install -e .`: a hint, not a ModuleNotFoundError traceback
    note = tmp_path / "n.md"
    note.write_text("---\ntitle: t\n---\n# t\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "yaml", None)
    with pytest.raises(SystemExit):
        kb.parse(note)
    assert "pip install pyyaml" in capsys.readouterr().err


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


def test_kb_check_rejects_unquoted_list_items(tmp_path):
    # YAML reads `[Cataclysm: Dark Days Ahead]` as a dict and `2004` as an int, and splits `Python (a, b)` on the comma;
    # the dict reached the index as "{'Cataclysm': ...}" and `kb search --game` crashed on .lower()
    root = tmp_path / "knowledge"
    (root / "games" / "x").mkdir(parents=True)
    note = root / "games" / "x" / "n.md"
    front = "kind: game\ntitle: t\ngame: Project Zomboid\ngames_also: [Cataclysm: Dark Days Ahead]\ntools: [Python 3.12 (a, b), grep]\ntags: [rts, 2004]\n"
    note.write_text(f"---\n{front}---\n# t\n", encoding="utf-8")
    fails, _ = kb.check_note(note, root)
    for key in ("games_also", "tools", "tags"):
        assert any(f.startswith(key) and "quote" in f for f in fails), (key, fails)
    assert [r["path"] for r in kb.search(root, [], game="cataclysm")] == ["games/x/n.md"]
    assert kb.search(root, ["python"], game="zomboid")
    kb.build_index(root)
    for bare in ("Cataclysm: Dark Days Ahead", "Python 3.12 (a, b)", "2004"):
        front = front.replace(bare, f'"{bare}"')
    note.write_text(f"---\n{front}---\n# t\n", encoding="utf-8")
    fails, _ = kb.check_note(note, root)
    assert not [f for f in fails if f.startswith(("games_also", "tools", "tags"))], fails


@pytest.mark.parametrize("url", ["https://github.com/alice/universal-modder.git","https://github.com/alice/universal-modder",
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


def test_run_timeout_exits_with_a_message(capsys):
    # a command that outlives timeout= ends in die(), like a failed one, not a TimeoutExpired traceback
    from um import common
    with pytest.raises(SystemExit):
        common.run([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.2)
    assert "timed out after 0.2s" in capsys.readouterr().err


# --------------------------------------------------------------------------- backup

@pytest.fixture
def backup_same_second(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(backup.time, "strftime", lambda *args: "20261006-120000")


def test_backup_same_second_keeps_every_snapshot(tmp_path, backup_same_second):
    src = tmp_path / "src"
    paths = []
    for i in range(12):
        make(src, {"save.dat": f"version {i}"})
        paths.append(backup.create(str(src), name="t", note=f"take {i}"))

    assert len(set(paths)) == 12
    assert paths[0].name == "20261006-120000.zip"  # keep the existing filename format when available
    assert backup.snapshots("t") == paths         # latest selection still works after ten collisions
    for i, path in enumerate(paths):
        with backup.zipfile.ZipFile(path) as z:
            assert z.read("save.dat") == f"version {i}".encode()
        assert backup._manifest(path)["note"] == f"take {i}"
    assert backup.diff("t")["changed"] == []
    make(src, {"save.dat": "modified"})
    backup.restore("t", yes=True)
    assert (src / "save.dat").read_text() == "version 11"


@pytest.mark.parametrize("removed", [0, 1])
def test_backup_after_deleted_snapshot_is_still_latest(tmp_path, backup_same_second, removed):
    src = tmp_path / "src"
    make(src, {"save.dat": "old"})
    paths = [backup.create(str(src), name="t") for _ in range(3)]
    paths[removed].unlink()
    make(src, {"save.dat": "new"})
    newest = backup.create(str(src), name="t")

    assert newest > paths[-1]
    assert backup.snapshots("t")[-1] == newest
    assert backup.diff("t")["changed"] == []


def test_backup_concurrent_creates_keep_every_snapshot(tmp_path, backup_same_second):
    from concurrent.futures import ThreadPoolExecutor

    src = tmp_path / "src"
    make(src, {"save.dat": "world"})
    with ThreadPoolExecutor(max_workers=8) as pool:
        paths = list(pool.map(lambda i: backup.create(str(src), name="t", note=str(i)), range(8)))

    assert len(set(paths)) == 8
    assert backup.snapshots("t") == sorted(paths)
    for i, path in enumerate(paths):
        with backup.zipfile.ZipFile(path) as z:
            assert z.read("save.dat") == b"world"
        assert backup._manifest(path)["note"] == str(i)


@pytest.mark.parametrize("error", [OSError, KeyboardInterrupt])
def test_backup_failed_create_keeps_previous_snapshot(tmp_path, backup_same_second, monkeypatch, error):
    src = tmp_path / "src"
    make(src, {"save.dat": "pristine"})
    first = backup.create(str(src), name="t")
    original = first.read_bytes()

    def fail_write(*args, **kwargs):
        raise error("interrupted backup")

    monkeypatch.setattr(backup.zipfile.ZipFile, "write", fail_write)
    with pytest.raises(error, match="interrupted backup"):
        backup.create(str(src), name="t")
    assert backup.snapshots("t") == [first]
    assert first.read_bytes() == original


def test_backup_repeated_restores_keep_undo_snapshots(tmp_path, backup_same_second):
    src = tmp_path / "src"
    make(src, {"save.dat": "pristine"})
    backup.create(str(src), name="t")
    for state in ("first take", "second take"):
        make(src, {"save.dat": state})
        backup.restore("t", yes=True)
        assert (src / "save.dat").read_text() == "pristine"

    undo = backup.snapshots("t-pre-restore")
    assert len(undo) == 2
    for path, state in zip(undo, ("first take", "second take")):
        with backup.zipfile.ZipFile(path) as z:
            assert z.read("save.dat") == state.encode()


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
