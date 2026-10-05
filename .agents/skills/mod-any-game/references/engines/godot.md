# Godot (3.x / 4.x)

**Identify.** There is a `.pck` next to the exe (magic `GDPC`), or the pck is appended to the exe itself.
`um scan` reads the Godot version from the pck header.
- Game logic is GDScript: tokenized (`.gdc`), sometimes encrypted with a per-game key. C# (.NET) builds also
  ship `<Game>.dll` in a `data_*` folder; for those, see dotnet-xna.md for reading them.
- Saves: `%APPDATA%\Godot\app_userdata\<Project>\` (or a custom `user://` dir if `use_custom_user_dir`).

## Read the game
- **GDRE Tools (gdsdecomp):** recovers a whole editable project (scenes, resources, decompiled GDScript)
  from the pck/exe. Open it in the matching Godot editor version to understand the structure.
- **Encrypted pcks:** the key is embedded in the exe; GDRE Tools can find it for many builds. If a game
  deliberately encrypts, check its mod policy before going further.

## Routes
1. **Godot Mod Loader** (github.com/GodotModding/godot-mod-loader), if the game ships with it or the
   community added it. Mods are zips in `mods/` with a manifest; script extensions hook methods via
   `extend`. Brotato, Dome Keeper and others use it.
2. **PCK overlay:** Godot loads extra packs with `ProjectSettings.load_resource_pack("res://mod.pck")`.
   Resources in a later pack override earlier ones with the same `res://` path. You need code execution to
   call it, from an injected autoload or a mod loader.
3. **override.cfg** next to the exe overrides project settings. `autoload/MyMod="*res://mod/my_mod.gd"`
   adds an autoload singleton if the script is inside a loaded pack. With `application/run/main_scene` you
   can bootstrap your own loader scene.
4. **Rebuild:** export the recovered project with your changes. Only for personal use; never redistribute a
   rebuilt game.

## Content
- New scenes and scripts: make them in the matching editor version and export a pck with just your files
  (`--export-pack`).
- **Sprites:** PNG + `.import` metadata (the editor generates `.ctex` on export). Match the game's
  texture filter: nearest for pixel art.

## Pitfalls
- Editor and runtime versions must match (4.2 vs 4.3 resource format changes).
- GDScript 2.0 (Godot 4) and 1.0 (Godot 3) are different languages.
- `godot-mcp` can drive the editor for an agent when you're building new content.
