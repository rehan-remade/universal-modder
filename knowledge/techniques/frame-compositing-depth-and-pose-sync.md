---
kind: technique
title: "Frame compositing: depth, pose sync, lighting and stale frames"
tags: [mashup, passthrough, frame-compositing, depth-compositing, reshade-addon, reprojection, camera-sync, msaa, readback, seqlock, diagnostics]
date: 2026-10-05
agents: ["Claude Code (Opus 5.5)"]
humans: ["LeiiLo"]
links: ["https://github.com/rehan-remade/universal-modder/tree/main/examples/minecraft-gta5-passthrough"]
---

# Frame compositing: depth, pose sync, lighting and stale frames

> When the guest renders its own world and the host blends the guest's colour and depth into its frame, the
> recurring failures are a pose from the wrong frame, unreadable host depth, image-only lighting, and a stale
> picture left on screen. This note collects how four bridges handled them (the GTA V example,
> [NewVegasCraft](https://github.com/Davozh/new-vegascraft), and the CrossOver Elden Ring / Monster Hunter: World bridges). Creator test results are reports.

## When to use it
Frame-compositing or mixed routes (see `choosing-a-mashup-route.md`), usually with a ReShade add-on or a
Present/swapchain hook on the host and a capture in the guest.

## How

### The transport is a CPU copy
Every bridge here reads guest pixels back from the GPU, copies them into shared memory (named Windows
memory, or a file-backed mapping that both a native JVM and a Wine/CrossOver process can map), then uploads
them into host textures. Budget for that copy:
- **Triple slots, double readback.** The CrossOver writers use two alternating PBO sets and three mapped
  frame slots, and throttle capture to host-frame progress.
- **Cap the size.** NewVegasCraft scales the requested guest resolution to a 1920×1080 pixel budget; the GTA
  V example keeps the host aspect and scales by area to about 1080p; the [CrossOver bridges](https://github.com/justbustin/minecraft-crossover-bridge) cap frames at
  1920×1200 and fall back to a depthless overlay window above that.
- **Upload with dynamic textures.** NewVegasCraft's creator reports guest upload going from 18.7 ms to about
  5.0–5.3 ms per frame after switching to dynamic BGRA write-discard textures (creator measurement).
- **Separate the layers.** World colour + depth, then hand/HUD as its own image so it stays stable while the
  world is reprojected. Elden Ring's bridge splits hand and HUD so the hand can be relit and the HUD not.

### Match each image to the pose it was rendered with
- Publish a pose only after its pixels exist. Keep a short pose history on the host (the CrossOver hosts
  keep eight) and choose: exact match → older slot → last uploaded image. Count each outcome and log it
  (they log every 300 presents).
- Read the host camera at present time, not in the main game loop. NewVegasCraft's frame shake was fixed by
  moving the host pose read to the present callback.
- Reproject when poses differ. The GTA V example rotates host-camera rays into the guest pose, then ray-marches
  24 logarithmically spaced depths with three refinements, ending at 400 m or nearer host geometry.

### Lighting is an approximation
Monster Hunter: World multiplies the guest world by blurred host-image luminance; Elden Ring adds ambient and
haze from two 8× downsample passes plus a small colour tint; the GTA V example relights from a blurred host
image, adds screen-space contact shadows and grading. None of these make guest blocks receive real host
shadows. If the user needs that, the route is geometry transfer ([SkyCraft](https://github.com/chasmlol/SkyCraft) draws exported meshes inside
Skyrim's renderer and samples native lights and sun-shadow cascades).

### Build the diagnostic tools first
NewVegasCraft is the model: one key cycles composite / host depth / guest depth / difference views; one drops
a 1×1×2 marker pillar where the native crosshair ray hits; one dumps the native projection matrix and pose; a
capture burst saves frames at a fixed host-frame interval; a pose ring exposes lag 0/1/2. A fake host that
compares each exported frame with the pose recorded for it catches misalignment before the real game is in
the loop (a synthetic test, not proof of real alignment).

## Gotchas
1. **Image slides or shakes when turning.** **Cause:** host pose sampled at a different time from the
   displayed image. **Fix:** read it at present; tag poses and images with a frame counter.
2. **Host depth reads empty.** **Cause:** NewVegasCraft's scene depth was a 4× MSAA surface; an earlier INTZ
   texture theory was wrong and removed. Depth must also be copied before the host clears it. **Fix:**
   instrument the actual depth resource; for that setup MSAA had to be off.
3. **Guest hidden behind glass and water.** **Cause:** host depth sampled after transparent passes.
   **Fix:** [LibertyCraft](https://github.com/mrborghini/libertycraft) snapshots opaque depth before transparency (a geometry-transfer bridge, but the same
   depth issue); native glass then isn't drawn over the guest, a known trade-off.
4. **"Drift" that isn't drift.** NewVegasCraft's last apparent slide was a real guest block intersecting a
   native sign; a live FOV control added during the hunt was removed after it misadjusted calibration.
   **Fix:** keep a list of hypotheses and delete the ones disproved.
5. **Stale guest image over the pause menu.** **Cause:** the host keeps drawing the last upload when the guest
   stops. The GTA V example's author cut around it in the demo; the fix was not built. Host/guest timeouts
   alone don't clear the uploaded image. **Fix:** hide the guest layer while host menus are open (as
   NewVegasCraft does) and drop images older than a set age.
6. **Torn or mixed layers.** **Cause:** the reader accepted a slot mid-write, or uploaded to textures before
   its final sequence check (MHW does; ER validates the CPU copy first and only then schedules GPU uploads).
   Both CrossOver Java writers can also skip a layer when `glMapBufferRange` returns null yet still publish
   valid-layer flags. **Fix:** validate, then upload; clear valid flags on failure.
7. **Shaders fail to compile under Proton.** NewVegasCraft's setup needed a native 32-bit `d3dcompiler_47`
   override. Version-specific; check the current setup.
8. **ReShade doesn't load through its normal proxy.** The GTA V example installs ReShade as an ASI because
   the `dxgi.dll` route did not load for its author.
9. **Field note and code disagree on lag.** The GTA V example's note describes a one-frame pose lag while the
   compositor defaults to zero (measured best per a code comment). **Fix:** record the setting actually used
   with every capture.
10. **Cross-compiler ABI.** NewVegasCraft's initial page describes an MSVC/GCC hidden-return-pointer workaround
    for a ReShade struct-returning virtual method. 32-bit hosts also need address-space budgeting: a whole-map
    allocation can matter. NewVegasCraft also crashed on its first native collision ray because a 4-byte-aligned
    stack met 16-byte SSE loads; aligned storage fixed it.

## Verification
The creator
measurements quoted are reports, not results reproduced here. See
`skills/mashup-mods/references/mashup-cases.md` for versions, and
`knowledge/games/gta-v/minecraft-passthrough.md` for the GTA V example's own field note.
