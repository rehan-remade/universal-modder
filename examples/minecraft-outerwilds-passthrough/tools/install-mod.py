#!/usr/bin/env python3
"""Install the BlockCraft passthrough into the OWML mods folder.

Restores/refreshes the mod from this project's build output without going through the build's default
OutputPath, so the agent controls exactly what lands in the game folder. Backs up whatever it replaces.

    tools/install-mod.py            # install (build output must exist)
    tools/install-mod.py --restore  # put the 1.0.0 content-port DLL back instead
"""
import argparse
import json
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MOD = Path.home() / ".local/share/OuterWildsModManager/OWML/Mods/SvenTheRedPanda.BlockCraft"
BUILD = PROJECT / "build"
SRC = PROJECT / "ow/src"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restore", action="store_true", help="reinstall the saved 1.0.0 DLL")
    args = ap.parse_args()

    MOD.mkdir(parents=True, exist_ok=True)

    if args.restore:
        dll = PROJECT / "backup-BlockCraft-1.0.0.dll"
        man = PROJECT / "backup-manifest-1.0.0.json"
        shutil.copy2(dll, MOD / "BlockCraft.dll")
        shutil.copy2(man, MOD / "manifest.json")
        print(f"restored 1.0.0 into {MOD}")
        return

    for name, src in [
        ("BlockCraft.dll", BUILD / "BlockCraft.dll"),
        ("BlockCraft.pdb", BUILD / "BlockCraft.pdb"),
        ("manifest.json", SRC / "manifest.json"),
        ("default-config.json", SRC / "default-config.json"),
    ]:
        if not src.exists():
            raise SystemExit(f"missing {src} (run dotnet build first)")
        shutil.copy2(src, MOD / name)

    # Keep the player's own config if present; otherwise seed it from the defaults.
    if not (MOD / "config.json").exists():
        shutil.copy2(SRC / "default-config.json", MOD / "config.json")

    # The dev bridge is opt-in by file presence, as in the portal-gun example.
    (MOD / "dev.enabled").touch()
    (MOD / "shots").mkdir(exist_ok=True)
    print(f"installed into {MOD}")
    for p in sorted(MOD.iterdir()):
        print("  ", p.name)


if __name__ == "__main__":
    main()
