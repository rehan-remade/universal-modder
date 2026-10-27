---
kind: technique
title: "Crysis Remastered data: paks, CryEngine 2 .chr 0x745, nanosuit shader modes and suit values"
game: "Crysis Remastered"
games_also: []
game_version: "Steam appid 1715130, files on disk 2026-10-17 (Bin64\\CrysisRemastered.exe 34,582,872 bytes, SHA-256 336c95e1c2d1...)"
platform: windows
engine: cryengine
route: asset-only
tools: ["Python 3.12 (uv), stdlib zipfile/struct + numpy + Pillow", "ffmpeg (MPEG-1 Layer II decode)", "Blender 5.1 (glTF import check)", "cgf-converter 2.0.0 (tried, see Gotcha 3)", "Ghidra 12 (exe section check only)", "um win (WinDrive scanmode) for console input"]
anti_cheat: "none (single player). The exe is wrapped in Steam DRM with an encrypted .text; it was not unpacked or modified. Values come from shipped plain-text files and from the running game's console"
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["ovROG"]
date: 2026-10-18
links: ["https://github.com/Markemp/Cryengine-Converter"]
tags: [cryengine2, crysis, crysis-remastered, pak, zip, chr, cgf, cdf, mtl, chunk-file, skinning, morph-targets, gltf, split-dds, fsb4, fmod, cfx, shaders, nanosuit, cvars, console, lua]
---

# Crysis Remastered data: paks, CryEngine 2 .chr 0x745, nanosuit shader modes and suit values

> How to read Crysis Remastered's own files offline, from your own Steam install: the `.pak` archives, the
> CryEngine 2 skinned-model chunk files (`.chr`, version 0x745) with bones, skin weights and facial morphs, split
> DDS textures, the FSB4 sound banks and suit voice lines, how the nanosuit's mode looks are made (shader passes in
> `Cloth.cfx`, not textures), and the suit's balance numbers from the shipped cfg/Lua and the running game's
> console. Use it when you want the nanosuit (or any Crysis character, sound or texture) as source data for a mod,
> a converter or a port, without touching the DRM-wrapped exe.

## When to use it
- You want a Crysis Remastered character model as glTF (skinned, with UVs, materials and selected facial morphs).
- You need the suit voice lines, suit SFX or HUD icons as WAV/PNG.
- You want the nanosuit's mode looks (strength red, speed yellow, armor metallic, cloak) on an engine that can't run
  CryEngine shaders, so you have to bake them.
- You need the suit's numbers (energy, recharge, armor absorption, cloak and sprint costs).

Everything here reads files from your own install and writes outside the game folder. Nothing extracted may be
redistributed; a tool built on this should extract at install time from the player's own copy.

## How

### Install layout
- `Bin64\CrysisRemastered.exe` (x64, 34.6 MB) is the only binary; CryGame is linked into it. Sections are
  `.text .rdata .data .pdata _RDATA .rsrc .reloc .bind`; the entry point is in `.bind` (Steam DRM). See Gotcha 5.
- `Game\*.pak` and `Game\Localized\<language>.pak` hold the data. `Engine\Config\*.cfg`, `Game\Config\diff_*.cfg`
  and `Game\Levels\**\*.cfg` are loose plain-text cvar files.
- Where things are (all verified on the 2026-10-17 Steam files):

  | What | Pak | Path inside |
  |---|---|---|
  | Lua scripts | `scripts.pak` | `scripts/...` (GameRules, Entities/actor, Entities/Items/XML) |
  | FP nanosuit arms | `objectsw.pak` | `objects/weapons/Arms_Global/arms_nanosuit_us.chr` (+ `.mtl` and per-mode `.mtl`) |
  | Nomad body | `objectsch.pak` | `objects/characters/Human/US/NanoSuit/NanoSuit_us.chr`, `NanoSuit_Helm_simple.chr`, `nanosuit_us.cdf` |
  | Skeleton | `objectsch.pak` | `objects/characters/human/generic/skeleton_male.chr` |
  | Prophet | `objectsch.pak` | `objects/characters/Human/story/Laurence_Barnes/*.cdf`, `objects/characters/Heads/Story/Laurence_Barnes/Barnes.chr`, `NanoSuit_Helm_neck_Barnes.chr`, `objects/characters/Heads/eyes/Eye_generic_04.cgf` |
  | Suit voice | `Localized/<lang>.pak` | `languages/dialog/suit/male\|female/suit_*.mp2` |
  | Suit / menu SFX | `sounds.pak` | `sounds/interface/interface_combined.fsb` + `interface.fev` |
  | HUD icons, sprites | `textures.pak` | `textures/HUD/HUD_QuickMenu_{Armour,Strength,Speed,Cloak}`, `textures/Sprites/...` |
  | Suit shader | (engine shaders) | `Engine\Shaders\HWScripts\CryFX\Cloth.cfx` |

### Paks
Plain zip, deflate. The central directory stores `/` but each local header stores `\`, so Python's `zipfile`
rejects every member (Gotcha 1). Index members by name with `\` turned into `/` and lowercased, and on the
mismatch error retry the read with the backslash form of the name. Paks over 700 MB were skipped and not checked
(Warhead's `level.pak` files use a non-standard method 6, see the Warhead note under Seen in).

### Chunk files (`.chr`, `.cgf`), version 0x745
All little-endian.
- **File header:** `"CryTek\0\0"`, u32 file type `0xFFFF0000`, u32 version `0x745`, u32 chunk table offset.
- **Chunk table:** u32 count, then 20-byte entries `{u32 type, u32 version, u32 offset, u32 id, u32 size}`.
  A v0x800 chunk repeats the first 16 bytes of its entry at its offset; its data follows. Detect that by checking
  whether the first u32 at the offset equals the type.
- Chunks used, each version 0x800:

  | Type | Chunk | Layout |
  |---|---|---|
  | `0xCCCC0000` | Mesh | i32 flags, flags2, nVerts, nIndices, nSubsets, subsetsChunkId, vertAnimChunkId; i32[16] stream chunk ids, indexed by stream type; i32[4] physics chunk ids; f32[3] bbox min, f32[3] bbox max |
  | `0xCCCC0016` | DataStream | u32 flags, type, count, elemSize, 2 reserved; then `count × elemSize` bytes. Types: 0 positions f32×3, 1 normals f32×3, 2 UVs f32×2, 3 colours u8×4, 5 indices u16 or u32 (by elemSize), 6 tangents, 8 shape deformation, 9 bone mapping |
  | `0xCCCC0017` | MeshSubsets | i32 flags, count, 2 reserved; `count × 36` bytes `{i32 firstIndex, numIndices, firstVertex, numVertices, matId; f32 radius; f32[3] center}`; if `flags & 2`, then per subset `{i32 n, u16 boneIds[128]}` (260 bytes) |
  | `0xACDC0000` | CompiledBones | 32 reserved bytes, then 584-byte bones: u32 controllerId @0, 2 × 104-byte physics @4, f32 mass @212, Matrix34 world→bone @216, Matrix34 bone→world @264 (row-major 3×4), char name[256] @312, i32 limbId @568, i32 parent offset @572 (relative, in bones; 0 = root), u32 numChildren @576, i32 children offset @580 |
  | `0xCCCC0014` | MtlName | flags, flags2, char name[128] @8, physType @136, i32 nSubMtls @140, i32 subMtl chunk ids @144 |
  | `0xACDC0002` | CompiledMorphTargets (also 0x801) | u32 count; per target `{u32 meshId, nameLen, nInt, nExt}`, name (e.g. `#Jaw_dropper_01`), `nInt × {u32 vertex, f32 delta[3]}`, `nExt × {u32 vertex, f32 delta[3]}` |

- **Skin weights.** Bone mapping is 8 bytes (u8×4 ids + u8×4 weights) or 12 bytes (u16×4 ids + u8×4 weights).
  The ids are **local to the subset's bone table** (MeshSubsets flag 2), not skeleton indices (Gotcha 2). Map
  each vertex through the table of the subset whose vertex range contains it, and divide the u8 weights by
  their sum.
- **Morphs.** The "ext" list indexes render vertices and holds offsets from the bind pose; that is the list to
  use. A parse that ends exactly at the chunk's end is a good check.
- **Materials.** The first MtlName chunk is the library. A subset's `matId` indexes its sub-material list, which
  is the order of `<SubMaterials>` in the `.mtl` XML. Sub-materials with `Shader="Nodraw"` are helpers; drop them.
- **Coordinates.** CryEngine is Z-up. For glTF, map `(x, y, z) → (x, z, −y)`; Blender's importer maps it back to
  the original Crysis coordinates. Joint locals are `parentB2W⁻¹ · B2W`; inverse bind matrices were taken as the
  rigid inverse of bone→world (the stored world→bone was not used, see Gotcha 4).
- **`.cdf`** (XML CharacterDefinition) assembles a character. `CA_BONE` attachments give `BoneName`, plus
  `Position` and `Rotation` (w, x, y, z) as a model-space bind transform; a static `.cgf` (same Mesh/DataStream
  chunks, no bones) is placed there and rigidly skinned to that bone.
- **What the files contain:**

  | File | Bones | Vertices / triangles | Notes |
  |---|---|---|---|
  | `arms_nanosuit_us.chr` | 59 (custom, FP pose) | 4154 / 6904 | DXT5 diffuse 8192² |
  | `NanoSuit_us.chr` | 74 (Bip01) | 6015 / 9219 | DXT5 diffuse 8192×4096 |
  | `NanoSuit_Helm_simple.chr` | | 2575 v | `nanosuit_us.cdf` = body + this helmet on `skeleton_male.chr` |
  | `Barnes.chr` (Prophet's head) | only Spine3 / Head | | 89 facial morph targets, no face bones |

  `Laurence_Barnes.cdf` = suit body + `Barnes.chr` + `NanoSuit_Helm_neck_Barnes.chr` + two `Eye_generic_04.cgf`
  attached on `Bip01 Head`. The face only moves by morphs; usable ones are `Jaw_dropper_*` and
  `Brow_*_raiser_*`, and a bone-driven face can derive jaw and brow weights from them.
- **Material hints.** Diffuse alpha is a gloss mask, not opacity (Gotcha 6). Real alpha: teeth alpha test
  0.723, eyeball alpha test 0.49, lashes blended. The iris is tinted by `PublicParams IrisColor` when the
  material's `StringGenMask` contains `IRIS`. The suit diffuse is very dark (mean 38/255); the relief lives in
  the `_ddn` normal map.

### Split DDS textures
A texture is stored in parts: `<name>.dds` (or `.dds.0`) holds the 128-byte DDS header plus the smallest mips;
`<name>.dds.1` … `.dds.N` hold the bigger mips, with `.dds.N` being mip 0. A standard DDS is the header, then
parts N, N−1 … 1, then the rest of the first part after its header. Check the joined size against the sum of
the mip sizes. Diffuse and spec are DXT5, `_ddn` is DXT1, up to 8192².

### Sounds
- **Voice lines** are raw MPEG-1 Layer II streams (`.mp2`, 44.1 kHz stereo, 96 kbit/s); ffmpeg decodes them
  directly. Mode lines are `suit_maximum_armor`, `suit_maximum_speed`, `suit_maximum_strength`, and
  `suit_modification_engaged` for the cloak (Gotcha 8). The only energy line is `suit_energy_critical`.
- **`interface_combined.fsb`** is an FMOD FSB4 bank: a 48-byte header (`"FSB4"`, sample count, sample-header
  size, data size, version, mode, ...), then one variable-size header per sample (u16 size, name, sample count,
  compressed size, loop start/end, mode, frequency, channels at +62). Sample data starts after the headers and
  each sample is 32-byte aligned. Every sample is MPEG-1 Layer II (mode 0x40200). Walk the MPEG frame headers and
  keep only whole frames before decoding, so the alignment padding is dropped. Sample names are cut to 29
  characters (Gotcha 9). `interface.fev` maps FMOD events (`suit:suit_armor_activate`, `suit:suit_strength_punch`
  ...) to these sample names.

### Nanosuit mode looks are shader passes
There are no per-mode suit textures. Each mode has its own `.mtl` next to the model (`nanosuit_us` is the default
and is what armor mode shows in Crysis 1; then `_strength`, `_speed`, `_cloak`, and separately `_invulnerability`).
They keep the same textures and switch on `%NANOSUIT_EFFECTS` in `Cloth.cfx` through `StringGenMask`. That flag
adds:
- an additive pass of moving energy bands: a sine of the object-space position (lightly offset by the bump
  normal) scrolling over time, sharpened with a power and multiplied by fresnel, a colour and the **diffuse
  alpha**, so it only shows on the armour plates. Its parameters are `SparksColor`, `SparksMultiplier`,
  `SparksPow`, `SparksPhase` and `SparksFrequency` in the material's `PublicParams` (red for strength, yellow for
  speed);
- a metallic environment reflection scaled by `MetallicAmount`, fresnel and diffuse alpha, which is non-zero only
  in `_invulnerability`.

Cloak mode instead darkens the material (`Diffuse` 0.282) and the engine draws its cloak layer on top. To get the
looks without CryEngine, bake them per texel: rasterise each triangle's object-space position into UV space
(keeping each sub-material's own Sparks parameters), evaluate the band term at one moment and as a time average,
replace fresnel by its hemisphere average (`FresnelBias + FresnelScale / (FresnelPower + 1)`), and add it onto the
diffuse. Armor and cloak have to be emulated (a metallic sheen with an assumed environment colour; a cool
blue-grey tint), since their real look comes from environment maps and the cloak layer.

### Suit values from cfg, Lua and the console
The suit cvars are registered in code with their defaults, and that code is encrypted on disk (Gotcha 5). The
plain-text cfg files override some of them at start-up or level load; the rest keep their code defaults, which
only the running game shows. Both sets were read from the running game's console (below), and every cfg-set
value matched its file; the difficulty cfgs were only checked on Easy (Verification). Read from the shipped files:

| Value | Source |
|---|---|
| Max suit energy 200 | `scripts/GameRules/SinglePlayer.lua` (`suitMaxEnergy = 200.0`, with a comment to keep it in step with the suit) |
| Player health 200 | `g_playerHealthValue` in every `Game\Config\diff_*.cfg` |
| Energy: full recharge in 4 s (also in armor, standing or moving) after a 2.5 s delay | `g_playerSuitEnergyRechargeTime*`, `g_playerSuitEnergyRechargeDelay` in `Engine\Config\common.cfg` |
| Health: full regen in 6 s after a 5 s delay | `g_playerSuitHealthRegenTime`, `g_playerSuitHealthRegenDelay` in `common.cfg` |
| Armor: a full bar soaks 125 HP (1.6 energy per HP); at least 30% of every hit is absorbed, even at 0 energy; armor mode drains 4 energy/s | `g_suitArmorHealthValue`, `g_suitArmorModeEnergyDrain` in `common.cfg`; the absorption rule in `SinglePlayer.lua` (mode 3 = armor) |
| Speed sprint: 24 energy/s, ×3 speed (×3 on low energy, ×1.8 when empty), ramp 3/s. Fleet sets 20 energy/s and ×2.5 / ×2.5 / ×1.1, which are the code defaults apart from the energy (22) | `g_suitSpeedEnergyConsumption`, `g_suitSprintMultiplier_speedMode_*`, `g_suitSprintAcceleration` in `Game\Levels\LevelDefaults.cfg` (applied on every level load) and `Levels\fleet\level.cfg` |
| Power melee ×1.4 (full and low energy alike) | `g_suitPowerMeleeScaleDamageWhenFullEnergy` / `...LowEnergy` in `common.cfg` |
| Cloak: `cloakEnergyCost` 10 for the player's cloak type 1; how that becomes energy per second is an open question | `cloakEnergyCost` in `scripts/Entities/actor/BasicActor.lua`; the player picks type 1 in `player.lua` |
| Cloak energy drained per damage taken: 33 (Normal, Hard), 1 (Easy), 50 (Delta) | `g_suitCloakEnergyDrainWhenDamaged` in `diff_*.cfg`; its help text says energy per point of damage (see Open questions) |
| AI cloak detection: Easy 2/4, Normal 2.5/4.5, Hard 3/5, Delta 3/5.5 m | `ai_CloakMinDist` / `ai_CloakMaxDist` in `diff_*.cfg` |
| Base punch: 245 damage (player), 30 for AI | `scripts/Entities/Items/XML/Weapons/Fists.xml` |

The cvar names and their help texts are plain strings in `.rdata`, which tells you what exists even where no
value is set. Remastered has a `ClassicSuit` variant of several cvars (`cl_classicSuit = 0` in the default
profile picks the new controls; help "Classic suit controls").

#### Reading cvars from the console
No file changes are needed. This is what worked:
1. With Steam running, start `Bin64\CrysisRemastered.exe -devmode` from your own install (Steam DRM runs as
   usual). The console wasn't tried without `-devmode`.
2. Open the console with `~`. The game reads keyboard input by scan code, so an agent has to send scan codes
   (WinDrive `scanmode on`, `~` = VK 0xC0 on a US layout, the key below Esc); virtual-key events are ignored
   (Gotcha 10). WinDrive drives the real keyboard, so ask the human first, and not while they're typing.
3. Type a cvar name and press Enter. The console and `Game.log` (install root) print `name = value [flags]`.
   Several names on one line separated by `;` all print, so about 70 cvars fit in 9 lines. `name ?` prints
   the help text. Read `Game.log` rather than screenshots.
4. Read twice: once in the main menu (code defaults plus `Engine\Config\common.cfg`) and once in a loaded
   level (`LevelDefaults.cfg`, the level's `level.cfg` and the difficulty cfg are applied by then, Gotcha 12).

Values that no cfg or Lua sets, so these are the code defaults. They were the same in the main menu and in a
level. Help texts are quoted short.

| Value | Cvar = value (help) |
|---|---|
| Power jump: force ×4.7, costs 20 energy (classic suit 70) | `g_suitPowerJumpForceMultiplier` = 4.7 ("upwards force multiplier ... in any suit mode"), `g_suitPowerJumpEnergyConsumption` = 20, `...Classic` = 70 |
| Power melee costs 20 energy | `g_suitPowerMeleeEnergyDrain` = 20 |
| Firing in strength mode costs 7 energy per shot | `g_suitRecoilEnergyCost` = 7 ("subtracted energy when weapon is fired in strength mode") |
| Cloak drain adjuster 0.73 | `g_suitCloakEnergyDrainAdjuster` = 0.73 ("multiplier for energy reduction in cloak mode"). How it combines with `cloakEnergyCost` 10 is not known (Open questions) |
| Sprint in strength, armor and cloak modes ×1.25 | `g_suitSprintMultiplier_strengthMode`, `_defenseMode`, `_cloakMode` = 1.25 |
| Speed-mode swimming ×2 (×0.9 when empty) | `g_suitSprintMultiplier_speedMode_swimmingGotFullEnergy` / `...GotLowEnergy` = 2, `...OutOfEnergy` = 0.9 |
| Normal jump while super-sprinting: extra force 2.5 forward, 1 up | `g_suitSpeedJumpExtraForceInViewDirection_Horizontal` = 2.5, `_Vertical` = 1 |
| Health regen while moving: 4 s (6 s standing); in armor mode 4 s standing and moving | `g_playerSuitHealthRegenTimeMoving` = 4, `g_playerSuitArmorModeHealthRegenTime` / `...Moving` = 4 |
| Swimming "dolphin" jumps (Shift+jump) in speed or strength mode cost 50 energy; ×1 base, ×2.5 sprinting | `pl_swimJumpSpeedCost`, `pl_swimJumpStrengthCost` = 50; `pl_swimJump*BaseMul` = 1, `pl_swimJump*SprintMul` = 2.5 |
| Zero-G: a dash costs 0.25, speed mode 0.15 (classic 0.5) | `pl_zeroGDashEnergyConsumption` = 0.25 ("percentage consumed when doing a dash"), `pl_zeroGSpeedModeEnergyConsumption` = 0.15, `...ClassicSuit` = 0.5. `Engine\Config\console*.cfg` set 0.07 on console platforms only |
| EMP field: suit stays off 10 s after leaving it | `g_empNanosuitDowntime` = 10 |
| Autoaim vs cloaked targets ×0.2; cloak fade speed 1 | `pl_aim_cloaked_multiplier` = 0.2, `ai_CloakIncrementMod` = 1 ("how fast cloak fades out") |
| AI with a nanosuit (the Korean nanosuit soldiers): energy recharge 10 s, health regen 33.3 s, 20 s in armor mode, strength melee ×0.4 | `g_AiSuitEnergyRechargeTime`, `g_AiSuitHealthRegenTime`, `g_AiSuitArmorModeHealthRegenTime`, `g_AiSuitStrengthMeleeMult` |
| Off by default: melee while sprinting, speed lean | `g_meleeWhileSprinting` = 0, `g_enableSpeedLean` = 0 |
| Strength scale 1 | `cl_strengthscale` = 1 ("nanosuit strength scale") |

Classic suit (`cl_classicSuit = 1`) values, also code defaults:

| Value | Cvar = value |
|---|---|
| Energy: full recharge in 10 s (also in armor, standing or moving) after a 1 s delay | `g_playerSuitEnergyRechargeTime*ClassicSuit` = 10, `g_playerSuitEnergyRechargeDelayClassicSuit` = 1 |
| Armor mode doesn't drain energy: −1, and a negative value makes the suit recharge instead (help text) | `g_suitArmorModeEnergyDrainClassicSuit` = −1 |
| Speed sprint 110 energy/s | `g_suitSpeedEnergyConsumptionClassicSuit` = 110 |
| Power jump 70 energy, zero-G speed mode 0.5 | see the table above |

Multiplayer variants (`...Multiplayer`): energy recharge 20 s, speed 50 energy/s, `g_mpSpeedRechargeDelay` = 1.

## Gotchas
1. **Python `zipfile` refuses every pak member** ("File name in directory ... and header ... differ").
   **Cause:** local headers store `\`, the central directory stores `/`. **Fix:** on that error, set the entry's
   `orig_filename` to the backslash form and read again; normalise names to `/` for lookups.
2. **Skinned mesh came out with weights on the wrong bones.** **Cause:** bone-mapping ids index the owning
   subset's 128-entry bone table, not the skeleton. **Fix:** find the subset whose vertex range holds the vertex
   and map ids through its table (only present when MeshSubsets `flags & 2`).
3. **cgf-converter 2.0.0 converts `arms_nanosuit_us.chr` but crashes on `NanoSuit_us.chr`** (an
   ArgumentOutOfRangeException inside its CompiledBones 0x800 reader), and drops UVs unless a material file is
   passed (`-mtl`, with `-objectdir` pointing at the extracted tree). **Fix:** a small own reader for the chunks
   above, about 450 lines of pure Python with a glTF writer.
4. **Inverse bind matrices.** The bone→world matrix was used, and its rigid inverse taken; the stored world→bone
   matrix was not relied on. The Warhead note found W2B and B2W are not always exact inverses, so keep the
   donor's matrices unchanged if you write `.chr` files back.
5. **The exe on disk can't be disassembled for cvar defaults.** **Cause:** it is wrapped in Steam DRM: the entry
   point sits in `.bind`, `.text` is encrypted on disk (byte frequencies are flat across the first 26 MB, no normal
   x64 prologue patterns, and no references to the 90 suit cvar name strings in `.rdata`). **Fix:** leave the file
   as installed. Take the effective values from the shipped cfg/Lua, and read the code defaults from the running
   game's console (Reading cvars from the console). The code is readable in the running process, from memory or
   a private dump kept outside any repo (CONTRIBUTING, DRM-wrapped executables); that wasn't tried here.
6. **Holes or see-through patches in the converted suit.** **Cause:** diffuse alpha is a gloss/effect mask.
   **Fix:** drop alpha from the diffuse on export, except for the few materials with an `AlphaTest` or `Opacity`
   (teeth, eyeballs, lashes).
7. **No per-mode suit textures anywhere in the paks.** **Cause:** the looks are the `%NANOSUIT_EFFECTS` passes in
   `Cloth.cfx`, switched on by the mode `.mtl` files. **Fix:** bake them (see above) or recreate the shader in the
   target engine from the `PublicParams`.
8. **"Cloak engaged" is not called `suit_cloak_*`.** The line the game plays is `suit_modification_engaged`;
   `suit_full_cloak_off` exists but the game doesn't use it. The strength activate event
   (`suit:suit_strength_activate`) plays a blank sample, so take `suit_strength_activate_04` from the bank for a
   sound.
9. **An FSB4 sample isn't found by its full name.** **Cause:** names in the sample headers are cut to 29
   characters. **Fix:** match by prefix, or truncate your lookup names to 29 characters.
10. **The console doesn't open, or typed text doesn't arrive, when an agent drives the game.** **Cause:** the
    game reads the keyboard by scan code and ignores virtual-key events. **Fix:** send scan codes (WinDrive
    `scanmode on`, then `key 0xC0` for `~`, `type ...`, `key 0x0D`). `type` sends Unicode characters in either
    mode and the console takes them, so only `~` and Enter need scan codes. A human typing on the keyboard has
    no such problem.
11. **`Unknown command` for some names found in `.rdata`.** `g_playerSuitHealthRechargeTime`,
    `...HealthRechargeTimeMoving` and `g_AiSuitHealthRechargeTime` are in the exe's strings but aren't cvars.
    **Fix:** take names from the console's own reply; a name that prints `name = value` exists.
12. **Main-menu values differ from what the player gets.** **Cause:** `LevelDefaults.cfg`, the level's
    `level.cfg` and the difficulty cfg are applied when a level loads. In the menu `g_suitSpeedEnergyConsumption`
    is 22 and the speed multipliers 2.5 / 2.5 / 1.1; in a level they are 24 and 3 / 3 / 1.8. **Fix:** read the
    effective values in a loaded level; use the menu for code defaults.

## Seen in
- Related CryEngine 2 notes: [Warhead build 711 static analysis and level PAK method 6](../games/crysis-warhead/build-711-static-analysis-and-level-pak-method-6.md)
  and [Black Ops Zombies in Warhead](../games/crysis-warhead/black-ops-zombies-native-animation-and-runtime.md)
  (writing `.chr` files back).

## Verification
- **Reader:** parsed all three nanosuit `.chr`, `Barnes.chr`, `NanoSuit_Helm_neck_Barnes.chr` and
  `Eye_generic_04.cgf` with hard checks: each stream type matches its slot, parent indices are in range, morph
  vertex ids are below the vertex count, and the morph chunk parses to exactly its last byte. Counts match the
  table above.
- **glTF:** imported into Blender 5.1. Mesh, UVs, skeleton and weights looked right, and Prophet's head, helmet
  neck and eyes landed in place from the `.cdf` transforms.
- **Audio and textures:** every WAV was checked for duration, peak and RMS. Joined split DDS files matched their
  expected size; icons were looked at.
- **Mode bakes:** rendered on the model in Blender and checked by eye by a human.
- **Suit values (2026-10-21, same exe as above):** 67 cvars read from the console of the running game, with
  `-devmode`, once in the main menu and once after loading a save on Contact (`island`). The save was on Easy:
  `g_difficultyLevel` = 1, and `ai_CloakMinDist` / `MaxDist` 2 / 4 and `g_suitCloakEnergyDrainWhenDamaged` 1
  match `diff_easy.cfg`. In the level every value that a cfg sets matched the cfg (200, 4 / 4 / 4 / 2.5, 6 / 5,
  125, 4, 1.4 / 1.4, 24, 3 / 3 / 1.8, 3). The values no cfg sets were the same in the menu and in the level.
  Help texts were read with `name ?`. No file was changed and no cvar was set.
- **Not verified:**
  - Normal, Hard and Delta in the running game (a new game wasn't started, so the player's saves stayed as they
    were); their values above come from the cfg files only;
  - what the values do in play: nothing was measured (energy drain, jump height, sprint speed);
  - the inferred formulas (for example "recharge time = seconds for a full bar");
  - the console without `-devmode`;
  - any other chunk types or versions (CompiledBones other than 0x800, physics, `.cga`, `.caf` animations);
  - paks over 700 MB, and whether Remastered's level paks use the same method 6 as Warhead.

## Open questions
- `g_suitCloakEnergyDrainWhenDamaged`: its help text says "how much suit energy is drained for every point of
  damage taken when in cloak mode". At 33 on Normal, about 6 HP of damage would empty a full bar of 200, so a
  hit breaks the cloak almost at once. That reading fits the help text but wasn't measured in play.
- How `g_suitCloakEnergyDrainAdjuster` 0.73 combines with `cloakEnergyCost` 10 (for example 7.3 energy/s, or
  only while moving). In the original Crysis's Mod SDK (`NanoSuit.cpp`), the drain per second is
  `cloakEnergyCost × adjuster × (horizontal speed × 0.5)`, at least 1, and ×8 in free fall, so movement is the
  moving factor there. Whether Remastered kept that formula wasn't checked; timing a full bar in cloak, standing
  and moving, would settle it.
- Whether the speed multiplier ×3 replaces or stacks with the base `sprintMultiplier` 1.5 in `player.lua`. The
  help texts say "sprint speed multiplier when in ... mode", which suggests it replaces the base one; not
  measured.
- Whether the zero-G costs (0.25, 0.15) are fractions of the bar, as "percentage consumed" suggests.
- A standalone public release of the reader.
