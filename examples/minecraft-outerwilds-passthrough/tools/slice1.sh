#!/usr/bin/env bash
# Drive the first slice of the BlockCraft passthrough.
#
# Sends commands to the running Outer Wilds mod through its dev bridge (dev_commands.txt) and tails the
# results (dev_log.txt). Both live in the installed mod folder, so nothing has to talk to the game.
#
#   tools/slice1.sh place 6        # put the screen 6 m in front of the camera
#   tools/slice1.sh dump           # host pose + guest status + link/reader counters
#   tools/slice1.sh shot slice1    # screenshot into the mod folder's shots/
#   tools/slice1.sh waitfor frames # block until the host has read a real guest frame
#   tools/slice1.sh tail           # follow the dev log
#
# BLOCKCRAFT_RESET=1 truncates the command file first, for a clean slate.
# BLOCKCRAFT_NOWAIT=1 sends a command without waiting for the log to answer.
set -u

MOD="${BLOCKCRAFT_MOD:-$HOME/.local/share/OuterWildsModManager/OWML/Mods/SvenTheRedPanda.BlockCraft}"
CMD="$MOD/dev_commands.txt"
LOG="$MOD/dev_log.txt"

if [ $# -eq 0 ]; then
	echo "usage: $0 <command...>   (see the header of this script)" >&2
	exit 2
fi

case "$1" in
	tail)
		tail -f "$LOG"
		exit 0
		;;
	screenshot|spectacle|shot)
		# KDE Plasma Wayland: use Spectacle, not grim. KWin does not implement wlroots' screencopy, so grim
		# exits with "compositor doesn't support the screen capture protocol". Spectacle talks to KWin.
		#
		# Spell the flags out: -o only writes a file with --background, and Qt's parser is not reliable at
		# combining short flags, so `-bm` can silently fall through to GUI mode and hang with no file.
		name="${2:-shot-$(date +%H%M%S)}"
		out="$MOD/shots/$name.png"
		mkdir -p "$MOD/shots"
		if WANT_WINDOW="${BLOCKCRAFT_SHOT_ACTIVE:-}" && [ -n "$WANT_WINDOW" ]; then
			spectacle --background --nonotify --activewindow --output "$out" >/dev/null 2>&1
		else
			spectacle --background --nonotify --fullscreen --output "$out" >/dev/null 2>&1
		fi
		if [ -s "$out" ]; then
			echo "shot -> $out"
		else
			echo "spectacle produced no file (is this a Wayland session with KWin running?)" >&2
			exit 1
		fi
		exit 0
		;;
esac

mkdir -p "$MOD"
# BLOCKCRAFT_RESET=1 truncates the command file first: the mod tracks a byte offset, so truncating gives
# it a clean slate without disturbing commands it has not read yet. (Do not delete the file - reopening
# it is how the mod notices there is more to read.)
if [ "${BLOCKCRAFT_RESET:-}" = "1" ]; then
	: >"$CMD"
fi
printf '%s\n' "$*" >>"$CMD"
echo "> $*"

# The bridge polls dev_commands.txt once a frame, so give it a moment and show what came back.
if [ "${BLOCKCRAFT_NOWAIT:-}" = "1" ]; then
	exit 0
fi

# The log only exists once the mod has run, so wait for it rather than spinning on an absent file.
for _ in $(seq 1 40); do
	[ -e "$LOG" ] && break
	sleep 0.25
done

before=$(wc -l <"$LOG" 2>/dev/null || echo 0)
for _ in $(seq 1 40); do
	sleep 0.25
	after=$(wc -l <"$LOG" 2>/dev/null || echo 0)
	if [ "$after" -gt "$before" ]; then
		tail -n "+$((before + 1))" "$LOG"
		break
	fi
done
