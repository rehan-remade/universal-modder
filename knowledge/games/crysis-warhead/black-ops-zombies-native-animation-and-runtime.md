---
kind: game
title: "Black Ops Zombies in Warhead: native viewmodels, reload accounting, materials and bounded tests"
game: "Crysis Warhead"
games_also: ["Call of Duty: Black Ops"]
game_version: "Warhead Bin64 1.1.1.711; owned Black Ops PC IWffu100 fastfiles v473"
platform: windows
engine: cryengine
route: reimplementation
tools: ["Universal Modder 0.2.0", "Python 3.12", "Lua 5.1 via Lupa", "Blender 5.2.1 LTS", "OpenAssetTools v0.33.0 with local extensions", "Ghidra 12.1.4", "FFmpeg gfxcapture", "private CGF/CHR/CAF and SWF writers"]
anti_cheat: "Private Warhead single-player copy only; Black Ops archives read offline; no injection or ownership bypass"
status: in-progress
agents: ["Codex (GPT-6)"]
humans: []
date: 2026-10-11
links:
  - https://github.com/Laupetin/OpenAssetTools/tree/v0.33.0
  - https://github.com/niftools/pyffi/blob/develop/pyffi/formats/cgf/cgf.xml
  - https://github.com/ruffle-rs/ruffle/tree/master/swf/src
  - https://github.com/vgmstream/vgmstream/blob/master/src/meta/fsb.c
tags: [mashup, zombies, cryengine2, lua, chr, caf, cgf, reload, nanosuit, materials, scaleform, audio, verification]
---

# Black Ops Zombies in Warhead: verified routes and remaining gaps

A private Warhead copy runs a ground-enemy Zombies prototype with emergence, damage, rounds and purchases while retaining the player's nanosuit and native health/energy/ammunition HUD. Only the host runs; owned Black Ops files supply references and locally converted content. Selected weapons use native skeletal source gestures, but the whole arsenal and long survival experience are incomplete.

Read the companion [Black Ops extraction](../call-of-duty-black-ops/t5-zombies-script-animation-and-audio-recovery.md) and [Warhead static-analysis](build-711-static-analysis-and-level-pak-method-6.md) notes. No converter, game content or playable package is distributed here.

## Setup

Windows; Warhead Bin64 `1.1.1.711`, DX9, low graphics, separate game copy and profile. Keep originals unchanged, decompiles/assets outside this repository, and recoverable profile/file snapshots before temporary overlays. Do not overwrite a running player's mod.

The player configuration uses windowed 1920x1080, `g_skipIntro=1`, `r_VSync=1`, `fixed_time_step=-0.0166666666667` and below-normal process priority. Bounded captures measured about 60 FPS on this machine. The inspected timer uses negative fixed timestep to wait for the wall-clock budget, then advances by the absolute simulation delta; it is not a universal limiter and can affect pace when frames miss the budget. `sys_MaxFPS` and `r_ZNear` were not assumed to exist; `cl_nearPlane` was the actual observed near-plane override.

## Route and why

Translate selected Zombies rules into host Lua modules and native weapon/entity adapters. Keep source rules, host API calls and presentation adapters separate so adaptations remain explicit.

The initial creature route baked source poses into shared static CGFs, permitting an independently validated emergence/damage slice without a matching Resource Compiler. Rigid guest guns attached to host hands could not animate barrels, magazines or cartridges. First-person weapons advanced to native CHR skins and CAF animation; the private build uses both routes.

## How the game works

### Activation, collision and player

Loose files under the copy's `Game` folder activated with `sys_PakPriority=0`; a presumed higher-priority PAK had not established activation. A cleaned cloned airfield removes original combatants. The custom arena is a host adaptation, not Kino geometry.

Loading ends at PRESS ANY KEY. Wait for a fresh `Level zombies_airfield loading time:` marker, target the authorized game's exact foreground process, send Enter and check actual mode startup. A load line alone does not prove gameplay began.

A custom `PE_LIVING` creature needed nested `Living` initialization. Top-level dimensions followed by setters had not yielded a projectile collider. Initialize its capsule, enable ray/explosion collision types on physical parts and traceability, then prove native bullets reach it. Observed Lua dimension names are `pivot_height`, `eye_height`, `cyl_r`, `cyl_height`, `cyl_pos`.

Preserve native player identity/body, `arms_nanosuit_us.chr`, suit powers and armor. Separate imported health or a guest player actor can conceal host damage/energy behavior. Entity IDs are userdata, not ordinary numbers: stringify logs and use an explicit stable hash where numeric variation is required.

### Native source weapons

The private CHR writer preserves host arm render streams and extends a donor skeleton for source gun articulation. Correct inter-chunk padding matters: implicit array counts inferred from chunk extent caused a native heap crash in the initial candidate. Each subset needs GPU bone palettes, internal weights, `Ext2Int` remapping, internal faces and compatible shape streams. Preserve unchanged donor `W2B`/`B2W` matrices exactly; they were not universally inverse here. Skin checks must distinguish internal and remapped render vertices.

CAF bone CRC32 IDs are case-sensitive. This CAL implementation honored only the first animation `filepath`; leaving the donor path first loaded the wrong clips. Missing/NO source tracks inherit idle/base transforms rather than glTF rest. Retain coherent units/bases and host anatomical arm lengths. Inspect grip, sights and full/empty gestures per weapon; pistol and shoulder-gun placement are not interchangeable.

Apply source sight-camera correction to both arms and gun. A front-sight marker alone did not center the M14 rear aperture. Hold source ADS idle while native zoom is active, detect actual ADS firing through firing/ammo change, and release that layer for reload/unzoom so it cannot mask the reload marker. IronSight stage exactly `1` failed native zoom for the tested Ray Gun; `1.0001` worked and was separately verified for M1911. This is a build-specific host adaptation.

### Reload timing and ammunition

Bindings differed from newer documentation: `IsFiring`, `Reload`, `IsZoomed` existed, `IsReloading` and `CancelReload` did not. Actor reload overrides did not deliver expected notifications; truthy Lua action returns did not block reload. `GetBonePos` took a name only. `GetAnimationTime` returned clip seconds and could read an older FIFO entry during blends.

Observe actual native playback through an authored marker/gate, with separate source motion/notetracks. Two-frame slowdown gates stretched fades; full-duration constant-pose gates worked. Keep phase hysteresis and completed-note state. Native Single transitioned about 500 ms before CAF end; a 15-native-frame final-pose hold, with normal/Speed Cola motion authored separately, preserved the whole gesture. This is host scheduling, not exact BO blending.

For tested magazine weapons with source capacity `N > 1`, native `clip_size=N-1` plus chamber 1 selected the empty gesture while preserving native full-reload rejection. On empty refill `0 -> N-1`, move the final cartridge from existing reserve; never create ammunition. Capacity-one/tube weapons need separate policies. Reset count history on explicit inventory sync so a scripted change is not mistaken for a shot/refill. Reconciliation must be idempotent and handle low reserve.

Olympia requires break-open full/empty gestures and cartridge notes; the inherited host pump motion was wrong. Python uses intro/loop/out; upgraded Ithaca and SPAS have distinct phase feed amounts. Loop reset can blend gradually, so use peak hysteresis rather than one threshold.

Only the two owned Thundergun definitions had `noPartialReload=1`. Lua rejection and temporary-magazine guards failed. The verified adapter used native capacity 1/chamber 0 to reject every non-empty reload while keeping source counts 2/4; after true empty `0 -> 1` refill it transfers additional cartridges from reserve. Apply only to those validated definitions, with low-reserve/last-cartridge tests.

Dual guns have independent clips, motion and firing but shared reserve. Re-read reserve before each feed and cancel pending feed before inactive/downed processing. An empty left-hand clip reference may reuse the owned normal gesture at empty duration, not a generic host gesture.

### Materials, HUD and sound

BO DXT5nm stores normal XY in alpha/green; convert to legacy ATI2/BC5 verified against owned host maps. Preserve source specular RGB rather than using diffuse as gloss. Packed source specular alpha does not automatically drive host shininess. The selected Illum route used `GLOSS_MAP=0x10`; baked detail layers needed full DX9 mip chains.

Preserve material state, not just pixels. Fur cards became opaque despite source alpha coverage. RGB reticle coverage and authored RGBA reticles need different conversions. The observed glass route used `Opacity=.999` to activate blending. Corrected dog materials were inspected without changing its 236 poses. Host eye shader/detail baking remain adaptations, not identical BO shaders.

This Flash player lacked the XML polling class of the first HUD attempt. Custom SWF driven through `HUD.DisplayBigOverlayFlashMessage` / `setMessageText` rendered dynamic Zombies state. Field instance names must differ from variable names. Preserve native health/energy/ammo/suit indicators and avoid duplicate counters. The final user layout also hid the weapon-name and score panel.

Replacing scope art failed; byte-identical original Crysis scope movies also failed in the candidate integration. The working Zombies HUD renderer finally displayed G11 base scope art. Optional transport field 22 selects scope state with immediate zoom/reload/return updates. Reserving a native-counter rectangle fixed masking; that visible window is a host adaptation. The other five scope definitions were not accepted/installed.

Allocated/playing sound handles did not prove audibility. Direct WAV and legacy wrapper attempts failed. Successful playback used private FEV/FSB banks compatible with owned FMOD `4.14.03`, with unique names/GUIDs; cache aliasing was a hypothesis, not instrumented. `NOSOUND` loads prove format acceptance only. Compare decoded PCM with source, then independently capture game-only output for audibility. Append event banks without renumbering installed IDs. `SeekData` before sequential subsound read-back avoided shared-reader EOF.

### Creatures and performance

For baked poses, blend local bone translation/scale/quaternions before skinning, advance the destination clip and compare final vertices with its current frame. Cap attack transitions before source impact time. Revalidate target identity, room, range, obstruction, stun and active player at impact; do not replay overdue attacks after stun or redirect a pending player hit to a lure.

`PreloadGeometry` pins persisted beyond an entity's `LoadObject` change. Track/release inactive pins and bound current/warm-up sets. Private limits of 128 human/48 dog poses are implementation choices, not engine limits. Shared flow fields use expanded actual obstacle bounds and invalidate on door removal; keep native checks for unregistered obstacles. Never block the game thread on capture/conversion.

## Build steps

1. Create private host/profile and recover owned data with provenance. Separate an engine-independent rules reference from native adapters.
2. Clean a copied mission, mount loose scripts and prove actual startup after Enter.
3. Bake one creature's emergence/movement/attack/death; convert CGF/MTL and independently round-trip samples with PyFFI. Prove native bullets/counting before scaling waves.
4. Preserve player/nanosuit. Take one weapon through CHR/CAF read-back, native loading, sight/grip inspection, real firing and full/empty reload accounting.
5. Add reload families separately. Install only specifically inspected candidates; keep immutable donors separate from installed-rig metadata.
6. Verify rendered alpha, native counters and game-output sounds separately from file acceptance.
7. Back up profile and overwritten files before bounded fixtures; replace overlays atomically to avoid mutating hardlinked originals. Keep a disk recovery manifest. Release held input while that exact game is foreground, close only its launched PID and restore overlays/profile in cleanup.
8. Keep the player launcher free of probes/deadlines. Use timestamp plus PID in evidence names because Windows reuses PIDs.

## Verification

Private evidence from 2026-10-10/11 consists of logs, GPU captures, inspected videos and JSON reports. These contain owned content and are not attached; this note summarizes observed outcomes.

| Evidence | Established | Limit |
|---|---|---|
| CGF round-trips/native projectile tests | Five later samples independently round-tripped; native shots hit creatures and caused counted deaths | Not CHR creature import/every pose |
| Natural run `23224-20261010T084602718127Z` | 500 points/M1911 8+32, real M14 purchase, rounds 1/2 complete, nine kills in round 3; 23 kills total | Early build, 180 seconds, player died; not later-build acceptance |
| Skin catalogue | 68 definitions/73 right-left skins passed serialized source weapon-pose checks | Not every hand/native action/visual acceptance |
| Install manifest, 11:09 UTC | 19 selected source-rig definitions installed | Other conversions do not imply installation |
| Reload checks | 86 Lua cases plus separate physical R/shot/partial/full/empty/Speed Cola fixtures | Mocks do not prove native blocking; families/interruptions incomplete |
| Creature/suit fixture | 13 checks: human/dog bullet death, emergence/chase/melee, dog bite 40, armor, cloak pause, stun, cleanup | Funded health/position fixture, not survival |
| Restart/density | Three restarts/42 checks; three 22-human + 2-dog cycles/51 checks over 188 seconds | Inflated-health stress fixture, not progression/leak proof |
| Density memory/captures | Peak process working set 1,510,592,512 bytes, inspected captures about 60 FPS | One bounded machine sample; engine memory is a different counter |
| G11 `20261011T110400Z` | Four zoom/shot/reload/exit checks; reticle/native counters inspected; installed HUD hashes match | G11 base only, full source appearance incomplete |
| Game-only PCM | Specific M1911, Quick Revive, box and M14 reload samples in output | Selected events, not whole audio mix |

The 19 source definitions are Olympia/M14/M1911/Python/MP40/Thundergun base/upgraded pairs, both dual CZ75 variants, upgraded AK74/Ithaca/SPAS/HS10 and base G11. Ray Gun reload framing failed visual review; candidate source rigs remained uninstalled. Prepared scope images/passing zoom assertions did not establish other scopes' acceptance.

The broader objective was paused at the user's request. No new game tests were performed to write these notes.

## Gotchas

1. **Load line but no gameplay.** Cause: key barrier or stale log. Fix: fresh-session log, foreground Enter and actual startup evidence.
2. **Correct-looking creature, bullets pass through.** Cause: Living/part collision setup. Fix: nested capsule and actual native ray/weapon proof.
3. **Rigid source reload or wrong pump gesture.** Cause: static attachment/host family cannot articulate guest parts. Fix: skeletal route and source clips per definition.
4. **Skeleton extension crashes at load.** Cause found here: chunk extent/padding. Fix: validate implicit arrays/layout rather than rejecting all extensions.
5. **Empty reload creates an extra round.** Cause: chamber/capacity policy. Fix: calibrated native capacity and conservative reserve reconciliation.
6. **Lua rejection passes mocks, native reload still happens.** Cause: callback assumptions. Fix: native refusal proof and host-enforced policy.
7. **Reload feed/sounds repeat during blends.** Cause: old FIFO time or repeated crossings. Fix: playback markers, hysteresis and completed-event tracking.
8. **Zoom test completes but sight never appears.** Cause: input before first draw or invisible movie. Fix: state-based checks plus independent screenshot acceptance.
9. **Fur/glass looks solid or spiky.** Cause: alpha state, packed channels or shader translation. Fix: inspect source pixels/state and actual rendering.
10. **Sound proof is only a playing handle.** Fix: game-only PCM comparison; label NOSOUND checks offline.
11. **W movement goes prone on AZERTY.** Cause: virtual key maps to a different physical scan code. Fix: resolve the intended DirectInput key for the active layout.
12. **Tests damage installed files or confuse old sessions.** Cause: hardlinks, missing restore, reused PIDs. Fix: atomic replacement, recovery archives, timestamped evidence, one authorized game and exact-PID cleanup.

## Assets

Source content and format templates came from the user's owned copies. Public links credit tool/format projects. No game files, donor templates, fonts, decompiled source, binaries or screenshots accompany this note. Private converters/rule implementations would need a separate provenance review before publication.

## Open questions

Remaining: all-weapon state/visual acceptance, scope variants, Ray Gun framing, exact rendering/recoil/burst/secondary behavior, interruptions, effects/audio mixing, wider AI/navigation interactions and long natural survival/performance. Short fixtures cannot close those gaps. This is an in-progress prototype, not a released total conversion.
