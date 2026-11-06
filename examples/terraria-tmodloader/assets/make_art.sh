#!/usr/bin/env bash
# Rebuilds FalArsenal/Assets/*.png and FalArsenal/icon.png from fal-generated art, with the repo's CLI.
#
#   ./make_art.sh                   # build the sprites; raw art missing from gen/ is generated (fal key)
#   GEN=~/my-art ./make_art.sh      # raw art somewhere else; OUT=... / ICON=... redirect the results
#
# 1. fal flux/dev draws each object on a flat white background -> gen/<name>.png (1024x1024). The art
#    this mod shipped with is in gen/ as .jpg (flux/dev's default format), so nothing is generated
#    unless you delete a file: there is no fixed seed, so a new call draws something new.
# 2. `um sprite` cuts the background out with a flood fill from the border (interior whites like eyes
#    survive), trims, and scales once with nearest neighbour into the frame sizes the mod uses. Items
#    point right, NPC sprites face left, NPC frames are stacked vertically (the game divides the texture
#    height by Main.npcFrameCount, so any consistent frame size works).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"   # universal-modder/
GEN="${GEN:-$HERE/gen}"
OUT="${OUT:-$HERE/../FalArsenal/Assets}"
ICON="${ICON:-$HERE/../FalArsenal/icon.png}"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$GEN" "$OUT"

um() { "$ROOT/bin/um" "$@"; }
q() { um "$@" >/dev/null; }   # intermediate steps: quiet
# Python with Pillow, for the two steps um has no command for (um's own environment when uv is around)
py() { if command -v uv >/dev/null 2>&1; then uv run --quiet --project "$ROOT" python - "$@"; else python3 - "$@"; fi; }

# ------------------------------------------------------------------ 1. raw art: fal flux/dev

STYLE="16-bit pixel art game sprite in the style of Terraria, crisp dark outline, limited palette, centered, plain flat white background, no shadow, no text"

raw() { local f; for f in "$GEN/$1.png" "$GEN/$1.jpg"; do [ -f "$f" ] && { echo "$f"; return 0; }; done; return 1; }

gen() {   # gen <name> "<what to draw>"
  raw "$1" >/dev/null && return
  # `um fal run` sends exactly these inputs (the image recipe adds fields meant for its default model)
  um fal run fal-ai/flux/dev "prompt=$2. $STYLE" image_size=square_hd num_images:=1 num_inference_steps:=40 \
    output_format=png --out "$GEN" --name "$1"
}

gen missile_launcher "a military shoulder-mounted rocket launcher bazooka seen from the side pointing right, olive green metal tube with yellow and black hazard stripes, grip and scope"
gen missile "a single small guided missile seen from the side pointing right, red nose cone, white and grey body, small tail fins, flame at the back"
gen nuke "a large nuclear bomb warhead pointing straight down, dark olive green body with a yellow radiation trefoil symbol, tail fins at the top"
gen tesla_rifle "a chunky handheld sci-fi tesla gun, perfectly horizontal side view with the muzzle pointing right, thick copper coils around the barrel crackling with electric blue sparks, glowing cyan energy cell, dark steel body and grip"
gen singularity_launcher "a handheld sci-fi black hole blaster gun, perfectly horizontal side view with the muzzle pointing right, long dark purple and black metal barrel, a glowing violet energy orb in a glass chamber at the back, pistol grip underneath"
gen orbital_remote "a handheld orbital strike laser designator remote control, dark grey metal with a long antenna, a big red button and a small glowing screen"
gen scrap_drone "a small hovering robot drone enemy seen from the side, rusty grey metal body, one big glowing red eye lens, two small spinning rotors on top, antenna"
gen neon_slime "a cute glowing cyan neon slime blob enemy with glowing circuit board lines inside it, two black eyes, a small antenna on top"
gen mech_walker "a small bipedal walking robot goblin enemy seen from the side facing left, rusty orange metal body, stubby legs mid-stride, one glowing green eye, claw arms"
gen mothership "a huge flying mechanical drone mothership boss seen from the side, wide saucer-like hull of rusty grey armor plates, one giant glowing red core eye on its underside, antennas, small turrets and blinking landing lights"

# ------------------------------------------------------------------ 2. sprites

# White background -> transparent: --grey 232 clears pixels whose channels are all >= 232 (the white
# plus flux's off-white noise), --tol 0 turns off the colour-distance test.
cut() { local name=$1; shift; q sprite cutout "$(raw "$name")" "$T/$name.png" --bg ffffff --tol 0 --grey 232 "$@"; }

# items, pointing right. --holes also clears white that the object encloses (between grip and barrel)
cut missile_launcher --holes
um sprite fit "$T/missile_launcher.png" "$OUT/HomingMissileLauncher.png" --size 64x26
cut tesla_rifle --holes
um sprite fit "$T/tesla_rifle.png" "$OUT/TeslaRifle.png" --size 62x30
cut nuke --grey 150                        # also the soft grey shadow flux put around it
um sprite fit "$T/nuke.png" "$OUT/TacticalNuke.png" --size 40x84
cut orbital_remote --grey 225 --spread 31  # every channel >= 225: this one sat on a greyer white
um sprite fit "$T/orbital_remote.png" "$OUT/OrbitalStrike.png" --size 24x38

# flux drew these two at an angle: rotate level, fit small, then centre in the frame (--no-upscale).
# They stay the size the first build gave them: the missile is drawn at 1.2x, and the launcher's
# hold offset was tuned for a gun this big.
cut missile
q sprite rotate "$T/missile.png" "$T/missile_level.png" -45
q sprite fit "$T/missile_level.png" "$T/missile_small.png" --size 14x5
um sprite fit "$T/missile_small.png" "$OUT/HomingMissile.png" --size 38x16 --no-upscale
cut singularity_launcher
q sprite rotate "$T/singularity_launcher.png" "$T/singularity_level.png" -16
q sprite fit "$T/singularity_level.png" "$T/singularity_small.png" --size 36x18
um sprite fit "$T/singularity_small.png" "$OUT/SingularityLauncher.png" --size 70x34 --no-upscale

# enemies, facing left, frames stacked vertically
cut scrap_drone --keep-top 0.76            # drop the ground shadow under it
q sprite flip "$T/scrap_drone.png" "$T/drone_left.png"
q sprite fit "$T/drone_left.png" "$T/drone.png" --size 46x30
q sprite frames "$T/drone.png" "$T/drone" --n 2 --kind bob   # frame 2 sits 1 px higher: a hover bob
um sprite sheet "$OUT/ScrapDrone.png" "$T/drone/drone_0.png" "$T/drone/drone_1.png" --vertical

cut neon_slime --grey 90 --spread 60       # its glow fades into the white: clear the pale halo too
q sprite fit "$T/neon_slime.png" "$T/slime.png" --size 38x34 --anchor bottom
q sprite frames "$T/slime.png" "$T/slime" --n 3 --kind squash  # _2 is the squashed one
um sprite sheet "$OUT/NeonSlime.png" "$T/slime/slime_0.png" "$T/slime/slime_2.png" --vertical

cut mech_walker --grey 150
q sprite flip "$T/mech_walker.png" "$T/walker_left.png"
for a in -5 0 5; do                        # a rocking walk: tilted, upright, tilted the other way
  q sprite rotate "$T/walker_left.png" "$T/walker_rot$a.png" "$a"
  q sprite fit "$T/walker_rot$a.png" "$T/walker$a.png" --size 40x46 --anchor bottom
done
um sprite sheet "$OUT/MechWalker.png" "$T/walker-5.png" "$T/walker0.png" "$T/walker5.png" --vertical

# boss: frame 2 is the same hull with the red core flared (only the saturated reds get brighter)
cut mothership
q sprite fit "$T/mothership.png" "$T/ship.png" --size 240x150
py "$T/ship.png" "$T/ship_flare.png" <<'PY'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGBA")
px = im.load()
for y in range(im.height):
    for x in range(im.width):
        r, g, b, a = px[x, y]
        if a and r > 150 and g < 90 and b < 90:
            px[x, y] = (255, min(255, g + 70), min(255, b + 50), a)
im.save(sys.argv[2])
PY
um sprite sheet "$OUT/DroneMothership.png" "$T/ship.png" "$T/ship_flare.png" --vertical

# ------------------------------------------------------------------ 3. mod icon (80x80, the mods list)

py "$OUT/DroneMothership.png" "$ICON" <<'PY'
import sys
from PIL import Image, ImageDraw, ImageFilter
sheet = Image.open(sys.argv[1]).convert("RGBA")
ship = sheet.crop((0, sheet.height // 2, sheet.width, sheet.height))  # frame 2, core lit
ship = ship.crop(ship.getbbox())
icon = Image.new("RGBA", (80, 80))
draw = ImageDraw.Draw(icon)
top, bottom = (12, 14, 26), (60, 26, 30)  # night sky into a red glow
for y in range(80):
    draw.line([(0, y), (79, y)], fill=tuple(int(t + (b - t) * y / 79) for t, b in zip(top, bottom)) + (255,))
small = ship.resize((76, round(ship.height * 76 / ship.width)), Image.LANCZOS)
x, y = (80 - small.width) // 2, (80 - small.height) // 2 + 2
glow = Image.new("RGBA", small.size, (255, 90, 60, 0))
glow.putalpha(small.getchannel("A").filter(ImageFilter.GaussianBlur(4)).point(lambda v: v * 0.45))
icon.alpha_composite(glow, (x, y + 3))
icon.alpha_composite(small, (x, y))
icon.save(sys.argv[2])
print(sys.argv[2], icon.size)
PY
