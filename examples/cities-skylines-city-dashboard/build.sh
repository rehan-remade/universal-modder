#!/bin/sh
# Compile the mod against the game's own DLLs and install it (DLL + page) as a local mod.
#   ./build.sh           compile and install
#   ./build.sh --page    assemble and install the page only (takes effect on a browser reload, no game restart)
# Needs the Mono C# compiler (`mcs`) and python3. Nothing from the game is copied anywhere: the game's
# assemblies are only referenced at compile time.
#   CITIES_DIR  game install folder   (default: the Steam library in your home folder, Linux)
#   MODS_DIR    local mods folder     (default: the Linux path; on Windows it is
#               %LOCALAPPDATA%\Colossal Order\Cities_Skylines\Addons\Mods)
set -e
CITIES_DIR="${CITIES_DIR:-$HOME/.local/share/Steam/steamapps/common/Cities_Skylines}"
MODS_DIR="${MODS_DIR:-$HOME/.local/share/Colossal Order/Cities_Skylines/Addons/Mods}"
M="$CITIES_DIR/Cities_Data/Managed"
D="$MODS_DIR/CityDashboard"
cd "$(dirname "$0")"
if [ "$1" != "--page" ]; then
  [ -f "$M/Assembly-CSharp.dll" ] || { echo "game assemblies not found in $M (set CITIES_DIR)"; exit 1; }
  mcs -target:library -nostdlib -noconfig -langversion:6 -optimize -nowarn:0618,0219,0168 \
    -r:"$M/mscorlib.dll" -r:"$M/System.dll" -r:"$M/System.Core.dll" \
    -r:"$M/Assembly-CSharp.dll" -r:"$M/ColossalManaged.dll" -r:"$M/ICities.dll" -r:"$M/UnityEngine.dll" \
    -out:mod/CityDashboard.dll mod/CityDashboard.cs
fi
# one self-contained index.html: styles and scripts inlined, no network needed
python3 - <<'PY'
import glob
base = open('web/src/base.html', encoding='utf-8').read()
css = open('web/src/estilo.css', encoding='utf-8').read()
js = "\n".join(open(f, encoding='utf-8').read() for f in sorted(glob.glob('web/src/*.js')))
open('web/index.html', 'w', encoding='utf-8').write(base.replace('/*@@CSS@@*/', css).replace('/*@@JS@@*/', js))
PY
mkdir -p "$D/web"
[ "$1" = "--page" ] || cp mod/CityDashboard.dll "$D/CityDashboard.dll"
cp web/index.html "$D/web/index.html"
echo "installed in $D"
