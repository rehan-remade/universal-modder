"""Find installed games and fingerprint one: engine, scripting runtime, anti-cheat, mod loaders, saves.

    um scan --list                 # Steam / Epic / Xbox installs on this machine (Windows, WSL, Linux, macOS)
    um scan terraria               # fuzzy name or a path; prints the report
    um scan "C:\\Games\\Foo" --json  # machine-readable, for agents

The report ends with ranked modding routes and the playbook to read next
(skills/mod-any-game/references/engines/*.md). Everything here is read-only.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import struct
import subprocess
import time
from pathlib import Path

from um.common import die, is_mac, is_windows, is_wsl, ps_exe, to_posix

MAX_ENTRIES = 80_000
MAX_DEPTH = 6

# --------------------------------------------------------------------------- installed games


def _vdf(text: str) -> dict:
    """Minimal Valve KeyValues parser (libraryfolders.vdf, appmanifest_*.acf)."""
    tokens = re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text)
    stack, cur, key = [], {}, None
    for s, brace in tokens:
        if brace == "{":
            new = {}
            cur[key] = new
            stack.append(cur)
            cur, key = new, None
        elif brace == "}":
            cur = stack.pop() if stack else cur
        elif key is None:
            key = s
        else:
            cur[key] = s.replace("\\\\", "\\")
            key = None
    return cur


def win_folders() -> dict:
    """The user's Windows shell folders (Documents is often redirected into OneDrive), also from WSL."""
    if not (is_windows() or is_wsl()):
        return {}
    cache = win_folders.__dict__
    if "v" not in cache:
        ps = ("$f=[Environment]; "
              "@($f::GetFolderPath('UserProfile'),$f::GetFolderPath('MyDocuments'),$f::GetFolderPath('ApplicationData'),"
              "$f::GetFolderPath('LocalApplicationData')) -join '|'")
        exe = ps_exe()
        try:
            out = subprocess.run([exe, "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30,
                                 cwd="/mnt/c" if is_wsl() else None).stdout.strip()
            prof, docs, roaming, local = (out.split("|") + ["", "", "", ""])[:4]
            cache["v"] = {k: to_posix(v) for k, v in dict(profile=prof, documents=docs, appdata=roaming, localappdata=local).items() if v}
        except (OSError, subprocess.TimeoutExpired):
            cache["v"] = {}
    return cache["v"]


def steam_registry_root() -> Path | None:
    """Where Steam says it lives (Windows registry); many installs aren't under Program Files (e.g. C:\\Steam)."""
    if is_windows():
        import winreg
        for hive, key, value in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    return Path(winreg.QueryValueEx(k, value)[0])
            except OSError:
                continue
    elif is_wsl():
        try:
            out = subprocess.run(["reg.exe", "query", r"HKCU\Software\Valve\Steam", "/v", "SteamPath"], capture_output=True,
                                 text=True, timeout=15, cwd="/mnt/c").stdout
        except (OSError, subprocess.TimeoutExpired):
            return None
        m = re.search(r"SteamPath\s+REG_SZ\s+(.+)", out)
        if m:
            return Path(to_posix(m.group(1).strip()))
    return None


def steam_roots() -> list[Path]:
    cands = []
    reg = steam_registry_root()
    if reg:
        cands.append(reg)
    if is_windows():
        cands += [Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam", Path(r"C:\Program Files\Steam")]
    elif is_wsl():
        cands += [Path("/mnt/c/Program Files (x86)/Steam"), Path("/mnt/c/Program Files/Steam")]
    if is_mac():
        cands.append(Path.home() / "Library/Application Support/Steam")
    if not is_windows():
        cands += [Path.home() / ".steam/steam", Path.home() / ".local/share/Steam",
                  Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam"]
    seen, out = set(), []
    for c in cands:
        try:
            r = c.resolve()
        except OSError:
            continue
        if (r / "steamapps").is_dir() and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def steam_games() -> list[dict]:
    games, libs = [], []
    for root in steam_roots():
        libs.append(root)
        lf = root / "steamapps" / "libraryfolders.vdf"
        if lf.exists():
            data = _vdf(lf.read_text(encoding="utf-8", errors="replace"))
            for v in (data.get("libraryfolders") or {}).values():
                if isinstance(v, dict) and v.get("path"):
                    libs.append(Path(to_posix(v["path"])))
    seen = set()
    for lib in libs:
        apps = lib / "steamapps"
        if not apps.is_dir() or apps.resolve() in seen:
            continue
        seen.add(apps.resolve())
        for acf in apps.glob("appmanifest_*.acf"):
            st = _vdf(acf.read_text(encoding="utf-8", errors="replace")).get("AppState", {})
            path = apps / "common" / st.get("installdir", "")
            if st.get("installdir") and path.is_dir():
                games.append(dict(store="steam", appid=st.get("appid"), name=st.get("name"), path=str(path),
                                  workshop=str(apps / "workshop" / "content" / st.get("appid", "")) if (apps / "workshop" / "content" / st.get("appid", "")).is_dir() else None))
    return games


def epic_games() -> list[dict]:
    base = Path(r"C:\ProgramData") if is_windows() else Path("/mnt/c/ProgramData") if is_wsl() else None
    out = []
    if base:
        for item in (base / "Epic/EpicGamesLauncher/Data/Manifests").glob("*.item"):
            try:
                d = json.loads(item.read_text(errors="replace"))
            except (json.JSONDecodeError, OSError):
                continue
            p = to_posix(d.get("InstallLocation", ""))
            if p and Path(p).is_dir():
                out.append(dict(store="epic", appid=d.get("AppName"), name=d.get("DisplayName"), path=p))
    return out


def xbox_games() -> list[dict]:
    out = []
    for drive in ("c", "d", "e", "f"):
        root = Path(f"{drive.upper()}:/XboxGames") if is_windows() else Path(f"/mnt/{drive}/XboxGames") if is_wsl() else None
        if root and root.is_dir():
            for g in root.iterdir():
                if g.is_dir():
                    out.append(dict(store="xbox", appid=None, name=g.name, path=str(g / "Content" if (g / "Content").is_dir() else g)))
    return out


def all_games() -> list[dict]:
    return steam_games() + epic_games() + xbox_games()


def resolve_game(query: str) -> dict:
    p = Path(to_posix(query)).expanduser()
    if p.is_dir():
        for g in all_games():
            if Path(g["path"]).resolve() == p.resolve():
                return g
        return dict(store=None, appid=None, name=p.name, path=str(p))
    q = re.sub(r"[^a-z0-9]", "", query.lower())
    games = all_games()
    exact = [g for g in games if re.sub(r"[^a-z0-9]", "", (g["name"] or "").lower()) == q or g.get("appid") == query]
    hits = exact or [g for g in games if q and q in re.sub(r"[^a-z0-9]", "", (g["name"] or "").lower() + Path(g["path"]).name.lower())]
    if not hits:
        die(f"no installed game matches {query!r}; pass the install folder instead (`um scan --list` shows what was found)")
    if len(hits) > 1:
        hits.sort(key=lambda g: len(g["name"] or ""))
    return hits[0]


# --------------------------------------------------------------------------- the file index


class Index:
    """Lower-cased relative paths of a game folder (bounded walk)."""

    def __init__(self, root: Path):
        self.root = root
        self.files: list[str] = []
        self.dirs: set[str] = set()
        self.truncated = False
        base = len(str(root)) + 1
        for dirpath, dirnames, filenames in os.walk(root):
            rel = dirpath[base:].replace("\\", "/")
            depth = rel.count("/") + 1 if rel else 0
            if depth >= MAX_DEPTH:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if d.lower() not in ("__pycache__", ".git", "shadercache")]
            for d in dirnames:
                self.dirs.add((rel + "/" + d if rel else d).lower())
            for f in filenames:
                self.files.append((rel + "/" + f if rel else f).lower())
            if len(self.files) > MAX_ENTRIES:
                self.truncated = True
                break

    def find(self, *patterns: str) -> list[str]:
        return [f for f in self.files if any(fnmatch.fnmatch(f, p) for p in patterns)]

    def has(self, *patterns: str) -> bool:
        return any(fnmatch.fnmatch(f, p) for p in patterns for f in self.files)

    def has_dir(self, *patterns: str) -> bool:
        return any(fnmatch.fnmatch(d, p) for p in patterns for d in self.dirs)

    def path(self, rel_lower: str) -> Path:
        """Case-insensitive rel path -> real path."""
        cur = self.root
        for part in rel_lower.split("/"):
            try:
                cur = next(c for c in cur.iterdir() if c.name.lower() == part)
            except (StopIteration, OSError):
                return self.root / rel_lower
        return cur


# --------------------------------------------------------------------------- binary sniffing


def pe_info(path: Path) -> dict | None:
    """Machine type and whether a PE file is a managed (.NET) assembly."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return None
    if head[:2] != b"MZ" or len(head) < 0x40:
        return None
    off = struct.unpack_from("<I", head, 0x3C)[0]
    if off + 0x100 > len(head) or head[off:off + 4] != b"PE\0\0":
        return None
    machine = struct.unpack_from("<H", head, off + 4)[0]
    opt = off + 24
    magic = struct.unpack_from("<H", head, opt)[0]
    dd = opt + (96 if magic == 0x10B else 112)
    clr_rva = struct.unpack_from("<I", head, dd + 14 * 8)[0] if dd + 15 * 8 <= len(head) else 0
    return dict(arch={0x14C: "x86", 0x8664: "x64", 0xAA64: "arm64"}.get(machine, hex(machine)), managed=clr_rva != 0)


def grep_file(path: Path, patterns: list[bytes], limit_mb: int = 400, budget_s: float = 6.0) -> dict[bytes, bytes]:
    """First match of each regex in a (big) binary, read in chunks, bounded by size and time."""
    found, t0, tail = {}, time.time(), b""
    try:
        with open(path, "rb") as f:
            read = 0
            while len(found) < len(patterns) and read < limit_mb << 20 and time.time() - t0 < budget_s:
                chunk = f.read(16 << 20)
                if not chunk:
                    break
                read += len(chunk)
                buf = tail + chunk
                for p in patterns:
                    if p not in found:
                        m = re.search(p, buf)
                        if m:
                            found[p] = m.group(0)
                tail = buf[-256:]
    except OSError:
        pass
    return found


def unity_version(ix: Index, data_dir: str) -> str | None:
    for name in ("globalgamemanagers", "data.unity3d", "maindata", "resources.assets"):
        rel = f"{data_dir}/{name}"
        if rel in ix.files:
            try:
                with open(ix.path(rel), "rb") as f:
                    head = f.read(1 << 16)
            except OSError:
                continue
            m = re.search(rb"(?:20\d\d|6000|[45])\.\d+\.\d+[abfpx]\d+", head)
            if m:
                return m.group(0).decode()
    return None


def godot_pck(path: Path) -> str | None:
    try:
        with open(path, "rb") as f:
            head = f.read(20)
            if head[:4] == b"GDPC":
                fmt, major, minor, patch = struct.unpack_from("<4I", head, 4)
                return f"{major}.{minor}.{patch} (pack format {fmt})"
            f.seek(-12, os.SEEK_END)
            tail = f.read(12)
            if tail[8:] == b"GDPC":   # pck appended to the executable
                size = struct.unpack_from("<Q", tail, 0)[0]
                f.seek(-12 - size, os.SEEK_END)
                head = f.read(20)
                if head[:4] == b"GDPC":
                    fmt, major, minor, patch = struct.unpack_from("<4I", head, 4)
                    return f"{major}.{minor}.{patch} (embedded in exe)"
    except (OSError, struct.error):
        pass
    return None


# --------------------------------------------------------------------------- knowledge tables

ANTI_CHEAT = [
    ("EasyAntiCheat", ("easyanticheat/*", "*easyanticheat*", "start_protected_game.exe", "eac_launcher.exe")),
    ("BattlEye", ("battleye/*", "*beservice*", "*_be.exe")),
    ("EA Javelin anticheat", ("eaanticheat*", "*/eaanticheat*")),
    ("nProtect GameGuard", ("gameguard/*", "*gamemon*.des")),
    ("XIGNCODE3", ("xigncode/*", "*x3.xem")),
    ("Tencent ACE", ("*ace-base*", "*sgguard*", "*/ace/*.sys")),
    ("mhyprot", ("*mhypbase.dll", "*mhyprot*")),
    ("PunkBuster", ("pb/pbsvc*", "pb/pbcl*")),
    ("Ricochet", ("*randgrid.sys",)),
]

LOADERS = [
    ("BepInEx", ("bepinex/core/*", "doorstop_config.ini", ".doorstop_version")),
    ("MelonLoader", ("melonloader/*",)),
    ("UE4SS", ("*ue4ss.dll", "*ue4ss-settings.ini", "*/ue4ss/*")),
    ("tModLoader", ("tmodloader.dll",)),
    ("SMAPI", ("stardewmodapi*", "smapi-internal/*")),
    ("Everest (Celeste)", ("celeste.mod.mm.dll", "everest*")),
    ("ModEngine2", ("*modengine2_launcher.exe", "*config_eldenring.toml")),
    ("REFramework", ("reframework/*",)),
    ("Script Extender (Bethesda)", ("skse64_loader.exe", "skse_loader.exe", "f4se_loader.exe", "nvse_loader.exe", "sfse_loader.exe", "obse64_loader.exe", "obse_loader.exe")),
    ("ScriptHookV", ("scripthookv.dll", "scripthookrdr2.dll")),
    ("ASI loader", ("*.asi",)),
    ("Cyber Engine Tweaks", ("bin/x64/plugins/cyber_engine_tweaks/*",)),
    ("RED4ext", ("red4ext/*",)),
    ("REDmod", ("tools/redmod/*",)),
    ("ReShade", ("*reshade.ini", "*reshade*.log")),
    ("Fabric/Forge profile", ("*fabric-loader*", "*neoforge*", "*forge-*.jar")),
    ("Steamodded (Balatro)", ("*steamodded*",)),
    ("Hollow Knight Modding API", ("*modding api*", "*/managed/mods/*")),
    ("RE_Kenshi (Kenshi OGRE plugin)", ("re_kenshi.dll", "kenshilib.dll")),
    ("Kenshi Mod Manager", ("kenshimodtool.exe",)),
]

# folders whose exes/jars belong to installers and runtimes, not the game (matched with leading "_" stripped,
# so GOG's __redist/__support, EA's __installer and Steam's _CommonRedist count)
SKIP_DIRS = {"redist", "commonredist", "vcredist", "directx", "installer", "installers", "support"}


def _in_skip_dir(rel: str) -> bool:
    return any(part.lstrip("_") in SKIP_DIRS for part in rel.split("/")[:-1])


MOD_DIRS = ["mods", "mod", "addons", "plugins", "custom", "workshop", "usermods", "~mods", "content/paks/~mods", "data/scripts", "bepinex/plugins"]

# known games: better routes than the engine default
KNOWN = {
    "terraria": ("tModLoader (free Steam app 1281930): C# ModItem/ModNPC/ModProjectile/ModSystem, hot reload from ModSources", "dotnet-xna.md"),
    "stardew valley": ("SMAPI + Content Patcher (JSON content packs) or C# SMAPI mods with Harmony", "dotnet-xna.md"),
    "celeste": ("Everest + Olympus; C# code mods with MonoMod hooks, maps with Lönn/Ahorn", "dotnet-xna.md"),
    "rimworld": ("XML Defs + C# with Harmony; drop mods in Mods/ (or Workshop)", "unity.md"),
    "age of empires ii: definitive edition": ("data mods (.dat via genieutils-py), UI/graphics mods, scenarios (AoE2ScenarioParser), SLD sprites", "genie-aoe2.md"),
    "the elder scrolls v: skyrim special edition": ("ESP/ESL plugins (xEdit, Creation Kit), Papyrus, SKSE + CommonLibSSE-NG native plugins, MO2", "bethesda.md"),
    "fallout 4": ("ESP plugins (FO4Edit, Creation Kit), Papyrus, F4SE plugins, MO2", "bethesda.md"),
    "starfield": ("Creation Kit plugins, SFSE", "bethesda.md"),
    "elden ring": ("ModEngine2 (offline, EAC disabled) + Smithbox/DSMapStudio param/map edits; never online", "big-frameworks.md"),
    "grand theft auto v": ("Story mode only: ScriptHookV + ASI loader, OpenIV/CodeWalker; BattlEye guards GTA Online - never mod online", "big-frameworks.md"),
    "grand theft auto v enhanced": ("Story mode only: ScriptHookV (enhanced build) + ASI loader; BattlEye guards GTA Online - never mod online", "big-frameworks.md"),
    "cyberpunk 2077": ("REDmod / Cyber Engine Tweaks (Lua) / RED4ext / ArchiveXL, WolvenKit for assets", "big-frameworks.md"),
    "baldur's gate 3": ("Script Extender (Lua) + LSLib/Multitool for .pak, official mod.io toolkit", "big-frameworks.md"),
    "valheim": ("BepInEx 5 + Jotunn, HarmonyX patches", "unity.md"),
    "lethal company": ("BepInEx 5 + HarmonyX (Thunderstore)", "unity.md"),
    "risk of rain 2": ("BepInEx 5 + R2API (Thunderstore)", "unity.md"),
    "hollow knight": ("Hollow Knight Modding API (Lumafly installer), C# mods", "unity.md"),
    "slay the spire": ("ModTheSpire + BaseMod (Java, SpirePatch)", "misc-engines.md"),
    "slay the spire 2": ("the game's own mod loader: C# .dll + Godot .pck + .json manifest in mods/; BaseLib (NuGet Alchyr.Sts2.BaseLib) for cards, relics and characters", "godot.md"),
    "balatro": ("Steamodded + lovely (Lua injection into the LÖVE game)", "misc-engines.md"),
    "kenshi": ("FCS .mod data mods + asset overrides in mods/<name>/ mirroring data/ (load order in the launcher or KMM); code via RE_Kenshi + KenshiLib C++ plugins (VS2010 v100 x64, GPLv3, listed in the mod's RE_Kenshi.json) - the game exe is native, no CLR", "native.md"),
    "factorio": ("official Lua modding API (mods/ folder, data.lua + control.lua)", "misc-engines.md"),
    "counter-strike 2": ("Workshop maps / Source 2 tools; local -insecure only. VAC: never inject on official servers", "source.md"),
    "portal 2": ("VScript (Squirrel) + Puzzle Maker/Hammer, Workshop", "source.md"),
    "half-life 2": ("Source SDK 2013 mods (C++), maps with Hammer", "source.md"),
    "doom": ("WAD/PK3 mods with a source port (GZDoom/UZDoom)", "misc-engines.md"),
    "minecraft": ("Fabric (Mixin) or NeoForge", "minecraft.md"),
}

# save/profile folders that don't follow the game's name ({profile}, {documents}, {appdata}, {localappdata})
KNOWN_SAVES = {
    "age of empires ii: definitive edition": ["{profile}/Games/Age of Empires 2 DE"],
    "terraria": ["{documents}/My Games/Terraria"],
    "tmodloader": ["{documents}/My Games/Terraria/tModLoader"],
    "stardew valley": ["{appdata}/StardewValley"],
    "the elder scrolls v: skyrim special edition": ["{documents}/My Games/Skyrim Special Edition"],
    "elden ring": ["{appdata}/EldenRing"],
    "grand theft auto v": ["{documents}/Rockstar Games/GTA V"],
    "grand theft auto v legacy": ["{documents}/Rockstar Games/GTA V"],
    "cyberpunk 2077": ["{profile}/Saved Games/CD Projekt Red/Cyberpunk 2077"],
    "counter-strike 2": [],
}

# Live-service games, matched against the whole name (see online_only): a substring test flagged Rusty Lake ("rust"),
# Battlefield 1942 and the 2009 Modern Warfare 2. Older entries in a series with an online-only sibling are left to the
# anti-cheat scan, which still warns when a protected client is installed.
ONLINE_ONLY = ["valorant", "league of legends", "fortnite", "apex legends", "pubg", "pubg battlegrounds", "rainbow six siege",
               "rainbow six siege x", "tom clancy s rainbow six siege", "tom clancy s rainbow six siege x", "call of duty",
               "call of duty hq", "call of duty warzone", "destiny 2", "genshin impact", "escape from tarkov", "battlefield 2042",
               "battlefield 6", "overwatch", "overwatch 2", "counter strike 2", "dota 2", "marvel rivals", "the finals", "rust",
               "dead by daylight", "naraka bladepoint", "warframe", "deadlock"]


def _plain(name: str) -> str:
    """'Tom Clancy's Rainbow Six® Siege' -> 'tom clancy s rainbow six siege'."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", name.lower().replace("®", "").replace("™", "")).split())


def online_only(name: str) -> str | None:
    """The ONLINE_ONLY entry this game's name is, if any. Whole names only, never substrings."""
    n = _plain(name)
    return n if n in ONLINE_ONLY else None

ENGINES = {
    # key: (label, playbook, route)
    "unity-mono": ("Unity (Mono)", "unity.md", "BepInEx 5 (or MelonLoader) plugin in C# with HarmonyX patches; read Managed/Assembly-CSharp.dll with ILSpy; assets via AssetRipper/UABEA"),
    "unity-il2cpp": ("Unity (IL2CPP)", "unity.md", "BepInEx 6 (IL2CPP) or MelonLoader; recover types with Cpp2IL / Il2CppDumper, patch through Il2CppInterop"),
    "unreal": ("Unreal Engine", "unreal.md", "UE4SS (Lua/C++ hooks, live property viewer) and/or pak mods in Content/Paks/~mods (FModel to browse, retoc/repak to pack)"),
    "godot": ("Godot", "godot.md", "recover the project with GDRE Tools; patch scripts/scenes via a PCK overlay or Godot Mod Loader"),
    "gamemaker": ("GameMaker", "misc-engines.md", "UndertaleModTool: decompile/edit GML, sprites and rooms in data.win"),
    "rpgmaker-mvmz": ("RPG Maker MV/MZ (NW.js)", "misc-engines.md", "JS plugins in js/plugins + js/plugins.js; data/*.json for database edits"),
    "rpgmaker-rgss": ("RPG Maker XP/VX/VX Ace (RGSS Ruby)", "misc-engines.md", "extract the RGSS archive, edit Ruby in Scripts.rvdata2"),
    "renpy": ("Ren'Py", "misc-engines.md", "unrpa/unrpyc to read; add .rpy files in game/"),
    "xna-fna": ("XNA/FNA/MonoGame (.NET)", "dotnet-xna.md", "the game's loader if any (tModLoader, SMAPI, Everest), else Harmony/MonoMod patches; read the exe with ILSpy"),
    "dotnet": (".NET application", "dotnet-xna.md", "Harmony/MonoMod patches via a loader (BepInEx supports .NET games too); read with ILSpy"),
    "source": ("Source (1)", "source.md", "custom/ + addons, VScript where supported, Source SDK mods; SourceMod only on servers you run"),
    "source2": ("Source 2", "source.md", "Workshop tools / addons, VScript/Panorama; decompile assets with Source 2 Viewer (VRF)"),
    "creation": ("Bethesda Creation/Gamebryo", "bethesda.md", "ESP/ESL plugins (xEdit, Creation Kit), Papyrus scripts, script-extender plugins, MO2 profiles"),
    "genie": ("Genie (Age of Empires DE)", "genie-aoe2.md", "data mods (genieutils-py), graphics/UI mods, scenarios; SLD sprites"),
    "clausewitz": ("Paradox Clausewitz/Jomini", "misc-engines.md", "script mods (plain text) in Documents/Paradox Interactive/<game>/mod"),
    "re-engine": ("Capcom RE Engine", "big-frameworks.md", "REFramework (Lua scripts, in-game UI) + Fluffy Mod Manager for pak/natives replacements"),
    "fromsoft": ("FromSoftware (Dantelion)", "big-frameworks.md", "ModEngine2 + Smithbox/DSMapStudio, param edits; offline only"),
    "rage": ("Rockstar RAGE", "big-frameworks.md", "story mode: ScriptHookV + ASI loader, OpenIV/CodeWalker for assets; never online"),
    "redengine": ("CD Projekt REDengine", "big-frameworks.md", "REDmod, Cyber Engine Tweaks, RED4ext, WolvenKit (Cyberpunk); REDkit (Witcher 3)"),
    "idtech": ("id Tech / Doom family", "misc-engines.md", "WAD/PK3/PK4 mods, source ports"),
    "cryengine": ("CryEngine", "native.md", "pak (zip) overrides, Lua/XML where exposed; native hooks otherwise"),
    "frostbite": ("Frostbite", "native.md", "Frosty Tool Suite for supported titles, offline only; most titles have kernel anti-cheat"),
    "electron": ("Electron / NW.js / HTML5", "misc-engines.md", "extract resources/app.asar (or package.nw), patch JS, open devtools"),
    "love2d": ("LÖVE (Lua)", "misc-engines.md", "the .love/exe is a zip of Lua; patch or inject with lovely"),
    "zengin": ("ZenGin (Gothic 1/2)", "zengin.md", "Daedalus script mods first (MDK scripts -> .DAT in a .mod volume; Ikarus/LeGo, Ninja); Union plugin SDK (x86 C++ DLL in system/autorun, gothic-api headers) for engine code; GD3D11 renderer; assets in Data/*.vdf via ZenKit. Union/GD3D11 need G1 1.08k_mod or G2 NotR 2.6.0.0-rev2: check the exe build first (on Steam use the Workshop beta, don't swap the exe), see zengin.md"),
    "java": ("Java", "misc-engines.md", "decompile jars (Vineflower/CFR), patch with a mod loader or bytecode (Mixin/ASM)"),
    "defold": ("Defold", "misc-engines.md", "unpack game.arcd; Lua scripts"),
    "cocos": ("Cocos2d-x", "native.md", "Lua/JS scripts if bundled; else native hooks"),
    "haxe": ("Haxe/OpenFL/HaxeFlixel", "misc-engines.md", "assets/ overrides; hscript mod loaders where present (Polymod)"),
    "native": ("Unknown native engine", "native.md", "proxy-DLL loader + function hooks (MinHook/SafetyHook), memory reading; Ghidra/IDA + x64dbg + Cheat Engine"),
}


# --------------------------------------------------------------------------- detection

# exe basenames that mark a binary as an editor/tool, never the game itself
# (matched against the lower-cased stem, e.g. "forgotten construction set")
TOOL_EXE_RE = re.compile(r"construction.?set|\bfcs\b|mod.?tool|mod.?manager|\bkmm\b|launcher|editor|setup|installer")


def detect(ix: Index) -> tuple[list[tuple[str, int, list[str], dict]], dict]:
    """-> [(engine_key, score, evidence, details)], extra facts"""
    hits: list[tuple[str, int, list[str], dict]] = []
    facts: dict = {}

    def add(key, score, ev, **det):
        hits.append((key, score, ev, det))

    # Unity
    data_dirs = [d for d in {"/".join(f.split("/")[:-1]) for f in ix.find("*_data/globalgamemanagers", "*_data/data.unity3d", "*_data/maindata")}]
    if ix.has("*unityplayer.dll", "*unityplayer.so", "*unityplayer.dylib") or data_dirs:
        dd = data_dirs[0] if data_dirs else ""
        il2cpp = ix.has("*gameassembly.dll", "*gameassembly.so", "*gameassembly.dylib", "*il2cpp_data/metadata/global-metadata.dat")
        det = dict(data_dir=dd, version=unity_version(ix, dd) if dd else None)
        info = f"{dd}/app.info" if dd else None
        if info and info in ix.files:
            try:
                company, product = (ix.path(info).read_text(errors="replace").splitlines() + ["", ""])[:2]
                det.update(company=company, product=product)
            except OSError:
                pass
        if il2cpp:
            add("unity-il2cpp", 100, ["UnityPlayer + GameAssembly / global-metadata.dat"], **det)
        else:
            add("unity-mono", 100, ["UnityPlayer + Managed/Assembly-CSharp.dll" if ix.has("*_data/managed/assembly-csharp.dll") else "UnityPlayer"], **det)

    # Unreal
    shipping = ix.find("*/binaries/win64/*-win64-shipping.exe", "*/binaries/win64/*-wingdk-shipping.exe", "*/binaries/linux/*-linux-shipping")
    paks = ix.find("*/content/paks/*.pak", "*/content/paks/*.utoc")
    if shipping or paks or ix.has_dir("engine/binaries/thirdparty"):
        det = {}
        if shipping:
            det["project"] = shipping[0].split("/")[0]
            det["exe"] = shipping[0]
            u16 = lambda t: re.escape(t.encode("utf-16-le"))  # FEngineVersion's branch name is a UTF-16 string on Windows
            pats = [rb"\+\+UE[45]\+Release-\d\.\d+", u16("++UE") + rb"[45]\x00" + u16("+Release-") + rb"\d\x00\.\x00\d\x00(?:\d\x00)?"]
            m = grep_file(ix.path(shipping[0]), pats, budget_s=8)
            for v in m.values():
                det["engine_version"] = v.replace(b"\x00", b"").decode(errors="replace").lstrip("+")
                break
        det["iostore"] = ix.has("*.utoc")
        det["paks"] = len(paks)
        add("unreal", 100 if shipping else 70, ["*-Win64-Shipping.exe" if shipping else "Content/Paks"], **det)

    # Godot
    pcks = ix.find("*.pck")
    for p in pcks[:3]:
        v = godot_pck(ix.path(p))
        if v:
            add("godot", 100, [p], version=v)
            break
    else:
        for exe in ix.find("*.exe", "*.x86_64")[:6]:
            v = godot_pck(ix.path(exe))
            if v:
                add("godot", 100, [f"{exe} (embedded pck)"], version=v)
                break

    # GameMaker
    for name in ("data.win", "game.unx", "game.ios", "game.droid", "assets/game.unx"):
        if name in ix.files:
            det = {}
            try:
                with open(ix.path(name), "rb") as f:
                    head = f.read(64)
                if head[:4] == b"FORM" and head[8:12] == b"GEN8":
                    det["bytecode_version"] = head[17]
            except OSError:
                pass
            add("gamemaker", 100, [name], **det)
            break

    # RPG Maker
    if ix.has("www/js/rpg_core.js", "js/rpg_core.js"):
        add("rpgmaker-mvmz", 100, ["rpg_core.js (MV)"], version="MV")
    elif ix.has("js/rmmz_core.js", "www/js/rmmz_core.js"):
        add("rpgmaker-mvmz", 100, ["rmmz_core.js (MZ)"], version="MZ")
    if ix.has("game.rgssad", "game.rgss2a", "game.rgss3a", "data/scripts.rxdata", "data/scripts.rvdata", "data/scripts.rvdata2"):
        add("rpgmaker-rgss", 100, ix.find("game.rgss*", "data/scripts.r*")[:2])

    # Ren'Py
    if ix.has_dir("renpy") and ix.has_dir("game"):
        add("renpy", 100, ["renpy/ + game/"], archives=len(ix.find("game/*.rpa")))

    # ZenGin (Gothic 1/2): the exe lives in system/, assets in Data/*.vdf volumes
    if ix.has("system/gothic.exe", "system/gothic1.exe", "system/gothic2.exe") or \
            (ix.has("system/vdfs32g.dll", "system/vdfs32.dll") and ix.has("data/*.vdf")):
        add("zengin", 95, ix.find("system/gothic*.exe")[:1] + ix.find("data/*.vdf")[:1])

    # XNA / FNA / MonoGame / .NET
    xna = ix.find("fna.dll", "monogame.framework.dll", "microsoft.xna.framework*.dll", "*/fna.dll")
    # shallowest first: the main exe often sits one level down (Gothic's system/, UE's binaries/)
    exes = sorted((f for f in ix.files if f.endswith(".exe") and not f.rsplit("/", 1)[-1].startswith("unins")
                   and not _in_skip_dir(f)),
                  key=lambda f: (f.count("/"), f))[:12]
    managed = []
    sizes: dict[str, int] = {}
    for e in exes:
        info = pe_info(ix.path(e))
        if info:
            facts.setdefault("executables", {})[e] = info
            if info["managed"]:
                managed.append(e)
        try:
            sizes[e] = ix.path(e).stat().st_size
        except OSError:
            pass
    if xna or ix.has("content/*.xnb"):
        add("xna-fna", 95, (xna or ["Content/*.xnb"])[:2] + managed[:1])
    elif managed or ix.find("*.runtimeconfig.json"):
        biggest_managed = max([sizes.get(m, 0) for m in managed] + [0])
        # native candidates are non-tool binaries only: managers/bundles (e.g. Kenshi's
        # 164 MB KMM) can dwarf the actual game exe, and when every native exe is
        # tool-like (setup.exe, ...) there is no game binary to prefer
        game_like = [e for e in exes if e not in managed and not TOOL_EXE_RE.search(Path(e).stem)]
        big_native = sorted(
            (e for e in game_like if sizes.get(e, 0) > biggest_managed),
            key=lambda e: -sizes.get(e, 0),
        )
        # a .NET Core/5+ apphost is a native exe next to <stem>.dll with a sibling
        # <stem>.runtimeconfig.json / <stem>.deps.json: the game is still .NET
        apphost = bool(big_native) and any(
            big_native[0][:-4] + ext in ix.files for ext in (".runtimeconfig.json", ".deps.json"))
        if managed and big_native and not apphost and all(TOOL_EXE_RE.search(Path(e).stem) for e in managed):
            # the only managed binaries are editors/tools (e.g. Kenshi's Forgotten
            # Construction Set); the shipped game binary is native, so .NET routes
            # (Harmony/BepInEx) do not apply to the game process
            ogre = ix.find("*ogremain*.dll")[:2]
            add("native", 65, big_native[:1] + ogre,
                note=f"managed exe(s) look like tools ({', '.join(managed)}); game binary is native")
        else:
            add("dotnet", 70, (managed or ix.find("*.runtimeconfig.json"))[:2])

    # OGRE (custom native engines, e.g. Kenshi): OgreMain + plugin config.
    # Only a secondary signal here; the tool-exe demotion above (or a stronger
    # engine hit) takes precedence when it fires.
    if not any(h[0] == "native" for h in hits) and ix.has("*ogremain*.dll"):
        plug = ix.find("plugins.cfg", "plugins_*.cfg")
        add("native", 55, ix.find("*ogremain*.dll")[:2] + plug[:1],
            **({"plugin_cfg": plug[0]} if plug else {}))

    # Source / Source 2
    if ix.has("*/gameinfo.gi") or ix.has("game/bin/win64/engine2.dll"):
        add("source2", 100, ix.find("*/gameinfo.gi")[:2] or ["game/bin/win64/engine2.dll"])
    elif ix.has("*/gameinfo.txt") and (ix.has("*_dir.vpk") or ix.has("bin/engine.dll", "bin/x64/engine.dll")):
        add("source", 100, ix.find("*/gameinfo.txt")[:2])

    # Bethesda
    if ix.has("data/*.esm") and ix.has("data/*.bsa", "data/*.ba2"):
        add("creation", 100, ix.find("data/*.esm")[:3])

    # Genie (Age of Empires DE)
    if ix.has("resources/_common/dat/*.dat") and ix.has("aoe2de_s.exe", "aoede_s.exe", "aoe*_s.exe"):
        add("genie", 100, ix.find("resources/_common/dat/*.dat")[:1])

    # Paradox
    if ix.has_dir("common") and ix.has_dir("events") and ix.has("launcher-settings.json", "*/launcher-settings.json"):
        add("clausewitz", 90, ["common/ + events/ + launcher-settings.json"])

    # RE Engine
    if ix.has("re_chunk_000.pak", "re_chunk_000.pak.*"):
        add("re-engine", 100, ["re_chunk_000.pak"])

    # FromSoftware
    if ix.has("eldenring.exe", "game/eldenring.exe", "darksoulsiii.exe", "game/darksoulsiii.exe", "sekiro.exe", "armoredcore6.exe", "game/armoredcore6.exe", "nightreign.exe", "game/nightreign.exe") or ix.has("*/regulation.bin", "regulation.bin"):
        add("fromsoft", 95, ix.find("*eldenring.exe", "*darksoulsiii.exe", "*sekiro.exe", "*armoredcore6.exe", "*nightreign.exe", "*regulation.bin")[:2])

    # RAGE
    if ix.has("gta5.exe", "gta5_enhanced.exe", "playgtav.exe", "rdr2.exe", "gtaiv.exe") or (ix.has("*.rpf") and ix.has("*.exe")):
        add("rage", 95, ix.find("gta5*.exe", "playgtav.exe", "rdr2.exe", "*.rpf")[:2])

    # REDengine
    if ix.has("archive/pc/content/*.archive") or ix.has("bin/x64/witcher3.exe", "content/content0/*.bundle"):
        add("redengine", 100, ix.find("archive/pc/content/*.archive", "bin/x64/witcher3.exe")[:1])

    # id Tech / Doom family
    if ix.has("*.wad", "*.pk3", "base/*.pk4", "id1/pak0.pak", "base/*.resources"):
        add("idtech", 70, ix.find("*.wad", "*.pk3", "base/*.pk4", "id1/pak0.pak", "base/*.resources")[:2])

    # CryEngine, Frostbite
    if ix.has("*crysystem.dll"):
        add("cryengine", 95, ix.find("*crysystem.dll")[:1])
    if ix.has("data/cas.cat", "*layout.toc"):
        add("frostbite", 90, ix.find("data/cas.cat", "*layout.toc")[:1])

    # Electron / NW.js / web
    if ix.has("resources/app.asar", "resources/app/package.json", "package.nw", "nw.dll", "*/nw.dll"):
        add("electron", 90, ix.find("resources/app.asar", "resources/app/package.json", "package.nw", "nw.dll")[:2],
            construct=ix.has("*c3runtime.js", "*c2runtime.js"), phaser=ix.has("*phaser*.js"))
    elif ix.has("index.html") and ix.has("*.js") and not hits:
        add("electron", 50, ["index.html + js"])

    # LÖVE, Java, Defold, Cocos, Haxe
    if ix.has("love.dll", "*.love", "lovec.exe"):
        add("love2d", 95, ix.find("love.dll", "*.love")[:1])
    # shallow jars only: a bundled Ghidra/SDK in a dev subfolder isn't the game's engine
    jars = [j for j in ix.find("*.jar") if j.count("/") <= 1 and not _in_skip_dir(j)]
    if jars and (ix.has_dir("jre", "jre/*", "jdk*", "java*") or len(jars) <= 5):
        add("java", 60, jars[:2])
    if ix.has("game.dmanifest", "game.arcd"):
        add("defold", 100, ["game.arcd"])
    if ix.has("*libcocos2d*.dll", "*cocos2d*.dll"):
        add("cocos", 90, ix.find("*libcocos2d*.dll", "*cocos2d*.dll")[:1])
    if ix.has("lime.ndll", "*lime.hdll"):
        add("haxe", 80, ix.find("lime.ndll", "*lime.hdll")[:1])

    if not hits:
        add("native", 10, ["no known engine signature"])
    hits.sort(key=lambda h: -h[1])
    return hits, facts


def save_hints(name: str, det: dict) -> list[str]:
    """Existing folders where this game probably keeps saves/config (Windows side)."""
    wf = win_folders()
    prof, docs = wf.get("profile"), wf.get("documents")
    appdata, local = wf.get("appdata"), wf.get("localappdata")
    base = re.sub(r"[:®™]", "", name or "")
    names = {n for n in (name, base, base.split(" - ")[0], re.sub(r"\s*(definitive edition|legacy|enhanced|remastered)$", "", base, flags=re.I),
                         det.get("product"), det.get("project")) if n}
    cands = [Path(t.format(**wf)) for t in KNOWN_SAVES.get((name or "").lower(), []) if all(k in wf for k in re.findall(r"{(\w+)}", t))]
    if det.get("company") and det.get("product") and prof:
        cands.append(Path(prof) / "AppData/LocalLow" / det["company"] / det["product"])
    for n in names:
        for d in {docs, prof and str(Path(prof) / "Documents")} - {None}:
            cands += [Path(d) / "My Games" / n, Path(d) / n]
        if prof:
            cands += [Path(prof) / "Saved Games" / n, Path(prof) / "Games" / n]
        if appdata:
            cands.append(Path(appdata) / n)
        if local:
            cands += [Path(local) / n, Path(local) / n / "Saved"]
    if is_mac():
        cands += [Path.home() / "Library/Application Support" / n for n in names]
    if not is_windows() and not is_wsl():
        cands += [Path.home() / ".local/share" / n for n in names] + [Path.home() / ".config" / n for n in names]
    out, seen = [], set()
    for c in cands:
        try:
            if c.is_dir() and str(c) not in seen:
                seen.add(str(c))
                out.append(str(c))
        except OSError:
            pass
    return out


def scan(query: str) -> dict:
    game = resolve_game(query)
    root = Path(game["path"])
    ix = Index(root)
    hits, facts = detect(ix)
    key, score, ev, det = hits[0]
    label, playbook, route = ENGINES[key]
    anti = [n for n, pats in ANTI_CHEAT if ix.has(*pats) or ix.has_dir(*[p.rstrip("/*") for p in pats if p.endswith("/*")])]
    loaders = [n for n, pats in LOADERS if ix.has(*pats) or ix.has_dir(*[p.rstrip("/*") for p in pats if p.endswith("/*")])]
    moddirs = [d for d in MOD_DIRS if d in ix.dirs]
    name = (game.get("name") or root.name)
    lname = name.lower()
    known = next((v for k, v in sorted(KNOWN.items(), key=lambda kv: -len(kv[0])) if k == lname or (k in lname and len(k) > 5)), None)
    online = online_only(name)
    routes = []
    if known:
        routes.append(dict(route=known[0], playbook=known[1], why="known game"))
    if not known or known[1] != playbook or key == "native":
        routes.append(dict(route=route, playbook=playbook, why=f"engine: {label}"))
    if key not in ("native",):
        routes.append(dict(route=ENGINES["native"][2], playbook="native.md", why="fallback when no loader reaches what you need"))
    warnings = []
    if len(ix.files) < 5:
        warnings.append("the install folder is (nearly) empty: the game is not fully installed, or lives elsewhere")
    if anti:
        warnings.append(f"anti-cheat present ({', '.join(anti)}): offline/single-player only, never inject into online play; "
                        "many titles need the anti-cheat disabled via an official offline launch option - do not bypass it")
    if online:
        warnings.append(f"'{online}' is an online competitive game: modding its client breaks the ToS and gets accounts banned - stop, or use official tools only (Workshop/creative modes)")
    if any(l == "ScriptHookV" for l in loaders) and "rage" in key:
        warnings.append("ScriptHookV only works in story mode; launch GTA offline")
    report = dict(
        name=name, store=game.get("store"), appid=game.get("appid"), path=str(root),
        engine=dict(key=key, label=label, confidence=score, evidence=ev, **{k: v for k, v in det.items() if v not in (None, "")}),
        other_engine_signals=[dict(key=h[0], evidence=h[2]) for h in hits[1:4]],
        anti_cheat=anti, mod_loaders_installed=loaders, mod_folders=moddirs,
        workshop=game.get("workshop"), saves=save_hints(name, det),
        executables=facts.get("executables", {}), routes=routes, warnings=warnings,
        playbook=f"skills/mod-any-game/references/engines/{routes[0]['playbook']}",
        files_indexed=len(ix.files), index_truncated=ix.truncated,
    )
    return report


def format_report(r: dict) -> str:
    e = r["engine"]
    lines = [f"{r['name']}" + (f"  ({r['store']} {r['appid']})" if r.get("store") else ""),
             f"  path:      {r['path']}",
             f"  engine:    {e['label']}  [{e['confidence']}%]  evidence: {', '.join(map(str, e['evidence']))}"]
    extra = {k: v for k, v in e.items() if k not in ("key", "label", "confidence", "evidence")}
    if extra:
        lines.append("             " + ", ".join(f"{k}={v}" for k, v in extra.items()))
    if r["other_engine_signals"]:
        lines.append("  also:      " + "; ".join(f"{o['key']} ({', '.join(map(str, o['evidence'][:1]))})" for o in r["other_engine_signals"]))
    ex = r.get("executables") or {}
    if ex:
        lines.append("  exes:      " + ", ".join(f"{k} [{v['arch']}{', .NET' if v['managed'] else ''}]" for k, v in list(ex.items())[:5]))
    lines.append(f"  anti-cheat: {', '.join(r['anti_cheat']) or 'none found'}")
    lines.append(f"  loaders:   {', '.join(r['mod_loaders_installed']) or 'none installed'}")
    if r["mod_folders"]:
        lines.append(f"  mod dirs:  {', '.join(r['mod_folders'])}")
    if r.get("workshop"):
        lines.append(f"  workshop:  {r['workshop']}")
    if r["saves"]:
        lines.append("  saves:     " + "\n             ".join(r["saves"]))
    lines.append("  routes:")
    for i, rt in enumerate(r["routes"], 1):
        lines.append(f"    {i}. {rt['route']}  ({rt['why']}; read references/engines/{rt['playbook']})")
    for w in r["warnings"]:
        lines.append(f"  WARNING:   {w}")
    if r.get("index_truncated"):
        lines.append("  note:      file index truncated (huge install); pass a subfolder for detail")
    return "\n".join(lines)


def main(args):
    if args.list:
        games = all_games()
        if args.json:
            print(json.dumps(games, indent=2))
        elif not games:
            print("no Steam/Epic/Xbox installs found; pass a game folder to `um scan <path>`")
        else:
            for g in sorted(games, key=lambda g: (g["name"] or "").lower()):
                print(f"{g['store']:6} {str(g.get('appid') or ''):>10}  {g['name']}  ->  {g['path']}")
        return
    if not args.game:
        die("give a game name or folder, or --list")
    r = scan(args.game)
    print(json.dumps(r, indent=2) if args.json else format_report(r))


def register(sub):
    p = sub.add_parser("scan", help="find installed games; fingerprint engine, anti-cheat, loaders, saves, routes")
    p.add_argument("game", nargs="?", help="name (fuzzy) or install folder")
    p.add_argument("--list", action="store_true", help="list installed games (Steam, Epic, Xbox)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=main)
