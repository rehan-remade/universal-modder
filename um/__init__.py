"""universal-modder: tools any AI agent (Claude Code, Codex, Cursor, Gemini CLI, ...) uses to mod games.

Subcommands (see `um --help`):
  scan      find installed games and fingerprint one: engine, runtime, anti-cheat, mod loaders, routes
  fal       generate game assets with fal (sprites, textures, PBR, 3D, rigs, SFX, music, voice, video)
  comfy     generate images locally with ComfyUI (no API key)
  sprite    cut out, fit, pixelate, recolor and pack 2D sprites
  render3d  render a GLB into sprite frames from a game's camera (Blender)
  video     compile styled showcase videos, trim, mux
  win       Windows (and WSL): screenshots, recording with game-only audio, input, processes
  backup    snapshot and restore save folders before you touch them
  publish   lint a mod folder before sharing: game files, decompiled code, secrets, credits
  kb        the knowledge base: search prior field notes, write your own, check it, open a PR
"""

__version__ = "0.2.0"
