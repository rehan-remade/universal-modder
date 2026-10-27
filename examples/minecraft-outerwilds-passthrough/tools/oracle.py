#!/usr/bin/env python3
"""The axis-alignment oracle for docs/CONTRACT.md.

The contract's position/yaw/pitch conversion is marked "unverified" until this passes. The problem is
that a wrong sign still renders *a picture*, so the only way to settle it is to compare the picture
against geometry whose answer we already know.

Method
------
1. Freeze the host bridge (`oracle on` through the dev bridge), so it stops sending camera poses.
   Without this the host overwrites the oracle's pose every frame and the test measures the player's
   camera rather than the one it asked for.

2. Build a landmark cross in the guest's world at a known place, using four unambiguous block colours:

       north (-Z)  magenta    east  (+X)  yellow (gold)
       south (+Z)  black      west  (-X)  orange

   Four distinct colours mean the rendered frame identifies the orientation by itself: which one is on
   the left, the right, the top and the bottom says how the world was rotated, and whether it was
   mirrored. One landmark could only prove "it moved"; four prove the whole mapping.

   The cross is built inside a cleared, empty volume high above the terrain. Landmarks placed at ground
   level are unreliable to read: the guest camera ends up inside whatever is there, and the resulting
   frame of dark rock matched the "black" probe across a third of the screen. An empty arena leaves
   only the floor, the four colours and sky in view.

3. Hold the guest camera at a known position aimed at a known yaw and pitch, using the same `cam`
   message the host sends.

4. Read the exported frame out of shared memory and find where each landmark colour landed. Compare
   with what the contract predicts.

Run: `uv run --with Pillow python3 tools/oracle.py`
"""
import importlib.util
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# --- the landmark cross -------------------------------------------------------------------------
# (name, MC block, dx, dz relative to the camera position)
#
# White is deliberately not used. The guest's sky is light blue and its clouds are near-white, so a
# white landmark matches them: a run of the oracle read 17430 "north" pixels from a frame containing no
# landmarks at all, all of them sky and cloud. Every colour here is one the sky cannot produce, so a
# match means a landmark.
LANDMARK_RADIUS = 3  # how far out along each axis the cross is laid

LANDMARKS = [
    ("north", "minecraft:magenta_concrete", 0, -LANDMARK_RADIUS),
    ("south", "minecraft:black_concrete", 0, LANDMARK_RADIUS),
    ("east", "minecraft:yellow_concrete", LANDMARK_RADIUS, 0),
    ("west", "minecraft:orange_concrete", -LANDMARK_RADIUS, 0),
]

# How to recognise each landmark's colour in the frame.
#
# These are the colours as *rendered*, not the block textures' nominal colours, and the two differ a lot:
# Minecraft shades a block by the light reaching it, and the guest scene here is dim, so yellow concrete
# reads as about (143,105,13) rather than its texture's (240,200,40), and orange as (134,59,1). Probes
# set from the texture values matched almost nothing, which is why an early run reported "none of the
# probe colours were found" from a frame that plainly contained all four landmarks.
#
# Holding the probes to the shaded values also makes the black probe safe. Black concrete in shadow is
# about (10,10,10) and the shaded floor is about (100,100,100), so a tight probe does not confuse the
# two; the loose one that matched "anything dark" is what let a cave wall pass as a landmark.
PROBE = {
    "north": ("magenta", (146, 46, 140)),
    "south": ("black", (14, 14, 14)),
    "east": ("yellow", (150, 110, 14)),
    "west": ("orange", (140, 62, 2)),
}

# The camera looks straight down at the cross.
#
# Geometry is the whole trick here, and it has to be checked rather than guessed. The four landmarks sit
# on the axes (north/south/east/west), so they are 90 degrees apart around the camera. Seen from a
# horizontal camera only two can ever be in a 70 degree view — an earlier version had the camera at
# yaw 0, pitch 40 and 6 blocks from a cross 4 blocks below, which puts every landmark 56 degrees off
# the view axis against a 35 degree half-angle, so the frame held nothing but sky. Looking straight down
# at a cross that is narrower than the frustum puts all four in frame at once, arranged symmetrically
# around the centre, which is exactly what the verdict compares against.
CAM_X, CAM_Y, CAM_Z = 0, 120, 0
CAM_PITCH = 90.0  # MC pitch: 90 looks straight DOWN
FOV = 70.0
GROUND_Y = 116  # the landmarks stand on this level, 4 blocks below the camera
LANDMARK_HEIGHT = 3
LANDMARK_WIDTH = 2

# The cleared volume: the camera is inside it, the cross is at the bottom of it, and it reaches wide
# enough that no terrain intrudes on the view down to the landmarks and far enough down to take the
# floor with it.
ARENA_MIN_X, ARENA_MIN_Y, ARENA_MIN_Z = -12, GROUND_Y - 2, -12
ARENA_MAX_X, ARENA_MAX_Y, ARENA_MAX_Z = 12, CAM_Y + 2, 12


def load_probe():
    spec = importlib.util.spec_from_file_location("pf", HERE / "probe-frame.py")
    pf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pf)
    return pf


def dev(command):
    """Run a dev-bridge command; the host's own channel, so the guest's socket stays ours."""
    subprocess.run([str(REPO / "tools" / "slice1.sh"), command],
                   cwd=REPO, env={**__import__("os").environ, "BLOCKCRAFT_NOWAIT": "1"},
                   capture_output=True, timeout=30)


def send_cmd(pf, sock, command):
    pf.send_text(sock, json.dumps({"t": "cmd", "c": command}))


def cam_message(frame, x, y, z, yaw, pitch):
    """The same shape HostBridge sends. Aim from (x,y,z) looking at yaw/pitch."""
    return json.dumps({
        "t": "cam",
        "f": frame,
        "p": [x, y, z],
        "r": [yaw, pitch, 0.0],
        "fov": FOV,
        "fp": True,
        "pl": [x, y - CAM_Y, z],
        "h": yaw,
    })


SLOT_STRIDE = 99_532_800
HEADER = 4096
SHM = "/dev/shm/blockcraft-frame"


def newest_slot():
    with open(SHM, "rb") as f:
        h = f.read(HEADER)
    latest, = struct.unpack_from("<i", h, 40)
    return latest, h


def publish_count():
    with open(SHM, "rb") as f:
        h = f.read(HEADER)
    return struct.unpack_from("<Q", h, 32)[0]


def wait_for_publishing(timeout=5.0):
    """Block until the guest is producing frames.

    A backgrounded Minecraft is throttled by the dynamic-fps mod (`states.invisible` can stop rendering
    altogether), and an idle guest silently returns the *same* frame no matter what pose is sent. Every
    earlier "the camera does not move" reading came from exactly that, so the check is now mandatory.
    """
    a = publish_count()
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.25)
        b = publish_count()
        if b > a:
            return (b - a) / (time.time() - t0)
    return 0.0


def read_colour(slot, w, h):
    with open(SHM, "rb", buffering=0) as f:
        f.seek(HEADER + SLOT_STRIDE * slot)
        return f.read(w * h * 4)


# A pixel only counts as a landmark when it is genuinely close to that colour *and* clearly closer to
# it than to any other. Without both tests a near-black frame classifies every pixel as "south"
# (nearest to (25,25,25)) and the oracle reports a confident, entirely wrong verdict from a black
# screen. That is exactly what its first run produced, so the guards matter more than the tolerance.
#
# The tolerance is deliberately tight. A loose one let the guest's *sky* (181,209,255) match white
# concrete (235,235,235): distance-squared 3992, comfortably inside a 60-per-channel budget, and far
# closer than any other probe, so both guards passed and the oracle reported a confident "north" from
# a frame containing no landmarks at all. Muted, lit scene colours all land within a few thousand of
# each other, so the budget has to be small enough that they cannot collide: 30 per channel.
MATCH_DIST = 30 * 30 * 3
MATCH_MARGIN = 1.6


def classify(px):
    """The probe colour this pixel matches, or None when it matches none of them clearly."""
    dists = sorted(
        ((sum((px[i] - rgb[i]) ** 2 for i in range(3)), name) for name, (_, rgb) in PROBE.items())
    )
    bestd, best = dists[0]
    if bestd > MATCH_DIST:
        return None
    # Demand separation from the runner-up, so a colour sitting between two probes (or an unrelated
    # colour that happens to be nearest to one) is rejected rather than mis-assigned.
    secondd = dists[1][0]
    if secondd < bestd * MATCH_MARGIN * MATCH_MARGIN:
        return None
    return best


# A landmark block at the distances the oracle uses covers thousands of pixels. A handful of stray
# matches is scene noise that happens to be near a probe colour, not a landmark, so anything below this
# is reported as not visible rather than being allowed to carry a verdict.
MIN_LANDMARK_PIXELS = 250


def analyse(pixels, w, h):
    if is_flat(pixels, w, h):
        return {}
    acc = {k: [0, 0, 0] for k in PROBE}
    # The pixel store is RGBA, so the byte stride is 4 and the loop must run over the whole buffer.
    # It used to run over `range(0, w*h, 4)`, which is only a quarter of the frame: `w*h` counts pixels
    # but `pixels[i]` indexes bytes, so the last three quarters of the image were never classified. A
    # landmark sitting in the bottom of the frame was reported "not visible" while a direct count of the
    # same buffer found 31776 of its pixels — the count and the analysis were not looking at the same
    # thing, and the count was right.
    for i in range(0, w * h * 4, 4):
        x = (i // 4) % w
        y = (i // 4) // w
        name = classify((pixels[i], pixels[i + 1], pixels[i + 2]))
        if name:
            a = acc[name]
            a[0] += x
            a[1] += y
            a[2] += 1
    out = {}
    for k, (sx, sy, n) in acc.items():
        if n >= MIN_LANDMARK_PIXELS:
            out[k] = (sx / n, sy / n, n)
    return out


def is_flat(pixels, w, h):
    """True when the frame is essentially one colour, so it cannot settle anything.

    A frame with no geometry in view (looking at the sky, or a world that has not loaded) is a single
    flat fill. The oracle used to accept such a frame and produce a confident verdict from it, because
    every pixel matched whichever probe colour it happened to be nearest to. Anything judged here has
    to have real variation in it.
    """
    # `w*h*4`: the buffer is RGBA bytes, so the sample walk has to span all of them (see analyse).
    # The stride is rounded up to a whole pixel so samples land on the first byte of a pixel.
    step = max(4, ((w * h * 4) // 20000 + 3) // 4 * 4)
    seen = {}
    total = 0
    for i in range(0, w * h * 4, step):
        key = (pixels[i] >> 4, pixels[i + 1] >> 4, pixels[i + 2] >> 4)
        seen[key] = seen.get(key, 0) + 1
        total += 1
    dominant = max(seen.values()) if seen else 1
    return dominant / total > 0.85


def main():
    pf = load_probe()
    try:
        sock = pf.connect()
    except Exception as e:
        print(f"cannot connect to the guest: {e}")
        print("is Minecraft running with the BlockCraft mod?")
        return 1

    print("freezing the host bridge so our pose is the one that renders")
    dev("oracle on")
    time.sleep(0.5)

    # The freeze stops the host sending poses, and the guest stops exporting when no pose has arrived
    # for two seconds (HostState.TIMEOUT_NANOS). So the publishing check has to come *after* we start
    # driving the camera ourselves, otherwise it always sees a guest that has just gone idle.
    fps = 0.0
    for _ in range(40):
        pf.send_text(sock, cam_message(0, 0.5, CAM_Y, 0.5, 0.0, CAM_PITCH))
        time.sleep(0.1)
        fps = wait_for_publishing(timeout=0.4)
        if fps > 0:
            break
    if fps <= 0:
        print("the guest is NOT publishing frames — it is throttled or paused.")
        print("A backgrounded Minecraft is throttled by the dynamic-fps mod; the picture it returns")
        print("would be a stale frame that cannot respond to any pose. Fix that first:")
        print("  set frame_rate_target for the invisible/unfocused states in the profile's")
        print("  config/dynamic_fps.json, then restart the guest.")
        dev("oracle off")
        return 1
    print(f"guest is publishing at {fps:.0f} fps")

    print(f"building the landmark cross at ground level y={GROUND_Y}")

    # Clear the arena first, then lay a floor and stand the landmarks on it.
    #
    # This is not tidiness. `setblock` refuses a cell that is already occupied unless it is told
    # `replace`, and the oracle used to place with a bare `setblock`, so wherever a landmark landed in
    # solid ground it was silently rejected — "Could not set the block" — and the oracle judged a frame
    # with no landmarks in it. Clearing and using `replace` makes the placement unconditional. The
    # camera also has to start somewhere it can actually see from, which is why the arena extends above
    # and around it rather than being centred on the camera's feet.
    arena = (
        (ARENA_MIN_X, ARENA_MIN_Y, ARENA_MIN_Z),
        (ARENA_MAX_X, ARENA_MAX_Y, ARENA_MAX_Z),
    )
    (ax0, ay0, az0), (ax1, ay1, az1) = arena
    send_cmd(pf, sock, f"fill {ax0} {ay0} {az0} {ax1} {ay1} {az1} minecraft:air replace")

    # The floor, as a full XZ slab one level under the landmarks. Written out from the arena bounds:
    # an earlier version had the ground level in the x slot (`fill 115 115 -12 12 115 12`), which
    # filled a 25-block sliver out at x=115 and left the camera looking at bare sky.
    floor_y = GROUND_Y - 1
    send_cmd(pf, sock, f"fill {ax0} {floor_y} {az0} {ax1} {floor_y} {az1} minecraft:stone replace")

    for name, block, dx, dz in LANDMARKS:
        # Centre the block on the offset rather than running outward from it, so the four landmarks are
        # symmetric about the camera. With an asymmetric block the centroids sit slightly off-axis and
        # the "which side did it land on" comparison gets a needless bias.
        half = LANDMARK_WIDTH // 2
        for y in range(GROUND_Y, GROUND_Y + LANDMARK_HEIGHT):
            for ox in range(-half, -half + LANDMARK_WIDTH):
                for oz in range(-half, -half + LANDMARK_WIDTH):
                    send_cmd(pf, sock, f"setblock {dx + ox} {y} {dz + oz} {block} replace")
        print(f"  {name:5s} {block:28s} at ({dx:+d}, {GROUND_Y}, {dz:+d})")

    # The camera sits above the arena floor, aimed at the cross.
    print("letting the world settle…")
    time.sleep(2.0)

    x, y, z = CAM_X, CAM_Y, CAM_Z
    yaw, pitch = 0.0, CAM_PITCH
    print(f"camera at ({x}, {y}, {z}) yaw {yaw} pitch {pitch} (MC: yaw 0 faces +Z, +pitch looks down)")
    print("  expectation if the mapping is correct (looking straight down, +X east, +Z south):")
    print("    north(-Z, magenta) UPPER  (up the screen)")
    print("    south(+Z, black)   LOWER  (down the screen)")
    print("    east (+X, yellow)  LEFT   (facing +Z with Y up, +X is on your left)")
    print("    west (-X, orange)  RIGHT")

    for i in range(150):
        pf.send_text(sock, cam_message(i, x, y, z, yaw, pitch))
        time.sleep(1 / 30)

    time.sleep(0.5)
    slot, hdr = newest_slot()
    w, h = struct.unpack_from("<II", hdr, 256 + 128 * slot + 24)
    px_, py_, pz_ = struct.unpack_from("<ddd", hdr, 256 + 128 * slot + 48)
    gyaw, gpitch = struct.unpack_from("<ff", hdr, 256 + 128 * slot + 72)
    print(f"newest slot {slot} is {w}x{h}, rendered from pose "
          f"({px_:.2f},{py_:.2f},{pz_:.2f}) yaw {gyaw:.1f} pitch {gpitch:.1f}")
    if abs(px_ - x) > 0.5 or abs(py_ - y) > 0.5 or abs(pz_ - z) > 0.5:
        print("  WARNING: the rendered pose is not the one we sent — the hold did not take effect.")
    if w == 0 or h == 0:
        print("slot has no size; nothing was published")
        return 1

    px = read_colour(slot, w, h)
    if is_flat(px, w, h):
        print("\nthe newest frame is essentially one flat colour, so it cannot settle the mapping.")
        print("Nothing with geometry is in view of the pose we held. Check that the landmarks were")
        print("actually placed, and that the camera looks at them rather than at empty sky.")
        dev("oracle off")
        return 1
    found = analyse(px, w, h)

    print("\nwhere each landmark colour landed (x grows right, y grows down):")
    if not found:
        print("  none of the probe colours were found — the landmarks are not in view")
        return 1
    for name in ("north", "east", "south", "west"):
        if name in found:
            cx, cy, n = found[name]
            side = "left" if cx < w * 0.42 else ("right" if cx > w * 0.58 else "centre")
            vert = "upper" if cy < h * 0.42 else ("lower" if cy > h * 0.58 else "middle")
            print(f"  {name:5s} centroid ({cx:6.1f},{cy:6.1f})  -> {side}, {vert} half  ({n} px)")
        else:
            print(f"  {name:5s} not visible")

    print("\nverdict:")
    checks = []
    east, west, south, north = (
        found.get("east"), found.get("west"), found.get("south"), found.get("north")
    )

    # Looking straight down with yaw 0, the screen axes are fixed by the mapping and nothing depends on
    # the pitch sign, which is what makes this view a clean test:
    #   +X (east) is to the LEFT, -X (west) to the RIGHT
    #   +Z (south) is DOWN the screen, -Z (north) UP
    # A mirrored or rotated mapping moves at least one of these, and the four colours between them pin
    # down which.
    if east and west:
        if east[0] < west[0]:
            checks.append("east(+X) is LEFT of west(-X): correct")
        else:
            checks.append("east(+X) is RIGHT of west(-X): EAST/WEST ARE MIRRORED")
    else:
        checks.append(f"east/west not both visible ({'east' if not east else 'west'} missing): "
                      "cannot check the horizontal axis")

    if north and south:
        if north[1] < south[1]:
            checks.append("north(-Z) is ABOVE south(+Z): correct")
        else:
            checks.append("north(-Z) is BELOW south(+Z): NORTH/SOUTH ARE MIRRORED")
    else:
        checks.append(f"north/south not both visible ({'north' if not north else 'south'} missing): "
                      "cannot check the vertical axis")

    # All four landmarks lie on a circle around the camera's axis, so in the frame they should sit at
    # the corners of a square centred on the middle of the screen. That is a strong check on the whole
    # mapping at once: a wrong yaw, a mirror or an axis swap all break the symmetry.
    if len(found) == 4:
        xs = [found[k][0] for k in found]
        ys = [found[k][1] for k in found]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        spread_x, spread_y = max(xs) - min(xs), max(ys) - min(ys)
        offx, offy = cx - w / 2, cy - h / 2
        checks.append(f"cross centre ({cx:.0f},{cy:.0f}) vs frame centre ({w / 2:.0f},{h / 2:.0f}): "
                      f"offset ({offx:+.0f},{offy:+.0f})px "
                      f"{'centred' if abs(offx) < w * 0.15 and abs(offy) < h * 0.15 else 'OFF-CENTRE'}")
        ratio = spread_x / spread_y if spread_y else 0
        checks.append(f"landmark spread {spread_x:.0f}x{spread_y:.0f}px, aspect {ratio:.2f} "
                      "(a square cross seen straight down should be near 1.0)")

    for c in checks:
        print("  " + c)

    ok = len(found) == 4 and not any(
        ("MIRRORED" in c or "OFF-CENTRE" in c or "not both visible" in c) for c in checks
    )
    print("\n" + ("CONTRACT CONFIRMED by the four-landmark cross." if ok else
                  "NOT settled: see the checks above."))

    print("\nreleasing the host bridge")
    dev("oracle off")
    sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

