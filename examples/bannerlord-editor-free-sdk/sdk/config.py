"""Paths and environment for the whole SDK. Every other module reads its paths from here.

Environment variables
  BANNERLORD_DIR         the game install (the folder that holds bin\\ and Modules\\). Default: the standard Steam
                         path, when it exists.
  BANNERLORD_MODULE_DIR  the module being built (<game>\\Modules\\<YourModule>). Required by every command that
                         reads or writes the installed module (install, revert, pack, ...). Library lookups work
                         without it.
  MODULE_ASSET_SUB       the sub-folder of the module's Assets folder that holds this SDK's packages. Default
                         "mymod". The game scans Assets recursively, so any name works.
  SDK_STAGE_DIR          where writers stage their output before install. Default ./stage (relative to the
                         current directory).
  SDK_BACKUP_DIR         where install keeps backups and manifests. Default ./backup.
  SDK_LOCK_FILE          optional lock file: install, revert and pack refuse while it exists and names another
                         owner (harness/game_lock.ps1 writes it). Default ./GAME_LOCK.

Nothing in this module touches the disk beyond looking whether a folder exists.
"""
import os, subprocess, sys

DEFAULT_GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"

_NO_GAME = os.path.join(os.getcwd(), "_BANNERLORD_DIR_not_set")   # a path that never exists, so imports still work

BANNERLORD_DIR = os.environ.get("BANNERLORD_DIR") or (DEFAULT_GAME if os.path.isdir(DEFAULT_GAME) else None)
BANNERLORD_MODULE_DIR = os.environ.get("BANNERLORD_MODULE_DIR") or None
MODULE_ASSET_SUB = os.environ.get("MODULE_ASSET_SUB") or "mymod"
SDK_STAGE_DIR = os.path.abspath(os.environ.get("SDK_STAGE_DIR") or "stage")
SDK_BACKUP_DIR = os.path.abspath(os.environ.get("SDK_BACKUP_DIR") or "backup")
SDK_LOCK_FILE = os.path.abspath(os.environ.get("SDK_LOCK_FILE") or "GAME_LOCK")

GAME = BANNERLORD_DIR or _NO_GAME
MODULES = os.path.join(GAME, "Modules")
NATIVE = os.path.join(MODULES, "Native")
NATIVE_MTLS = os.path.join(NATIVE, "EmAssetPackages", "core", "core_materials", "core_materials.tpac")
NATIVE_DATA = os.path.join(NATIVE, "ModuleData")

# The module. Without BANNERLORD_MODULE_DIR these point into a folder that does not exist.
MODULE = BANNERLORD_MODULE_DIR or os.path.join(SDK_STAGE_DIR, "_no_module")
MODULE_NAME = os.path.basename(os.path.normpath(MODULE))
GAME_ASSETS = os.path.join(MODULE, "Assets")                         # the folder the game scans
ENGINE_LOOSE = os.path.join(GAME_ASSETS, MODULE_ASSET_SUB)            # per-asset packages while the module is loose
LOOSE = os.path.join(MODULE, "AssetsLoose", MODULE_ASSET_SUB)         # ... and while it is packed (never read by the game)
# While the module is packed (tpac_pack.py) the per-asset packages live in AssetsLoose, which the game never reads, and the
# game loads Assets\<sub>_packed. Same depth either way, so dirname(dirname(ASSETS)) stays the module folder.
PACKED = os.path.isdir(LOOSE)
ASSETS = LOOSE if PACKED else ENGINE_LOOSE
RDC_DIR = os.path.join(MODULE, "RuntimeDataCache")
MODULE_DATA = os.path.join(MODULE, "ModuleData")
ASSET_SOURCES = os.path.join(MODULE, "AssetSources", MODULE_ASSET_SUB)
PACKED_SUB = MODULE_ASSET_SUB + "_packed"


def require_game():
    """Exit with a clear message when the game install is unknown."""
    if not BANNERLORD_DIR or not os.path.isdir(NATIVE):
        sys.exit("Bannerlord install not found: set BANNERLORD_DIR to the folder that holds bin\\ and Modules\\ "
                 "(default %s)" % DEFAULT_GAME)


def require_module():
    """Exit with a clear message when no module folder is configured (install, revert and pack commands)."""
    require_game()
    if not BANNERLORD_MODULE_DIR:
        sys.exit("BANNERLORD_MODULE_DIR is not set: point it at the module you are building "
                 "(<game>\\Modules\\<YourModule>). The folder is created by install when it does not exist.")


def source_base(filename):
    """The '$BASE/...' source path the editor stores in a package record (only informative: the game never reads it)."""
    return "$BASE/Modules/%s/AssetSources/%s/%s" % (MODULE_NAME if BANNERLORD_MODULE_DIR else "MyModule", MODULE_ASSET_SUB, filename)


def game_processes():
    """Image names of running processes that belong to the game or its tools. tasklist truncates image names to 25
    characters (TaleWorlds.MountAndBlade.Launcher.exe becomes TaleWorlds.MountAndBlade.), so names are matched by
    prefix: "Bannerlord" (Bannerlord.exe, Bannerlord.BE.exe) and "TaleWorlds.MountAndBlade" (the launcher)."""
    try:
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True).stdout
    except OSError:
        return []
    names = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith('"'):
            continue
        name = line.split('","')[0].strip('"')
        if name.lower().startswith(("bannerlord", "taleworlds.mountandblade")):
            names.append(name)
    return names


def game_running():
    return bool(game_processes())


def lock_refusal(owner=None):
    """SDK_LOCK_FILE (harness/game_lock.ps1): refuse while somebody else holds it (a playtest, a harness run)."""
    held = open(SDK_LOCK_FILE).read().strip() if os.path.exists(SDK_LOCK_FILE) else ""
    if held and not (owner and held.startswith(owner + " ")):
        return "%s is held (%s): not touching the game folder" % (SDK_LOCK_FILE, held)
    return None


if __name__ == "__main__":
    for k in ("BANNERLORD_DIR", "BANNERLORD_MODULE_DIR", "MODULE_ASSET_SUB", "SDK_STAGE_DIR", "SDK_BACKUP_DIR", "SDK_LOCK_FILE",
              "NATIVE", "ASSETS", "RDC_DIR", "PACKED"):
        print("%-22s %s" % (k, globals()[k]))
    print("%-22s %s" % ("game running", game_processes() or "no"))
