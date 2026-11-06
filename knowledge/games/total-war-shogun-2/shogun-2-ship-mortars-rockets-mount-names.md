---
kind: game
title: "Making ported Napoleon ship weapons work in Shogun 2 (mount names, batteries, gun placement, detonators)"
game: "Total War: SHOGUN 2"
games_also: ["Napoleon: Total War"]
game_version: "Shogun 2 build 6262 (v1.1.0) with Fall of the Samurai, Steam, Windows 11"
platform: windows
engine: native
route: data
tools: ["capstone", "Frida 17", "Python (own pack/DB tools)", "um win", "um backup"]
anti_cheat: "none in single player; Frida only in offline single-player custom battles"
status: in-progress
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-26
links: ["https://github.com/Frodo45127/rpfm"]
tags: [naval, ships, mortar, rocket, torpedo, bow-chasers, warscape, total-war, models_naval, projectiles, effects]
---

# Making ported Napoleon ship weapons work in Shogun 2 (mount names, batteries, gun placement, detonators)

> A port of Napoleon's France into Shogun 2 brought Napoleon's ships over as data. Their bomb ketch
> mortars, rocket-ship rockets and several ships' bow guns either never fired or misbehaved.
> `empire.retail.dll` turned out to enforce six hard rules that data must satisfy. All were found by
> disassembly and confirmed with Frida hooks in one-ship custom battles.
>
> In game now:
> - the mortars burst on deck;
> - the rockets fly with trails and burst on impact;
> - the 3-Decker's bow guns fire forward and reload;
> - the steam frigate's fire forward, 3 of its 4 reloading.
>
> The Indiaman's bow guns still stall in their reload. Its cause is identified in game but not fixed.

## Setup
- **Game:** Shogun 2 build 6262 (Steam app 34330, the classic release, not the 2026 Complete Edition) with
  Fall of the Samurai, Windows 11. The 32-bit `empire.retail.dll` has image base 0x10000000.
- **Mod:** a PFH3 "mod" pack enabled through `user.script.txt`. Ships use Napoleon hulls converted into
  `models_naval` v6 rows.
- **Analysis:** capstone over the DLL, plus Frida 17 attached to the running game.
  - Use entry hooks only: a mid-function hook crashed the game.
  - Use one Frida session per function: two sessions hooking the same listener closed the game when both
    were killed.
- **Test launches:** the exe with a temporary `steam_appid.txt` (Steam still runs and checks that the
  account owns the game; the file only lets the exe start without Steam's launcher), driven with `um win`.
  Saves were snapshotted first with `um backup`.
- **Test battles:** each one has a single ship under test against one enemy ship.

## Route and why
- **Route:** data only. The mod does not patch the executable.
- **What the owner asked for:** these weapons fired by a special ability, like FotS's torpedo boat.
- **Why that isn't possible:**
  - The torpedo button (`BCQ_FIRE_TORPEDOS`, 0x102a7910 → 0x1037e240) launches two copies of one
    hard-wired projectile. The table loader binds the row keyed `boshin_naval_torpedo` to a fixed slot
    (0x10c8a4a7).
  - No gun takes part.
  - A ship gun's projectile changes only through the ammunition commands and the AI
    (0x10392020 → 0x10437210).
- **So:** the weapons fire as ordinary guns, as Napoleon itself fires them.

## How the game works (what we had to learn)
1. **Mount names are read by substring** (0x1035db80-0x1035de1c).
   - `mortar` and `rocket` create stub engines whose get-projectile is `xor eax,eax; ret`. Such a gun never
     fires.
   - `torpedo` takes the bow-chaser gun.
   - Anything else is armed by facing.
   - Napoleon's `cannon_mortar` / `cannon_rocket` mounts must be renamed (e.g. `cannon`).
2. **Batteries** (0x1035df23-0x1035df63).
   - Each gun joins the port, starboard, front or back battery it points along.
   - The front battery is refused when |collision-box front z − aim z| > 20 m, and the back battery when
     the gap is > 10 m (constants 20.0 and 10.0).
   - Bowsprit collision can push a bow gun past that limit. It then sits in a broadside battery, draws no
     forward arc and never bears.
3. **Placement** (0x10398b30 → 0x103888d0).
   - At ship placement each gun is put on the deck at the MIDPOINT of its mount position and aim point. A
     deck walk piece must lie within 0.5 m of that point and contain it in plan.
   - A gun that fails is never placed: its world position stays 0, the attack loop skips it (0x10183bc9),
     and it doesn't count as operational.
   - So you can't satisfy rule 2 by stretching the aim point far forward.
4. **Reload tasks** (0x1048a510; points from 0x1044f320; loaded test 0x10472e30).
   - A naval cannon reloads through tasks done at fixed points around its placed point, in metres:
     - task 7: (−0.08, −1.56)
     - task 2: (−0.89, +0.75)
     - task 4: (+0.99, +1.29)
   - A man must walk to each point. If a point is off the deck or unreachable, the gun fires once and never
     counts as loaded again.
5. **Detonators** (burst test 0x10483156-0x10483330).
   - A `percussive` explosion bursts where the shot strikes, if the shot is above the ground or water.
   - A `fuse` explosion never bursts once the shot has struck something. Otherwise it bursts when its
     timer runs out, wherever the shot is.
   - Napoleon's naval shell and rocket are `fuse`: deck hits act as solid shot, and rockets burst in mid-air.
   - FotS's own exploding naval shells are `percussive`.
6. **Effects.**
   - The exe only names `LandBattle.xml`. Particle effects that exist only in `effects/navalbattle.xml`
     (e.g. Empire's `congreve_rocket` trail) draw nothing, at sea too.
   - FotS's naval effects all live in landbattle.xml.
7. **Spread.**
   - `projectiles.spread` is degrees, applied to pitch AND yaw by up to ±spread/2 each (0x10433830).
   - Napoleon's naval rocket has spread 15, so rockets climbed up to 7.5° above the aim and missed.
   - No stock Shogun 2 artillery shot has spread above 0.
8. **Gunnery.**
   - A battery takes the nearest enemy in its shape and issues one attack command (kind 0x2c).
   - The command re-checks its guns on every update (0x101839b0).
   - gate1 measures range from the ship centre, not from the battery.

## Build steps
1. Rename `cannon_mortar` and `cannon_rocket` mounts to `cannon`.
2. For each bow or stern gun, check the 20 m / 10 m battery rule against the collision box. If it fails:
   - keep the mount and aim where Napoleon has them;
   - trim the tip of the jib-boom off the hull's collision until the rule passes (here 1.7-4.1 m on three
     hulls);
   - don't move the aim point: rules 3 and 4 then break.
3. Check every gun's midpoint is on a deck walk piece, and its reload task points are on the deck.
4. Special shells and rockets: detonator `percussive`, effects that exist in landbattle.xml, and a trail
   (`rocket_trail` plus `additive_rocket_trail` for rockets). Shot type `solid_shot` keeps them off the HUD
   ammunition buttons, since `rocket` has a HUD key.
5. Validate offline with a model of these rules: this project's own (unpublished) `tools/naval_engine.py`,
   `projectile_flight.py` and `test_naval_engine.py`.

## Verification
- **Probe:** entry hooks on:
  - the engine constructors (0x1040d450, stubs 0x1040d500 / 0x1040d610);
  - battery add (0x1041c5d0);
  - launch (0x102fb8f0, firing entity at +4, position and velocity at +0xC..+0x20);
  - hit (0x102fab70, unit hit at +4);
  - burst (0x1044bca0, with detonator and position);
  - placement deck-find (0x103888d0 from 0x10398dc5);
  - the attack command (0x101839b0, gate1 0x104375d0, accept 0x10157580).

  Reload state is read from engine +0x754 / +0x75c.
- **Results**, each ship alone against one enemy, roster checked on screen:
  - Bomb Ketch: bursts on the enemy deck at 8-9 m height (filmed).
  - Rocket Ship: rockets with trails, 3 of 4 bursting on the target.
  - 3-Decker: 3 forward volleys, 13 hits.
  - Steam frigate: 5 forward volleys, 11 hits. One bow gun stalls at reload task 7 (bit 0x2): its man is on
    the point but never facing it.
  - Indiaman: its bow guns fire 1-3 shots, then the men stop about 1.5 m short of the point of task 7
    (bit 0x2), behind the gun. **Not fixed.**
- **Not verified:**
  - launch sounds;
  - the collision trim's effect on ramming and AI spacing;
  - 63 other guns whose crew or reload points sit further off the deck than any gun seen reloading.

## Gotchas
1. **"Mount names are never read" is false.** **Symptom:** a search for `cannon_mortar` in the DLL finds
   nothing. **Cause:** the DLL holds the substrings `mortar`, `rocket` and `torpedo`. **Fix:** search for
   short words, not full keys.
2. **A launch log line does not prove the weapon works.** **Symptom:** the probe counted "rocket" launches
   while the owner saw shells going up and bursting in the air. **Cause:** the launch hook only names the
   projectile row. **Fix:** film the projectile frame by frame and log the burst position and height, not
   just launches.
3. **Moving the aim point to satisfy the battery rule unmans the gun.** **Symptom:** the gun is in the
   front battery with an arc drawn, but never fires; the tooltip shows fewer guns operational. **Cause:**
   the placement midpoint fell off the deck. **Fix:** trim the collision instead.
4. **One volley, then silence.** **Symptom:** the bow guns fire once and never again. **Cause:** a reload
   task point is off the deck. **Fix:** keep the guns where task points are on deck; check with a model.
5. **No trail at sea.** **Symptom:** the rocket draws as a dot with a white streak. **Cause:** its trail
   effect existed only in navalbattle.xml, which the game never loads. **Fix:** use effects from
   landbattle.xml.
6. **Mortar shells act as solid shot on deck hits.** **Symptom:** shells hit decks without bursting.
   **Cause:** `fuse` detonator. **Fix:** `percussive`. Misses into water then only splash.
7. **Frida gotchas.**
   - The probe's ship-space vs world-space mix gave a constant 790-803 m "distance": convert frames before
     judging.
   - Run one Frida session per hooked function, and detach gracefully.

## Assets
None new. Napoleon's models, animations and shots were already ported (built from the player's own Napoleon
install and never distributed, see the [faction port](shogun-2-napoleon-france-faction-port.md)); only data
rows and hull collision changed.

## Cost and time
About 20 hours of wall clock over two days. One supervisor ran an offline worker (disassembly, data, builds)
and a game worker (probed one-ship battles), over 12 offline rounds and about 25 test battles.

## Open questions
- **Indiaman's bow guns:** why the men stop about 1.5 m short of reload task 7 (z ≈ 18.6 on that deck).
  Possibly a hatch or obstacle in the walk data.
- **The frigate's fourth bow gun:** its man is on the point but never faces it.
- **Untested guns:** whether the 63 guns flagged by the reload-point model reload in game.
