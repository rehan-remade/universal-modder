#!/usr/bin/env bash
# Install/remove the GTA V Legacy passthrough through a transactional, ownership-scoped helper.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WIN=${PASSTHROUGH_WIN_DIR:-'C:\dev\passthrough'}
RUNTIME=${RUNTIME:-$HERE/third_party/runtime}
BUILD=${BUILD:-$(wslpath -u "$WIN\\gta\\build")}
ARGS='-nobattleye -noBE'

steam_libraries() {
    for steam in "/mnt/c/Program Files (x86)/Steam" "/mnt/c/Program Files/Steam"; do
        [ -d "$steam/steamapps" ] || continue
        printf '%s\n' "$steam"
        sed -n 's/^[[:space:]]*"path"[[:space:]]*"\(.*\)"/\1/p' "$steam/steamapps/libraryfolders.vdf" 2>/dev/null |
            sed 's/\\\\/\\/g' | while read -r path; do wslpath -u "$path"; done
    done
}

GTA_DIR=${GTA_DIR:-}
if [ -z "$GTA_DIR" ]; then
    while read -r library; do
        acf="$library/steamapps/appmanifest_271590.acf"
        if [ -f "$acf" ]; then
            GTA_DIR="$library/steamapps/common/$(sed -n 's/^[[:space:]]*"installdir"[[:space:]]*"\(.*\)"/\1/p' "$acf")"
            break
        fi
    done < <(steam_libraries)
fi
GTA=${GTA_DIR:?GTA V Legacy not found in your Steam libraries: set GTA_DIR to the folder with GTA5.exe}
case $GTA in [A-Za-z]:*) GTA=$(wslpath -u "$GTA") ;; esac
[ -f "$GTA/GTA5.exe" ] || { echo "GTA5.exe not found in: $GTA" >&2; exit 1; }
[ -f "$HERE/install_passthrough.py" ] || { echo "missing transactional installer helper" >&2; exit 1; }

if [ "${1:-}" = "--remove" ]; then
    exec python3 "$HERE/install_passthrough.py" remove "$GTA"
fi
[ "${1:-}" = "" ] || { echo "usage: install.sh [--remove]" >&2; exit 2; }
[ -f "$RUNTIME/ScriptHookV.dll" ] || { echo "fetch the runtime first: gta/fetch_deps.sh" >&2; exit 1; }
[ -f "$BUILD/MCPassthrough.asi" ] || { echo "build it first: gta/build.sh" >&2; exit 1; }

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
printf '%s' "$ARGS" > "$stage/args.txt"
printf '[GENERAL]\r\nEffectSearchPaths=.\\reshade-shaders\\Shaders\\\r\nTextureSearchPaths=.\\reshade-shaders\\Textures\\\r\nPresetPath=.\\ReShadePreset.ini\r\nPreprocessorDefinitions=RESHADE_DEPTH_INPUT_IS_REVERSED=1,RESHADE_DEPTH_INPUT_IS_UPSIDE_DOWN=0,RESHADE_DEPTH_INPUT_IS_LOGARITHMIC=0\r\n\r\n[OVERLAY]\r\nTutorialProgress=4\r\nShowClock=0\r\nShowFPS=0\r\n\r\n[SCREENSHOT]\r\nSavePath=.\\\r\n' > "$stage/ReShade.ini"
printf 'Techniques=MCPassthrough@MCPassthrough.fx\r\nTechniqueSorting=MCPassthrough@MCPassthrough.fx\r\n' > "$stage/ReShadePreset.ini"

python3 "$HERE/install_passthrough.py" install "$GTA" \
    "$RUNTIME/ScriptHookV.dll" "ScriptHookV.dll" \
    "$RUNTIME/dinput8.dll" "dinput8.dll" \
    "$BUILD/MCPassthrough.asi" "MCPassthrough.asi" \
    "$RUNTIME/ReShade64.dll" "ReShade64.asi" \
    "$HERE/shaders/MCPassthrough.fx" "reshade-shaders/Shaders/MCPassthrough.fx" \
    "$HERE/third_party/ReShade.fxh" "reshade-shaders/Shaders/ReShade.fxh" \
    "$HERE/third_party/ReShadeUI.fxh" "reshade-shaders/Shaders/ReShadeUI.fxh" \
    "$stage/args.txt" "args.txt" \
    "$stage/ReShade.ini" "ReShade.ini" \
    "$stage/ReShadePreset.ini" "ReShadePreset.ini"
