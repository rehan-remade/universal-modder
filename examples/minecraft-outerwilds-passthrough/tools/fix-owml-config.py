#!/usr/bin/env python3
"""Repair OWML.Config.json for a Linux (Proton) install.

OWML is a Windows program running under Wine, but it stores its paths in the config the *Linux* way and
adds the drive letter itself. Disassembling OWML.Common.dll (2026-10-19):

    // OwmlConfig.get_GamePath
    if (!WineChecker.IsUsingWine()) return gamePath;
    return "Z:" + gamePath;                  // <- the prefix is added here, not stored

So the config must hold `<steam>/steamapps/common/Outer Wilds/` with **no** `Z:` and no
backslashes. Storing `Z:\\home\\...` makes OWML build `Z:Z:\\home\\...`, and the game reports
"Current game path is not valid". `owmlPath` is the same class of path.

Writing backslash paths from a shell also mangles them (a shell string turns `\\h` into an escape), which
is how this file got broken in the first place, so it is only ever written from here.

    tools/fix-owml-config.py            # show and repair
    tools/fix-owml-config.py --dry-run  # show what it would write

Both paths are guessed from the usual Steam and Mod Manager locations; override them with --game and
--owml if your install is somewhere else.
"""
import argparse
import json
import os
from pathlib import Path

CONFIG = Path.home() / ".local/share/OuterWildsModManager/OWML/OWML.Config.json"


def default_game():
    """The first Steam library that actually holds Outer Wilds."""
    roots = [
        Path.home() / ".steam/steam",
        Path.home() / ".local/share/Steam",
        Path(os.environ.get("STEAM_ROOT", "")) if os.environ.get("STEAM_ROOT") else None,
    ]
    for root in roots:
        if not root:
            continue
        game = root / "steamapps/common/Outer Wilds"
        if game.exists():
            return str(game) + "/"
    # Not installed where we looked: fall back to the most common layout so --dry-run still shows something.
    return str(Path.home() / ".steam/steam/steamapps/common/Outer Wilds") + "/"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--game", default=default_game(), help="Outer Wilds install dir (trailing slash)")
    ap.add_argument("--owml", default=str(CONFIG.parent) + "/", help="OWML install dir (trailing slash)")
    args = ap.parse_args()

    game, owml = args.game, args.owml
    cfg = json.loads(CONFIG.read_text())
    before = (cfg.get("gamePath"), cfg.get("owmlPath"))

    cfg["gamePath"] = game
    cfg["owmlPath"] = owml
    # Launch the game as its own process. The launcher's in-process path loads Assembly-CSharp.dll
    # itself and exits silently under Wine; the exe path is what a normal modded launch does.
    cfg["forceExe"] = True

    print("before:", before)
    print("after: ", (cfg["gamePath"], cfg["owmlPath"]))
    if args.dry_run:
        return
    CONFIG.write_text(json.dumps(cfg, indent=2))
    print("wrote", CONFIG)


if __name__ == "__main__":
    main()
