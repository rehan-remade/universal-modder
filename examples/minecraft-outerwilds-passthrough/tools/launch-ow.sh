#!/usr/bin/env bash
# Launch Outer Wilds through OWML, under Proton, in the background.
#
# Not working on the author's machine (MODLOG, 2026-10-19): OWML's launcher couldn't start the game under
# Proton there, and Steam runs this game with Proton Experimental, not the Proton 11.0 assumed below. The
# game was launched from Steam instead (`steam -applaunch 753640`).
#
# Run from the OWML folder: the launcher reads OWML.Config.json from its *working directory*, not from
# its own location, and dies in SaveConsolePort if it can't find it.
#
# -consolePort tells it not to spin up its console socket (it exits on that path under Wine). The value
# is only written back into the config.
#
# Use Steam's Proton script rather than the bare wine binary: bare wine does not set up WINEDLLPATH or
# the DXVK/vkd3d runtime, and the game exits 53.
set -eu

WINE_DIR="${WINE_DIR:-$HOME/.local/share/Steam/steamapps/common/Proton 11.0}"
OWML="${OWML:-$HOME/.local/share/OuterWildsModManager/OWML}"
COMPAT="${COMPAT:-$HOME/.local/share/Steam/steamapps/compatdata/753640}"
PORT="${PORT:-38737}"
LOG="${LOG:-/tmp/opencode/ow-launch.log}"

export STEAM_COMPAT_DATA_PATH="$COMPAT"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam"
export STEAM_COMPAT_INSTALL_PATH="$OWML"

cd "$OWML"
exec "$WINE_DIR/proton" run ./OWML.Launcher.exe -consolePort "$PORT" >>"$LOG" 2>&1
