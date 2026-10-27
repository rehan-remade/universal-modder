---
kind: game
title: "Native double jump and infinite skill energy with a full HUD meter"
game: "Ghostrunner"
games_also: []
game_version: "Steam app 1139900, installed build 9002517"
platform: windows
engine: unreal
route: native-hook
tools: ["UE4SS v3.0.1 (log: 3.0.1 Beta #0, Git SHA d935b5b)", "Python 3.12.14", "Capstone 5.0.9", "Windows process-memory APIs", "universal-modder 0.2.0", "ffmpeg gfxcapture"]
anti_cheat: "None detected by the bounded um install scan; single-player. Keep modded runs off leaderboards (Kill Run, speedrun boards)"
status: working
agents: ["WorkBuddy AI (DeepSeek V4.1)", "Codex (GPT-6)"]
humans: []
date: 2026-10-18
links: ["https://github.com/UE4SS-RE/RE-UE4SS", "https://github.com/rehan-remade/universal-modder/pull/359"]
tags: [ghostrunner, unreal, ue4ss, lua, reflection, double-jump, skill-energy, hud, native-patch]
---

# Native double jump and infinite skill energy with a full HUD meter

> Enable the game's own second-jump branch with a reflected player flag, then keep sword-skill energy
> ready while preserving the full HUD meter. The double-jump implementation went through eleven Lua
> revisions; the energy implementation exposed why raw cooldown writes and HUD updates need separate
> verification. The human confirmed both behaviors, and a captured game frame verified the corrected meter.

This extends the double-jump field note from [PR #359](https://github.com/rehan-remade/universal-modder/pull/359),
which closed without merging after its head repository was deleted. The original filename is retained.
WorkBuddy AI's 2026-10-17 journal and note supply the double-jump implementation and revision history;
Codex independently retested the existing mod and implemented the energy/HUD correction on 2026-10-18.
Historical crash diagnoses below are the original session's findings, not crashes reproduced by Codex.

## Setup

- **Game:** Ghostrunner, Steam app **1139900**, installed build **9002517**; x64 shipping executable.
- **Engine:** UE **4.26**, independently reported by `um scan` and the existing UE4SS initialization log.
- **Host:** Windows 10 x64, build **19045**.
- **Existing loader:** UE4SS **v3.0.1**. Its log reports "3.0.1 Beta #0" and Git SHA **d935b5b**, which is
  the commit of RE-UE4SS's `v3.0.1` release tag, so the original session's release archive and the binary
  loaded on the retest are the same release. It was already installed and loaded; installing or upgrading
  a loader was not part of the Codex session.
- **Helper:** Python **3.12.14**, Capstone **5.0.9**, `ctypes` access to Windows process-memory APIs.
- **Lab:** saves and configuration were backed up with `um backup`; `um win shot` captured the game window.

The original session also observed a 35.8 GB classic PAK with a companion `.sig`, rather than IoStore
`.utoc`/`.ucas` files. The Lua route avoided editing or repacking game content. An empty `LogicMods`
directory alone was not treated as proof that Blueprint mod loading worked.

The tested `Ghostrunner-Win64-Shipping.exe` has SHA-256:

```text
c6ceba1a667a7859606cf3922b51ace6f0032a2637718c2502d6b433a8202454
```

Every numeric layout and executable RVA below is an observation for **that image**. A matching game name,
store label or Unreal version alone is insufficient to reuse the patch on another build.

## Route and why

Use live Unreal reflection to identify the possessed player and skill objects, then make a temporary
native change in the running process. The requested result was for the current game, so a restart or
replacement PAK was unnecessary.

For double jump, WorkBuddy AI's `DoubleJump` Lua mod enables the native flag through UE4SS's reflection
API. Codex found it already installed and verified it without adding another jump implementation.
For skill energy, a small external helper first refilled the actual cooldown fields and then intercepted
the native setter's incoming value so its normal HUD notification also remained correct.

Ghostrunner is single-player, but Kill Run and community speedrun boards rank times. Keep the double jump
and the energy helper out of any run you post or compare.

The Lua source, memory reader, process controller and local launcher are not included in this note. This
is a field report of the observed symbols, layout, correction and verification; it is not a portable
trainer package.

## How the game works

### Double jump belongs to PlayerCharacter

The relevant reflected field is `/Script/Ghostrunner.PlayerCharacter.bCanDoubleJump`, not a property of
`JumpComponent`. The live pawn was a `BP_PlayerCharacter_C` instance. Observed values included
`FirstJumpVelocity = 1100`, `SecondJumpVelocity = 1100` and `JumpCounter = 0` while grounded.

The flag was already true when inspected. The human then jumped, released Space, pressed it again in
mid-air, and confirmed a second jump. This verifies the existing mod's behavior on the tested build; it
does not establish that changing generic `Character.JumpMaxCount` is an equivalent implementation.

The original session found `EJumpType` names including `FirstJump`, `SecondJump`, `SuperJump`,
`KunaiJump` and `HelJump`, then scanned **3733 loaded UClasses** to locate the owner of the flag.
`JumpComponent` existed but did not own it. Finding a name in the executable was a clue; reflection and
an actual second jump established the working route.

The final Lua script starts a two-second `LoopAsync` timer, but schedules object discovery and writes
inside `ExecuteInGameThread`. It resolves the owner class, validates the reflected property, enumerates
instances while excluding class defaults and archetypes, and calls
`ImportText("true", prop:ContainerPtrToValuePtr(obj), 0, obj)`. It re-enumerates instances rather than
retaining a pawn obtained from an earlier hook callback. The timer is intended to cover respawns and
travel; repeated level transitions were not independently stress-tested. UE4SS builds after 3.0.1
deprecate `LoopAsync` in favour of `LoopInGameThreadWithDelay`, which runs the callback on the game thread.

### Double-jump investigation: eleven revisions

The original journal records these outcomes. The causes are diagnoses from that session's logs and
code changes; they should not be read as universal UE4SS behavior across versions.

| Revision | Attempt | Observed result and diagnosis |
|---|---|---|
| v1 | `LoopAsync` calls `FindFirstOf("Character")`, then uses a delayed pawn callback | Access violation; UObject work was performed off the game thread and a pawn was retained across a delay. |
| v2 | One attempt inside `PlayerController:ClientRestart` | No crash, no effect; the pawn was not valid yet and the one-shot stopped retrying. |
| v3 | Hook `PlayerController:PlayerTick` | Hook registration threw because the target was not a UFUNCTION; the Lua error stopped the remaining chunk. |
| v4 | Schedule work on a pawn retained from `ClientRestart` | Crashed; the retained hook-parameter wrapper was diagnosed as invalid when used later. |
| v5 | Observe new movement components and hook `Character:Jump` | Partial information; no jump-hook callbacks were observed in the tested gameplay. |
| v6 | Reflect on new `ActorComponent` objects during level load | Crashed on `FAsyncLoadingThread`; the callback was not a safe place for this reflection work. |
| v7 | Read `pawn.JumpComponent`, then call `:get()` | Crashed on the menu pawn; the missing property yielded placeholder userdata rather than the expected component. |
| v8 | `FindFirstOf("JumpComponent")` when no instance was available | Crashed in this test; the journal did not establish a version-independent cause. |
| v9 | `Reflection():GetProperty()` and `IsValid()` | Ran without the earlier crashes; established that `JumpComponent` did not own the flag. |
| v10 | Scan loaded UClasses for the property | Found `/Script/Ghostrunner.PlayerCharacter` as the owner. |
| v11 | Re-enumerate instances and import `true` every two seconds on the game thread | The log reported one patched player, and the human confirmed a second jump in a real level. |

Three changes made the investigation productive:

1. Use the shipping executable's reflected names to identify candidate state, then verify ownership at
   runtime instead of assuming that a nearby class name owns it.
2. Ask which loaded class has the property. The one-time scan removed the need to guess between the
   character, movement component and jump component.
3. Read UE4SS's own `Mods/ConsoleCommandsMod/Scripts/set.lua`. Its path is
   `Class:Reflection():GetProperty(name)` → `Property:IsValid()` → `Property:ImportText(...)`.
   That supplied the checked property API used by the working script. It still requires correct
   threading and valid objects; Lua `pcall` does not catch native access violations.

### Sword energy is represented by per-skill cooldowns

`PlayerCharacter.SwordSkillsRef` points to the current `SwordSkills` component. Its standard slots include
`FurrashuSkill`, `NamiSkill`, `ShirudoSkill`, `JishinSkill` and `ForcePushSkill`.

The initialized skills inherit `BaseSwordSkill`, which exposes `MaxCooldown` and `CurrentCooldown`.
In this session, `MaxCooldown` was **400**. The selected **Tempest** ability, labelled **风暴** in the HUD,
was `ForcePushSkill`; one diagnostic read found a remaining cooldown of about **213**. A zero cooldown
means ready. `JishinSkill` was null and was skipped.

Useful reflected offsets for this image, to cross-check against a fresh dump:

| Owner | Field | Offset |
|---|---|---|
| `PlayerCharacter` | `bCanDoubleJump` | `0x854` |
| `PlayerCharacter` | `SwordSkillsRef` | `0xDA0` |
| `SwordSkills` | `FurrashuSkill`, `NamiSkill`, `ShirudoSkill` | `0xB8`, `0xC0`, `0xC8` |
| `SwordSkills` | `JishinSkill`, `ForcePushSkill` | `0xD0`, `0xD8` |
| `SwordSkills` | `CurrentSkillRef` | `0x118` |
| `BaseSwordSkill` | `MaxCooldown`, `CurrentCooldown` | `0xE4`, `0xF0` |

Resolve names and property types first. The helper required both cooldown properties to be reflected
four-byte floats and validated that the skill component's player references matched the possessed pawn.

### A raw refill and a HUD update are different observations

The first implementation held `CurrentCooldown` at zero every 50 ms. It recorded **16 refill writes**
with successful readback; this is a count of field writes, not necessarily 16 ability activations. The
human confirmed repeated casts but reported that the displayed energy meter did not stay full.

Inspection of native `BaseSwordSkill.SetCooldown` explained the mismatch. That method stores the new
cooldown and later broadcasts a clamped fraction equivalent to **1 - CurrentCooldown / MaxCooldown**.
Writing the float externally skips the notification. Actual readiness and the visible meter therefore
need separate verification.

For the tested image, the native setter begins at RVA **0x14051D0**. At RVA **0x14051DF**, it saves the
incoming float argument with `movaps xmm7, xmm1` (expected bytes **0F 28 F9**). The temporary replacement
was `xorps xmm7, xmm7` (**0F 57 FF**), also three bytes. The setter then uses zero while retaining the
original downstream update and HUD-broadcast path. A subsequent captured gameplay frame showed the
selected skill's meter fully lit.

The bytes were changed only in the process, with the exact executable hash and original bytes checked
first. They were restored when disabling the helper. No executable on disk was patched.

## Build steps

### Double jump through the loader API

1. Back up saves and configuration. In the original setup, UE4SS was placed next to the shipping
   executable under `Ghostrunner/Binaries/Win64`; it was already present for the Codex retest.
2. Place the Lua mod under `Mods/DoubleJump/Scripts/main.lua` and enable `DoubleJump : 1` in `Mods/mods.txt`.
3. Resolve the native owner class and `bCanDoubleJump` through reflection. Validate the property before
   obtaining a value pointer; exclude class defaults and archetypes from the instance query.
4. Use a timer only to schedule `ExecuteInGameThread`. Inside that callback, enumerate current instances
   and import `true` through the validated property. Do not carry a hook-parameter wrapper across ticks.
5. In a real level, check the loader's patched-instance log, then jump, release Space, and press it again
   in mid-air. A registration-success message alone does not establish that an input hook is called.

The original session's successful log was:

```text
owner: Class /Script/Ghostrunner.PlayerCharacter
scanned 3733 classes, 94 character/player/jump candidates
patched bCanDoubleJump=true on 1 instance(s)
```

The corresponding script remains local; this note records its implementation rather than distributing
the loader or game content. Tuning `SecondJumpVelocity` and `InitialCoyoteTime` was not tested.

### Infinite skill energy and HUD synchronization

1. Identify the PID and executable behind the actual game window. Hash that executable, record the
   build, and back up saves and configuration before gameplay tests.
2. Inspect the loaded reflection data. Find the native `PlayerCharacter`, `SwordSkills` and
   `BaseSwordSkill` classes and their properties, rather than relying on the names of arbitrary instances.
3. Resolve the current pawn through its player controller's `Pawn` reference. Validate its UObject
   registry entry and then its `SwordSkillsRef`. Exclude class defaults, archetypes, destroyed objects and
   stale addresses. Check that the component's `PlayerPtr` and `PlayerRef` match this pawn.
4. For a double-jump investigation, inspect the native flag and test its behavior before adding another
   jump system. The existing loader-based flag change already worked here. Loader-side UObject writes
   and reflected function calls should run through the game thread.
5. For unlimited energy on this exact image, verify the setter instruction above before changing its
   saved float argument to zero. The helper briefly suspended the selected process while writing the
   three bytes, read them back, flushed the instruction cache, restored page protection and resumed the
   process. Disable restores the original instruction. Do not call the setter from an arbitrary remote
   thread merely to refresh the HUD.
6. The helper also checked initialized standard skill slots every 50 ms and refilled nonzero cooldowns.
   Before each field write it revalidated possession, component ownership, the skill's registry identity
   and its float layout. Null slots were skipped. Re-resolve the binding after possession changes.
7. Test the selected ability repeatedly after each action finishes. Check readiness, the actual cooldown
   and the HUD separately. Disable and read back the original setter instruction before treating the
   temporary patch as reversible.

For a new build, repeat the reflection and function analysis. The hash gate should fail closed rather
than applying the old RVA to a different executable.

## Verification

- **Double jump:** inspected the current pawn's native flag and jump values; the human confirmed a second
  upward jump after releasing and pressing Space again in mid-air. This independently retested the
  behavior reported by the original journal. A later read-only check after a game restart again found
  `bCanDoubleJump = true`, both jump velocities at 1100 and generic `JumpMaxCount = 1`; this later snapshot
  was a flag check, not another behavioral jump test.
- **Energy:** the human confirmed consecutive Tempest casts after the first refill implementation.
  Instrumentation recorded 16 nonzero-to-zero cooldown writes with successful readback.
- **HUD:** the human's report exposed the stale-meter problem. After correcting the native setter input,
  a captured frame from active gameplay showed a full lower-left meter. This was a visual check by the
  agent, not a second explicit human confirmation of the HUD correction.
- **Energy test runtime:** the setter patch was active, the four initialized standard skill slots read
  zero cooldown, and the helper reported no error. This describes that process's final test snapshot;
  the process-only patch does not establish automatic enablement after a later game restart.
- **Disable:** the original three instruction bytes were read back after stopping the helper. The helper
  was then enabled again and the replacement bytes were verified.

![Full skill meter in active Ghostrunner gameplay after the native update correction](media/infinite-skill-energy-full-hud.png)

**Not verified:** other game builds or storefronts, other abilities individually, Hel/DLC behavior,
repeated level transitions under the final helper, long stress runs, automatic exit cleanup after closing
the game, or normal energy spending during an extended disabled session. Ghostrunner has no multiplayer. Whether
a timed mode uploads results while the mod or the patch is active was not checked, so keep modded runs
off leaderboards (see Route and why).

## Gotchas

1. **Missing Lua properties looked like objects.** **Cause:** the original session received placeholder
   userdata from `obj.MissingProperty`; calling `:get()` on it led to a native crash. **Fix:** resolve and
   validate the reflected property before using its value pointer. `pcall` catches Lua errors, not
   native access violations.
2. **Object callbacks and hook arguments outlived their safe context.** **Cause:** some new-object
   callbacks ran during asynchronous loading, and retained hook wrappers were later invalid.
   **Fix:** keep UObject work on the game thread, acquire current instances there and validate them.
3. **Hook registration succeeded or failed for reasons unrelated to gameplay.** **Cause:** `PlayerTick`
   was not a UFUNCTION, while `Character:Jump` registered but produced no callbacks in this test.
   **Fix:** guard registration errors and verify actual callback activity before building on a hook.
4. **The first pawn or movement component was not the player.** **Cause:** menu and spectator objects
   existed before the playable character. **Fix:** verify class ownership and possession, not just the
   first object whose name resembles a character.
5. **Automated focus failed while screenshots worked.** **Cause:** the original borderless-fullscreen
   session hit Windows' foreground lock. **Fix:** let the human navigate in that session and read
   captures/logs; do not treat a successful focus request as proof that later input reached the game.
6. **A previously valid pawn address started returning nonsense.** **Cause:** the player object was
   destroyed/reallocated during play. **Fix:** follow the controller's current `Pawn` reference and
   validate registry identity and possession again before a write; do not retain an instance address
   across respawns merely because it was valid in an earlier snapshot.
7. **Unlimited casting worked while the meter looked depleted.** **Cause:** external cooldown writes
   bypassed `SetCooldown`'s UI notification. **Fix:** preserve the native setter and broadcast path while
   forcing its cooldown input to zero; verify the actual ability and the HUD independently.
8. **The app label pointed at a different installation folder.** **Cause:** display metadata was not a
   reliable source of the running executable's path. **Fix:** use the window/process identity. In this
   case the two candidate executables had identical hashes, but only one shipping game process was active.
9. **A named skill slot contained no object.** **Cause:** not every declared slot was initialized in the
   current mode. **Fix:** skip null slots; `JishinSkill` being absent was not a reason to dereference it or
   fail the remaining skill checks.
10. **Generic Unreal jump settings suggested the wrong starting point.** **Cause:** this game exposes its
   own player-specific jump state. **Fix:** inspect `PlayerCharacter.bCanDoubleJump`, `SecondJumpVelocity`
   and `JumpCounter`; do not infer behavior from `Character.JumpMaxCount` alone.

## Assets and credits

The image is a screenshot of the locally running game. No game binaries, extracted assets, save files,
decompiled code dumps or local account paths are included.

WorkBuddy AI (DeepSeek V4.1) authored the original double-jump implementation, journal and field note,
previously submitted by `linlinseven7` in PR #359. Codex (GPT-6) incorporated that history, independently
retested the installed mod, and wrote the external energy helper and its process guards. The human
confirmed the actual second jump and repeated Tempest casts.

UE4SS supplied the mod runtime, reflection API and bundled console-command reference.
`universal-modder` supplied scan, backup, capture and knowledge-base checks. Runtime mod/helper source
and full private logs are outside this contribution.

## Open questions

- Re-find the native setter and validate the layout on other Ghostrunner builds.
- Test whether the native jump flag survives travel without the Lua re-apply loop, and tune jump
  velocity only with a separate in-game test. Other named jump variants were not implemented.
- Test every initialized ability and Hel/DLC modes independently before claiming support for them.
- Exercise repeated deaths, map travel, game exit and reattachment as dedicated lifecycle tests.
