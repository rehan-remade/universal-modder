#!/bin/sh
# Remove the mod from the game. Close the game first.
#   ./remove.sh          remove the mod only
#   ./remove.sh --all    also remove the recorded history (one CSV per city)
B="${CITIES_USER_DIR:-$HOME/.local/share/Colossal Order/Cities_Skylines}"
if pgrep -x Cities.x64 >/dev/null 2>&1; then echo "Close Cities: Skylines before removing the mod."; exit 1; fi
rm -rf "$B/Addons/Mods/CityDashboard" && echo "mod removed from $B/Addons/Mods/CityDashboard"
if [ "$1" = "--all" ]; then rm -rf "$B/CityDashboard" && echo "history removed from $B/CityDashboard"; else echo "history kept in $B/CityDashboard (use --all to delete it)"; fi
