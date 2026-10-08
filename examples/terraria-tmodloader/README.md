# Terraria (tModLoader): Fal Arsenal

A tModLoader mod with five weapons, three enemies and a boss that aren't in vanilla Terraria. The
sprites were generated with fal (FLUX dev) and cut into Terraria's frame layout with `um sprite`. It
was ported from the mod behind the Terraria showcase videos (single player, tModLoader 2026.07 on
Terraria 1.4.4); the scripted scenes, RL agent and in-game recorder were taken out, and the recorder
and agent bridge are kept in `reference/` for what they teach.

**Weapons**
- **Homing Missile Launcher**: missiles steer to the nearest enemy, deal splash damage and blow small
  craters.
- **Tactical Nuke**: a warhead drops 60 tiles in front of you. Everything within ~50 tiles of ground zero
  dies (bosses too), the ground is vaporised into a crater with an ash rim, and a pixel-art fireball and
  mushroom cloud go up. The screen flashes and the camera pans over and back. The item isn't consumed.
- **Tesla Rifle**: hitscan chain lightning that hits the first enemy within 30 degrees of your aim, then
  jumps to up to 4 more for 15% less damage each time.
- **Singularity Launcher**: fires an orb that opens into a black hole for 2.5 s. It pulls in enemies and
  loose loot (bosses only a little), grinds anything close, then implodes for triple damage.
- **Orbital Strike**: locks on near the cursor (bosses first), then a beam from the sky sweeps onto the
  target for 2 s, burning everything under it and scorching a trench. The Drone Mothership can't move
  or dash while it's caught in the beam.

**Enemies** (they spawn on the surface now and then)
- **Scrap Drone**: circles and strafes above you and shoots lasers.
- **Neon Slime**: a glowing slime that uses the vanilla slime AI and spawns in daytime.
- **Mech Walker**: walks at you and hops over steps and gaps.

**Boss: Drone Mothership** (5200 life). Phase 1 circles high above you, launching Scrap Drones and
firing laser fans. Below half health it turns red, dashes at you and fires homing rockets. It has the
vanilla boss bar, music and messages, and drops gold, Souls of Flight, Hallowed Bars and Healing
Potions.

Explosions dig into the world, so try it in a spare world. Multiplayer isn't tested; the net code
follows vanilla's patterns (tile edits sent like vanilla explosives, the boss summoned through the
server).

## Install and build

1. Install tModLoader from Steam. It's free (app 1281930), and it has to be in your Steam library to
   start at all.
2. Copy `FalArsenal/` into your ModSources folder. tModLoader creates that folder, along with the
   `tModLoader.targets` file that `FalArsenal.csproj` imports, when you open Workshop > Develop Mods:
   - Windows: `Documents\My Games\Terraria\tModLoader\ModSources\`
   - Linux: `~/.local/share/Terraria/tModLoader/ModSources/`
   - macOS: `~/Library/Application Support/Terraria/tModLoader/ModSources/`
3. In the game, go to **Workshop > Develop Mods > FalArsenal > Build + Reload**. That builds the mod,
   enables it and reloads.

From the command line, all of these build a `.tmod` into `<save folder>/Mods` and enable it:

```
# from the tModLoader install folder, with the .NET runtime it installs on first start (no SDK needed)
.\dotnet\dotnet.exe tModLoader.dll -build "<ModSources>\FalArsenal"   # Windows (cmd or PowerShell)
dotnet tModLoader.dll -build "<ModSources>/FalArsenal"                 # any .NET 8 (Linux, WSL)

# in FalArsenal/, with the .NET 8 SDK (this is also what IDEs use)
dotnet build                                                           # inside ModSources/
dotnet build -p:TmlInstallDir="<tModLoader install folder>"            # anywhere else
```

Add `-tmlsavedirectory <dir>` to a `-build` command (or pass
`-p:ExtraBuildModFlags="-tmlsavedirectory <dir>"` to `dotnet build`) to write somewhere other than
your normal save folder.

## Getting the items

- Type `/arsenal` in chat to get one of each weapon, and `/mothership` to summon the boss near you.
- Or craft them at an Iron or Lead Anvil. The recipes are cheap on purpose:

| Item | Ingredients |
|---|---|
| Homing Missile Launcher | 8 Iron or Lead Bars, 10 Gel |
| Tactical Nuke | 12 Iron or Lead Bars, 5 Fallen Stars |
| Tesla Rifle | 8 Iron or Lead Bars, 3 Fallen Stars |
| Singularity Launcher | 8 Iron or Lead Bars, 2 Lenses, 3 Fallen Stars |
| Orbital Strike | 6 Iron or Lead Bars, 1 Lens, 5 Fallen Stars |

## How the art was made

`assets/make_art.sh` rebuilds every PNG in `FalArsenal/Assets` and `FalArsenal/icon.png`:

1. fal FLUX dev draws each object on a flat white background (1024x1024). The prompt is the object
   plus one shared style line: *16-bit pixel art game sprite in the style of Terraria, crisp dark
   outline, limited palette, centered, plain flat white background, no shadow, no text*.

   ```bash
   um fal run fal-ai/flux/dev "prompt=a single small guided missile seen from the side pointing right, red nose cone, white and grey body, small tail fins, flame at the back. <style>" \
     image_size=square_hd num_images:=1 num_inference_steps:=40 output_format=png --out gen --name missile
   ```

   It uses `um fal run` rather than `um fal image`, because the image recipe adds inputs meant for its
   default model. The ten drawings this mod shipped with are in `assets/gen/` (as `.jpg`, flux/dev's
   default format), and the script only calls fal (with `FAL_KEY`) for a file you delete. There's no
   fixed seed, so that call draws something new.

2. `um sprite` turns each drawing into the frames the mod uses:

   ```bash
   um sprite cutout gen/missile.jpg t/missile.png --bg ffffff --tol 0 --grey 232   # border flood fill: all channels >= 232 -> clear
   um sprite rotate t/missile.png t/missile_level.png -45                          # flux drew it diagonally
   um sprite fit t/missile_level.png t/missile_small.png --size 14x5               # nearest neighbour, once
   um sprite fit t/missile_small.png Assets/HomingMissile.png --size 38x16 --no-upscale

   um sprite flip t/scrap_drone.png t/drone_left.png                               # NPC sprites face left
   um sprite fit t/drone_left.png t/drone.png --size 46x30
   um sprite frames t/drone.png t/drone --n 2 --kind bob                           # 2-frame hover
   um sprite sheet Assets/ScrapDrone.png t/drone/drone_0.png t/drone/drone_1.png --vertical
   ```

   Frame sizes: launcher 64x26, missile 38x16, nuke 40x84, Tesla 62x30, Singularity 70x34, remote
   24x38, drone 2x 46x30, slime 2x 38x34, walker 3x 40x46, Mothership 2x 240x150. The Mothership's
   second frame (its red core flaring) and the icon are the only steps done with a few lines of Pillow.
   The shipped sprites came from the first build (a Pillow script). Running `make_art.sh` on the same
   raw art reproduces them. Two come out byte-identical; the rest are off by a pixel of scale or
   position (`um sprite fit` rounds where that script truncated), and the drone's bob and the slime's
   squash are a little gentler. So a run rewrites a few pixels of the committed PNGs.

## Lessons from building this

- NPC frames are stacked vertically, and the game takes the frame height as texture height /
  `Main.npcFrameCount`, so any consistent frame size works. You don't have to match vanilla's.
- Item sprites point right. NPC sprites face left, and `spriteDirection = 1` flips them to face right.
  A projectile's sprite has to match its draw code: these ones point right because `PreDraw` rotates
  them by `velocity.ToRotation()`. Many vanilla projectile sheets point up and add 90 degrees.
- Vanilla fighter AI (aiStyle 3) stops chasing on the surface in daytime: it wanders off and
  despawns. The Mech Walker has its own AI for that reason. To read vanilla code like this, decompile
  the game with ilspycmd into a folder outside the repo, for example
  `ilspycmd -p -o ~/tml-decomp "<tModLoader install>/tModLoader.dll"` (or Terraria.exe for vanilla),
  then grep `AI_003_Fighters`. Never commit the decompile (`um publish check` flags decompiler output).
- Recording: capture the game window by its HWND with ffmpeg's gfxcapture (`um win record`). FNA3D's
  D3D11 `ReadBackbuffer` leaks a full frame per call, and gdigrab gives black frames. Get game-only
  sound with a process-loopback capture (um/ps1/ProcLoopback.ps1). Never block the game's main
  thread while ffmpeg stops, because gfxcapture stalls on a frozen window. Stop processes by exact PID
  (`um win kill <pid>`). From an agent's shell, `pkill -f <pattern>` also matches the shell running it
  and kills that too. `reference/InModRecorder.cs` is the in-game version, with the details.
- Explosive takes destroy the world. Keep a pristine copy and restore it before each take:
  `um backup create "<save folder>/tModLoader/Worlds" --name worlds`, then `um backup restore worlds --yes`
  (the save folder is `Documents\My Games\Terraria` on Windows).
- tModLoader refuses to start unless the free tModLoader app is in your Steam library, including
  builds from GitHub. Add it to your library; don't try to get around the check. The command-line
  `-build` exits before any Steam code runs, so building works without it.
- `ModSystem.ModifyScreenPosition` runs after screen shake is applied, so setting
  `Main.screenPosition` outright cancels the shake. The nuke's camera adds an eased offset instead.
- `ModProjectile.OnSpawn` only runs on the machine that spawned the projectile, before the net sync is
  sent. Data other players need goes in `Projectile.ai[]`, which is how the Tesla arcs work.
- `PostDrawTiles` gets no active SpriteBatch (call `Begin`/`End` yourself). `PostDrawInterface` draws
  with the UI scale applied, so a full-screen flash has to divide by `Main.UIScale`.
- The csproj: tModLoader offers to "upgrade" a mod whose csproj has no `<Import Project="..\tModLoader.targets" />`,
  or that has no `Properties/launchSettings.json`, so both follow its template. Don't name your own override property `TMLPath`: `tMLMod.targets` already uses `tMLPath`,
  and MSBuild property names ignore case.
- Under WSL, against a Windows install, `dotnet tModLoader.dll -build` worked. `dotnet build` compiled
  there too, but its packaging step (`-server -build`) failed to load FNA3D, which it needs to convert
  the PNGs. Package on Windows, or use `-build` under WSL.
- flux/dev returns JPEG unless you ask for `output_format=png`. The first build saved its JPEGs with
  a `.png` name, and Pillow opened them anyway; they're stored under their real extension here.

## Files

```
FalArsenal/            the mod (copy this into ModSources)
  Weapons.cs           Homing Missile Launcher, Tactical Nuke
  EnergyWeapons.cs     Tesla Rifle, Singularity Launcher, Orbital Strike
  Mobs.cs              Scrap Drone, Neon Slime, Mech Walker
  Boss.cs              Drone Mothership and its rockets
  Fx.cs                explosions, nuke crater and mushroom cloud, flash, camera focus, draw helpers
  Commands.cs          /arsenal, /mothership
  Localization/        display names and tooltips
  Assets/, icon.png    sprites (made by assets/make_art.sh)
assets/make_art.sh     fal prompts -> um sprite pipeline
assets/gen/            the raw fal/flux drawings it starts from
reference/             not built: InModRecorder.cs (window + game-audio capture from inside the game),
                       AgentBridge.cs (JSON-lines socket so an outside agent can read menus, click and play)
```

Sprites generated with fal (fal-ai/flux/dev) and processed with universal-modder's `um sprite`.
