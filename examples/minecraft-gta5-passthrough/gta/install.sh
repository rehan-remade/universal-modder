#!/usr/bin/env bash
# Install the passthrough into GTA V Legacy story mode. The ownership manifest records only files this run
# created; removal deletes only unchanged owned files and preserves everything else.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WIN=${PASSTHROUGH_WIN_DIR:-'C:\dev\passthrough'}
RUNTIME=${RUNTIME:-$HERE/third_party/runtime}
BUILD=${BUILD:-$(wslpath -u "$WIN\\gta\\build")}
ARGS='-nobattleye -noBE'
MANIFEST_NAME=.universal-modder-mcpassthrough-owned

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
MANIFEST=$GTA/$MANIFEST_NAME

remove_owned() {
    [ -f "$MANIFEST" ] || { echo "no ownership manifest at $MANIFEST; refusing broad deletion" >&2; exit 1; }
    changed=0
    while IFS=$'\t' read -r expected rel; do
        case $rel in ''|/*|*'..'*|*\\*) echo "unsafe ownership entry: $rel" >&2; exit 1 ;; esac
        target=$GTA/$rel
        if [ -L "$target" ]; then
            echo "preserving symlink: $rel" >&2
            changed=1
        elif [ -f "$target" ] && [ "$(sha256sum "$target" | cut -d' ' -f1)" = "$expected" ]; then
            rm -v -- "$target"
        elif [ -e "$target" ]; then
            echo "preserving changed file: $rel" >&2
            changed=1
        fi
    done < "$MANIFEST"
    rmdir "$GTA/reshade-shaders/Shaders" "$GTA/reshade-shaders" 2>/dev/null || true
    if [ "$changed" -eq 0 ]; then
        rm -v -- "$MANIFEST"
    else
        echo "ownership manifest retained because changed files remain: $MANIFEST" >&2
    fi
}

if [ "${1:-}" = "--remove" ]; then
    remove_owned
    exit 0
fi
[ "${1:-}" = "" ] || { echo "usage: install.sh [--remove]" >&2; exit 2; }
[ ! -e "$MANIFEST" ] || { echo "already installed according to $MANIFEST; remove it first" >&2; exit 1; }
[ -f "$RUNTIME/ScriptHookV.dll" ] || { echo "fetch the runtime first: gta/fetch_deps.sh" >&2; exit 1; }
[ -f "$BUILD/MCPassthrough.asi" ] || { echo "build it first: gta/build.sh" >&2; exit 1; }

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
printf '%s' "$ARGS" > "$stage/args.txt"
printf '[GENERAL]\r\nEffectSearchPaths=.\\reshade-shaders\\Shaders\\\r\nTextureSearchPaths=.\\reshade-shaders\\Textures\\\r\nPresetPath=.\\ReShadePreset.ini\r\nPreprocessorDefinitions=RESHADE_DEPTH_INPUT_IS_REVERSED=1,RESHADE_DEPTH_INPUT_IS_UPSIDE_DOWN=0,RESHADE_DEPTH_INPUT_IS_LOGARITHMIC=0,RESHADE_DEPTH_LINEARIZATION_FAR_PLANE=1000\r\n\r\n[OVERLAY]\r\nTutorialProgress=4\r\nShowClock=0\r\nShowFPS=0\r\n\r\n[SCREENSHOT]\r\nSavePath=.\\\r\n' > "$stage/ReShade.ini"
printf 'Techniques=MCPassthrough@MCPassthrough.fx\r\nTechniqueSorting=MCPassthrough@MCPassthrough.fx\r\n' > "$stage/ReShadePreset.ini"

sources=(
    "$RUNTIME/ScriptHookV.dll"
    "$RUNTIME/dinput8.dll"
    "$BUILD/MCPassthrough.asi"
    "$RUNTIME/ReShade64.dll"
    "$HERE/shaders/MCPassthrough.fx"
    "$HERE/third_party/ReShade.fxh"
    "$HERE/third_party/ReShadeUI.fxh"
    "$stage/args.txt"
    "$stage/ReShade.ini"
    "$stage/ReShadePreset.ini"
)
targets=(
    "ScriptHookV.dll"
    "dinput8.dll"
    "MCPassthrough.asi"
    "ReShade64.asi"
    "reshade-shaders/Shaders/MCPassthrough.fx"
    "reshade-shaders/Shaders/ReShade.fxh"
    "reshade-shaders/Shaders/ReShadeUI.fxh"
    "args.txt"
    "ReShade.ini"
    "ReShadePreset.ini"
)

# Complete preflight: never start an install that would replace someone else's bytes.
for i in "${!sources[@]}"; do
    src=${sources[$i]}; rel=${targets[$i]}; dst=$GTA/$rel
    [ -f "$src" ] || { echo "missing install source: $src" >&2; exit 1; }
    [ ! -L "$dst" ] || { echo "refusing destination symlink: $rel" >&2; exit 1; }
    if [ -e "$dst" ] && ! cmp -s "$src" "$dst"; then
        echo "refusing to replace existing file: $rel" >&2
        exit 1
    fi
done

manifest_tmp=$stage/owned
: > "$manifest_tmp"
for i in "${!sources[@]}"; do
    src=${sources[$i]}; rel=${targets[$i]}; dst=$GTA/$rel
    if [ ! -e "$dst" ]; then
        mkdir -p "$(dirname "$dst")"
        cp -v -- "$src" "$dst"
        printf '%s\t%s\n' "$(sha256sum "$dst" | cut -d' ' -f1)" "$rel" >> "$manifest_tmp"
    else
        echo "preserving identical pre-existing file: $rel"
    fi
done
[ -s "$manifest_tmp" ] || { echo "nothing new was installed"; exit 0; }
mv -- "$manifest_tmp" "$MANIFEST"
echo "installed into $GTA; ownership manifest: $MANIFEST"
