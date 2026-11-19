"""universal-modder: tools any AI agent (Claude Code, Codex, Cursor, Gemini CLI, ...) uses to mod games.

Subcommands (see `um --help`):
  scan      find installed games and fingerprint one: engine, runtime, anti-cheat, mod loaders, routes
  fal       generate game assets with fal (sprites, textures, PBR, 3D, rigs, SFX, music, voice, video)
  comfy     generate images locally with ComfyUI (no API key)
  sprixen   2D sprites with Sprixen: one style per project, animation sheets, terrain tiles
  voidless  2D sprites with Voidless: 8-way turns and animation sets on one asset
  sprite    cut out, fit, pixelate, recolor and pack 2D sprites
  render3d  render a GLB into sprite frames from a game's camera (Blender)
  video     compile styled showcase videos, trim, mux
  win       Windows (and WSL): screenshots, recording with game-only audio, input, processes
  backup    snapshot and restore save folders before you touch them
  publish   lint a mod folder before sharing: game files, decompiled code, secrets, credits
  kb        the knowledge base: search prior field notes, write your own, check it, open a PR
  fastfile  Call of Duty 4 / World at War: list and dump the rawfiles (GSC, CSC, menus) in your own .ff zones
  iwi       Call of Duty 4 / World at War: PNG to IWI v6 textures (DXT1/DXT5) and back
  weapon    Call of Duty 4 / World at War: read, edit, clone and diff weapon files
"""

__version__ = "0.2.0"
