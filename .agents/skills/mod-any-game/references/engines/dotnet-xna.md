# .NET games: XNA / FNA / MonoGame and friends

**Identify.** The exe is a managed assembly (`um scan` shows `.NET`). Look for `FNA.dll`,
`MonoGame.Framework.dll` or `Microsoft.Xna.Framework*.dll`, and `Content/*.xnb`.
- Examples: Terraria, Stardew Valley, Celeste, Terraria's tModLoader itself, many indie games.
- The whole game is readable C#, and patching is well supported.

## Known loaders (use them)

### Terraria → tModLoader
- A free Steam app (1281930). It must be in the Steam library; don't bypass that check.
- Mods are C# in `Documents/My Games/Terraria/tModLoader/ModSources/<Mod>/`. Build them in game with
  Workshop → Develop Mods → Build + Reload, or build from the command line with the `tModLoader.targets`
  the game generates.
- **Content classes:**
  - `ModItem`: `SetDefaults`, `Shoot`, `UseItem`, `AddRecipes`;
  - `ModProjectile`: `AI`, `PreDraw`, `OnHitNPC`;
  - `ModNPC`: `AI`, `FindFrame`, `SetStaticDefaults` with `Main.npcFrameCount`;
  - `ModSystem` (world hooks, UI);
  - `ModPlayer`;
  - `ModCommand` (chat commands, great for testing: `/arsenal`);
  - `GlobalNPC` / `GlobalItem` change vanilla content.
- **Art:** PNGs next to the class (`Texture => "Mod/Assets/Name"`). NPC sheets are vertical strips, with
  frame height = texture height / `npcFrameCount`.
- **Lab:** `-tmlsavedirectory <dir>` isolates saves; `-skipselect Player:World` loads straight in.
  `Main.instance.InactiveSleepTime = TimeSpan.Zero` keeps full speed unfocused.
- **Hooks into vanilla methods:** `On_Main.DoUpdate += ...` (detours) and `IL_*` (IL edits) via MonoMod,
  which ships inside tModLoader.
- **Logs:** `tModLoader-Logs/client.log`.
- Worked example: `examples/terraria-tmodloader/`.

### Stardew Valley → SMAPI
- Plain content changes (sprites, dialogue, maps, data) → Content Patcher packs (JSON).
- Code → SMAPI C# mods:
  - `ModEntry : Mod`
  - `helper.Events.GameLoop.UpdateTicked`
  - `helper.GameContent` for asset edits
  - Harmony for patches
- Use the NuGet `Pathoschild.Stardew.ModBuildConfig`, which finds the game and deploys the mod.

### Celeste → Everest
- Install through the Olympus installer.
- Code mods use MonoMod hooks (`On.Celeste.Player.Update += ...`).
- Maps are built with Lönn.

### Others
BepInEx also loads into many plain .NET/Mono games (not just Unity). Otherwise use MonoMod/HarmonyX with a
tiny launcher.

## Read the game
- `ilspycmd -p -o ~/<game>-decomp <Game>.exe`. Keep the output **outside** the repo.
- The .NET SDK gives you ilspycmd: `dotnet tool install -g ilspycmd`.
- dnSpyEx for stepping through with a debugger.
- The decompile is the spec. Port logic from it; don't guess.

## Assets
- `.xnb` is XNA's compiled content. Loaders usually let you ship plain PNG/WAV instead: tModLoader loads PNG
  directly, and SMAPI loads PNG/JSON/TMX. To unpack stock `.xnb` for reference, use `xnbcli` / StardewXnbHack.
- Match the game's pixel scale and outline style. Terraria sprites are 2x-scaled pixel art with dark
  outlines.

## Pitfalls
- 32-bit vs 64-bit: old XNA Terraria is x86. tModLoader and FNA builds are x64 .NET 8.
- Single-player only for gameplay mods unless every client has the mod. tModLoader syncs mods in
  multiplayer if `side = Both`.
- Never ship decompiled code. Use hooks and your own code.
