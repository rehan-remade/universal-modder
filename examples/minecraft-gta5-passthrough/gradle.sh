#!/bin/bash
# From WSL: sync the Fabric project to the Windows working folder and run a Gradle task there with a Windows JDK
# (Minecraft has to run on Windows, next to GTA).
#   ./gradle.sh build | runClient | genSources
#   ./gradle.sh install      build, then copy the jar into the launcher profile's game dir (<game dir>\mods)
# PASSTHROUGH_WIN_DIR  the Windows working folder (default C:\dev\passthrough); the project is mirrored to its mc\,
#                      and Gradle's cache is its gradle-home\
# PASSTHROUGH_JDK      a Windows JDK 25 (default <PASSTHROUGH_WIN_DIR>\jdk25)
# PASSTHROUGH_MC_DIR   the game dir of the launcher profile you play with (default <PASSTHROUGH_WIN_DIR>\mcgame)
# On Linux or macOS, `cd mc && ./gradlew build` with JDK 25 builds the same jar.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WIN=${PASSTHROUGH_WIN_DIR:-'C:\dev\passthrough'}
DST=$(wslpath -u "$WIN\\mc")
task=${1:-}
case $task in build|runClient|genSources|install) ;; *) echo "usage: gradle.sh build|runClient|genSources|install" >&2; exit 2 ;; esac
if [ "$task" = install ]; then
	"$0" build
	MODS=$(wslpath -u "${PASSTHROUGH_MC_DIR:-$WIN\\mcgame}")/mods
	mkdir -p "$MODS"
	cp -v "$DST/build/libs/passthrough-$(sed -n 's/^version=//p' "$HERE/mc/gradle.properties").jar" "$MODS/"
	exit 0
fi
mkdir -p "$DST"
rsync -a --delete --exclude build --exclude .gradle --exclude run --exclude '*.log' "$HERE/mc/" "$DST/"
# cmd.exe starts in the mirror (a Windows folder, not \\wsl$); .\ because cmd may not look in the current folder
# (NoDefaultCurrentDirectoryInExePath). The JDK and Gradle home go over as environment.
cd "$DST"
export JAVA_HOME=${PASSTHROUGH_JDK:-"$WIN\\jdk25"} GRADLE_USER_HOME="$WIN\\gradle-home"
export WSLENV=${WSLENV:+$WSLENV:}JAVA_HOME:GRADLE_USER_HOME
cmd.exe /d /s /c ".\\gradlew.bat --console=plain $task" 2>&1 | grep -v "UNC paths\|CMD.EXE was started\|Defaulting to Windows"
exit ${PIPESTATUS[0]}
