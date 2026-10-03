---
kind: game
title: "Halo 3 weapons, Covenant, vehicles and maps ported into Minecraft from your own MCC install"
game: "Halo 3 (MCC)"
games_also: ["Minecraft Java Edition"]
game_version: "Halo: The Master Chief Collection, Steam app 976730, build 19905945 (Halo 3 cache type MccHalo3U13); Minecraft Java 1.21.4 + Fabric loader 0.19.3/0.19.5, Fabric API 0.119.4+1.21.4"
platform: windows
engine: native
route: loader-api
tools: ["Fabric Loom 1.18 (Mojang mappings)", "Reclaimer 2.1.1644 via pythonnet", "Reclaimer RMF importer 1.0.5 (its pure-Python reader)", "Assembly Halo3MCC plugin layouts", "vgmstream r2117", "ffmpeg"]
anti_cheat: "EasyAntiCheat on MCC; never launched or touched. The route only reads Halo's files on disk."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: ["daanishmufti"]
date: 2026-10-03
links: []
tags: [content-port, mashup, blam, reclaimer, pythonnet, fmod, fsb5, voxelize, maps, fabric, shields, vehicles]
---

# Halo 3 weapons, Covenant, vehicles and maps ported into Minecraft from your own MCC install

> A Fabric 1.21.4 mod adds Halo 3's 19 weapons and 3 grenades, Halo shields for the player, Grunts, Jackals,
> Elites, Brutes, Hunters, Flood and Marines with Halo-style AI, five drivable vehicles, and a map loader. The mod
> ships only code. A Python converter reads the user's own MCC install and produces a resource pack (real Halo 3
> models, rank-coloured textures, sounds), exact Halo 3 stats, and block versions of the multiplayer maps
> (Valhalla, Guardian, The Pit...). Verified in a dev client with a scripted autotest and in-game screenshots.

## Setup
- Windows 10 Pro 19045. MCC on Steam (D:\steam\...\Halo The Master Chief Collection), `halo3\maps\*.map` (42 files),
  `halo3\fmod\pc\sfx.fsb` (+ `sfx.fsb.info`).
- Minecraft: Fabric example mod branch `1.21.4`, Loom 1.18 (needs a **Java 25** JVM to run Gradle; the mod still
  targets Java 21), Mojang mappings.
- Reclaimer v2.1.1644 (MSI; needs the .NET 9 Desktop Runtime) and its `reclaimer_rmf_importer-1.0.5-windows_x64.zip`.
- Python 3.12 via `uv`, packages `pythonnet>=3.0.3`, `numpy`, `pillow`. vgmstream-cli r2117. ffmpeg from `um win setup`.
- The official Halo 3 Mod Tools (H3EK, Steam 1695791) were **not needed**: everything below reads the shipped
  `.map` files.

## Route and why
Pattern 1 of mashup-mods (port the content): Minecraft is the host with a normal Fabric mod; Halo is only a data
source. No IPC, no injection into an anti-cheat game, and shareable as code + converter. Passthrough (both games at
once) was rejected: MCC has EAC and a native engine, which is a lot of risk for "Halo stuff in Minecraft".

## How the game works (what we had to learn)
- **Two engines in one install.** `um scan` reports MCC as Unreal (that's the menu shell,
  `mcc-win64-shipping.exe`). Halo 3 itself is Blam gen3 in `halo3\halo3.dll` with cache files `halo3\maps\*.map`.
- **Reclaimer opens MCC Halo 3 maps headless.** `Reclaimer.Blam.Common.CacheFactory.ReadCacheFile(path)` gives an
  `MccHalo3.CacheFileU6` (type `MccHalo3U13`); `ContentFactory.TryGetGeometryContent(item, out provider)` works for
  `mode` (render models), `sbsp` and `scnr` tags; `provider.GetContent()` is a `Scene`;
  `Reclaimer.Geometry.GeometryExtensions.WriteRMF(scene, path)` writes RMF, which the RMF importer's `src/` package
  (plain Python, no Blender) reads.
- **Units and transforms.** RMF positions are already Halo world units (1 wu = 3.048 m; `scene.unit_scale` = 3048
  is mm per wu, don't multiply). Row-vector matrices: `pos @ mesh.vertex_transform @ permutation.transform`;
  `uv @ mesh.texture_transform` (Minecraft wants no V flip); bone world = `local_bone @ ... @ local_root`. Halo axes
  are X forward, Y left, Z up; `(x_mc, y_mc, z_mc) = (y, z, x)` is a pure rotation.
- **Skeleton.** Halo 3 biped bone names already read pelvis/spine/spine1/head/l_upperarm/l_forearm/l_hand/
  l_thigh/l_calf..., so procedural animation can target them directly. Bind pose: arms hang down but **elbows are
  bent ~90 degrees forward** (hands at about z = 0.5 blocks). Vehicles: wheels are `lf_tire/rf_tire/lb_tire/rb_tire`.
- **Materials.** Each mesh segment's material lists texture mappings with a usage (`diffuse`, `color_change`,
  `blend`, `self_illum`...). Diffuse alpha usually holds a specular mask. `color_change` (R channel) is the armour
  tint region: baking `diffuse * lerp(1, rank_colour, mask)` per rank gives correct Elite/Brute/Grunt rank colours.
- **Terrain.** BSP terrain shaders blend 2-4 diffuse layers by a blend map; mapping `blend_channel` 1/2/4/8 means
  R/G/B/A. Sampling the blend map at each triangle's UV (times the mapping's tiling) and picking the dominant
  layer gives grass, snow, rock and dirt in the right places.
- **Raw tag fields.** Reclaimer's typed tags don't cover weapon stats or scenario placements, but its translators
  do: tag block = `{int32 count, int32 pointer, int32 pad}`, address =
  `MetadataTranslator.GetAddress(PointerExpander.Expand(ptr))` (MCC Halo 3 expands `ptr << 2`), tag references are
  16 bytes with the tag index in the low 16 bits at +12. Field offsets come from Assembly's `Plugins/Halo3MCC/*.xml`
  (there is no Halo3MCC `jpt!.xml`; the Halo3 one matches). Useful ones: `scnr` Weapons 0x114 (0xA8), Weapon
  Palette 0x120 (0x10), Vehicles 0xE4 (0xA8), Vehicle Palette 0xF0, Equipment 0xFC (0x8C), Player Starting
  Locations 0x24C (0x18); `weap` Magazines 0x424 and Barrels 0x43C (rate, shots per fire, fire recovery, error
  angle in radians, projectile ref, heat per round), heat loss 0x1D4, zoom 0x31E/0x320; `proj` initial velocity
  0x23C, guided rate 0x250, impact/detonation damage refs 0x1F0/0x158; `jpt!` radius 0x0, damage 0x1C/0x20; `hlmt`
  New Damage Info 0x88 (body 0xC, shield 0x20, stun 0x2C, recharge 0x30); `char` Vitality Properties 0x78 (body,
  shield) with parent character at 0x4. Damage and vitality are in the same "Halo points" (MP Chief body 45,
  shield 70; AR bullet 7.5; BR 6; sniper 80).
- **Sounds.** Reclaimer's Halo 3 sound path expects Xbox XMA; MCC PC keeps Halo 3 effects in an FMOD FSB5 bank
  (`sfx.fsb`, 16,421 Vorbis samples with short names). `sfx.fsb.info` is 280-byte records in the same order with
  the original source path at +24 (`data\sound\weapons\assault_rifle\ar_fire\19103_b.aif`), which maps samples to
  sound tags exactly. vgmstream decodes them (subsong = index + 1).
- **Campaign vs MP.** Weapons, vehicles and the MP Chief/Elite are in MP maps (riverworld is enough). Grunt, Jackal,
  Brute and Marine models live in `030_outskirts`, Hunter in `040_voi`, Flood combat form in `050_floodvoi`. The
  third-person Energy Sword model isn't in MP maps; `fp_energy_blade` works as a held item.

## Build steps
1. Mod: Fabric 1.21.4 template, `org.gradle.java.home` = a JDK 25, `./gradlew build`.
2. Converter, run against a Minecraft game dir (`--instance`):
   `convert.py models` (31 models: per id, search MP then campaign maps for the `mode` tag, `WriteRMF`, write the
   scene's textures as DDS, read the RMF, rigid-skin each triangle to its dominant bone, write the mod's mesh format
   and PNGs into `resourcepacks/Halo3-Converted`); `convert.py stats` (raw tag fields -> `config/halo3mc/stats.json`);
   `convert.py sounds` (FSB -> mono OGG + `sounds.json`); `convert.py maps --maps riverworld,...` (scenario scene ->
   world-space triangles -> per-triangle block -> surface voxelization -> run-length `.h3vox`, plus spawns/weapons/
   vehicles from the raw scenario blocks).
3. In game: enable the resource pack, `/halo3 map load riverworld`.

## Verification
- Scripted in-game autotest (`-Dhalo3mc.autotest=all|weapons|vehicles|map|gallery|ai`) in a dev client that
  quick-plays into a flat world made by a self-halting dev server. The server side drives the trigger through the
  weapon state (no OS input), logs `[AUTOTEST] RESULT` lines, and asks the client to grab screenshots between frames.
- Results: all 19 weapons kill fresh targets with the converted stats; all 5 vehicles drive (Banshee climbs ~50
  blocks); Covenant and Marines target and kill each other; 11 maps build (Valhalla: 976x262x641 blocks before
  cropping, 1.14M solid). Screenshots checked for every model, rank colour, vehicle and map.
- Not verified: multiplayer (dedicated server + remote clients), long play sessions, Reclaimer on other MCC
  builds, campaign maps as playable levels.

## Gotchas
1. **Gradle fails resolving Loom 1.18.** **Cause:** Loom 1.18 requires a Java 25 JVM. **Fix:** point
   `org.gradle.java.home` at a JDK 25; keep `release = 21` for the mod.
2. **`System.Drawing.Common ... manifest definition does not match`** when loading Reclaimer through pythonnet.
   **Cause:** the WindowsDesktop framework's System.Drawing.Common 9.0 is in the TPA list; Reclaimer ships 10.0.
   **Fix:** load coreclr with a runtimeconfig naming only Microsoft.NETCore.App, and add Reclaimer's folder and
   `runtimes\win\lib\net9.0` to `sys.path`.
3. **`Failed to create Python type for Reclaimer.Drawing.DdsImage` (PresentationCore missing).** **Cause:**
   pythonnet reflects every member and DdsImage has WPF-typed ones. **Fix:** never return DdsImage to Python; compile
   a `System.Linq.Expressions` delegate that calls `IBitmap.ToDds(i).WriteToDisk(path)` inside .NET.
4. **`'ICacheFile' object has no attribute 'CreateReader'`.** **Cause:** pythonnet hands back the interface.
   **Fix:** `cache.__implementation__`.
5. **Models 3048x too big.** **Cause:** multiplying by `scene.unit_scale` (mm per wu). **Fix:** positions are
   already world units.
6. **Converted characters aim with forearms pointing at the sky.** **Cause:** Halo's bind pose has elbows bent
   forward. **Fix:** per-node rest rotations: upper arm to straight down, forearm aligned with the upper arm; animate
   on top.
7. **Holes in characters with Minecraft cutout rendering.** **Cause:** diffuse alpha is a specular mask. **Fix:**
   force alpha to 255 for `opaque` materials.
8. **Valhalla turned into a lake.** **Cause:** substring keyword matching ("river" in "riverworld"). **Fix:**
   match whole words of shader/texture names.
9. **Terrain one flat colour.** **Cause:** averaging the blend map instead of the layer textures. **Fix:** sample
   the blend map per triangle and pick the dominant layer.
10. **Construct converted to 2061x1998x1051 blocks.** **Cause:** the space backdrop is level geometry. **Fix:** crop
    to the box around the map's own spawns, weapons and vehicles plus a margin.
11. **Grenades exploded in mid-air with tag timers.** **Cause:** Halo 3 grenade timers start on bounce/rest, not on
    throw. **Fix:** keep throw fuses, import only blast damage and radius.
12. **Jackals got energy shields.** **Cause:** the Jackal `char` "shield vitality" is its gauntlet. **Fix:** model it
    as frontal armour.
13. **`um win shot` returns a pure white frame of the Minecraft (LWJGL) window, even by hwnd.** **Fix:** take
    screenshots inside the game (`Screenshot.grab` at the start of a client tick, when the main target still holds
    the last full frame including the HUD).
14. **Autotest steps never ran their first tick.** **Cause:** setting `stepStart = tick` on the transition tick.
    **Fix:** `stepStart = tick + 1`.

## Assets
All Halo assets are generated at the user's end from their own install (models, textures, sounds, maps). The mod's
built-in placeholders are original box models and pixel art. Character voices (Grunt panic, Elite roars) live in
the dialogue banks (`english.fsb` etc.) and weren't mapped; vanilla sounds stand in.

## Cost and time
One long session (about 8 hours wall-clock including two waits on the human approving installs).

## Open questions
- Map the dialogue banks for character voices; read `vehi` speed blocks for exact vehicle handling.
- Attach the Warthog's chaingun turret (separate `vehi`) at its marker; hide the Banshee pilot.
- Skeletal animation from Halo's `jmad` tags instead of procedural poses.
- Validate the converter on other MCC builds and on ODST / Reach caches (Reclaimer supports them).
