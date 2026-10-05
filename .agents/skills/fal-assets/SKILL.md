---
name: fal-assets
description: Generate game assets with fal (fal.ai) through the fal MCP server, the `um fal` CLI (REST) or `fal api`. Covers sprites and icons with transparent backgrounds, consistent variants and animation frames, pixel art, seamless textures, PBR material maps, image-to-3D models, remeshing, auto-rigging, sound effects, music, voice lines, and trailer or cutscene video. Use whenever a mod needs new art, audio or 3D models, or the user mentions fal, generating sprites, textures, models, SFX or music for a game.
---

# Game assets with fal

fal runs hundreds of generative models behind one API key. Use it whenever the mod needs something that
doesn't exist yet: a weapon sprite, a boss, a unit rendered from 16 angles, a tileable floor, a laser sound,
boss music, a voiced line.

## Setup (check once per session)
- **Key.** `FAL_KEY` must be set (create one at https://fal.ai/dashboard/keys). `um fal` also reads it from
  a `.env` file (`FAL_KEY=...`) in the working folder. Never write the key into mod files; `um publish check`
  flags leaked keys.
- **MCP.** fal's hosted MCP server is `https://mcp.fal.ai/mcp` with header `Authorization: Bearer $FAL_KEY`.
  The repo pre-configures it for each agent:
  - Claude Code: `.mcp.json`
  - Codex: `.codex/config.toml`
  - Cursor: `.cursor/mcp.json`
  - VS Code/Copilot: `.vscode/mcp.json`
  - Gemini CLI: `gemini-extension.json`

  To add it by hand:
  - Claude Code: `claude mcp add --transport http fal https://mcp.fal.ai/mcp --header "Authorization: Bearer $FAL_KEY"`
  - Codex (`~/.codex/config.toml`): `[mcp_servers.fal]` with `url = "https://mcp.fal.ai/mcp"` and
    `bearer_token_env_var = "FAL_KEY"`
  - anything else: point its MCP config at the URL and header above.
  MCP tools: `search_models`, `recommend_model`, `get_model_schema`, `get_pricing`, `run_model`,
  `submit_job`/`check_job`/`get_job_result`, `upload_file`, `search_docs`.
- **No fal key?** For images, `um comfy` uses a local ComfyUI server instead (`um comfy status`, then
  `um comfy image "..." --sprite`). It has no audio, 3D or video recipes.
- **CLI alternatives:** `pip install fal` gives `fal api <endpoint> key=value key:=json`; the genmedia CLI
  (`genmedia run ... --json --download`) is agent-friendly too.

## Which interface
- **Discovery** (what's the best model for X right now, its inputs, its price): fal MCP
  `recommend_model` / `search_models` / `get_model_schema` / `get_pricing`, or `um fal search`,
  `um fal schema <endpoint>`, `um fal price <endpoint>`. The catalog changes weekly. The defaults below were
  current in September 2026; check before a big batch.
- **Anything that must land on disk** (every game asset): `um fal <recipe>`. It uploads local inputs,
  queues, polls, downloads every output file, and appends the endpoint, inputs, seed and request id to
  `<out>/fal_manifest.jsonl`, so every asset can be traced and regenerated.
- **Quick look or one-off** where a URL is enough: MCP `run_model`.

## Recipes (`um fal <recipe> --help` for options; `--model` overrides the endpoint; `--set k=v` passes extra inputs)

| Asset | Command | Default endpoint |
|---|---|---|
| Sprite / icon, transparent background | `um fal sprite "<subject, view, style>" --name x` | `openai/gpt-image-2` (`background=transparent`) |
| Concept art, key art, backgrounds | `um fal image "<prompt>" --aspect 16:9` | `fal-ai/nano-banana-2` |
| Consistent variants, extra frames, recolors, same character new pose | `um fal edit "<change>" --ref base.png` | `fal-ai/nano-banana-2/edit` |
| Background removal | `um fal rmbg in.png` | `fal-ai/birefnet/v2` |
| Clean pixel art from any image | `um fal pixelate in.png --colors 24` | `fal-ai/image2pixel` |
| Upscale | `um fal upscale in.png --factor 2` | `fal-ai/seedvr/upscale/image` |
| Seamless tiling texture | `um fal texture "mossy cobblestone"` | `fal-ai/z-image/turbo/tiling` |
| PBR maps (basecolor, normal, roughness, metalness, height) | `um fal pbr "rusted sheet metal"` | `fal-ai/patina/material` |
| Image → textured 3D model (GLB) | `um fal model3d concept.png [--engine trellis2\|hunyuan\|tripo\|meshy]` | `fal-ai/trellis-2` |
| Auto-rig a humanoid, optional animations | `um fal rig character.glb --animate` | `fal-ai/meshy/rigging` |
| Sound effect | `um fal sfx "plasma rifle shot, punchy" --seconds 1.2` | `fal-ai/elevenlabs/sound-effects/v2` |
| Music | `um fal music "tense boss battle, chiptune, 150 bpm" --seconds 90` | `elevenlabs/music/v2.5` |
| Voice line | `um fal voice "You dare challenge me?" --voice-id Adam` | `fal-ai/elevenlabs/tts/eleven-v3` |
| Trailer / cutscene clip | `um fal video still.png "camera orbits the boss"` | `bytedance/seedance-2.5/image-to-video` |
| Anything else | `um fal run <endpoint> key=value key:=json image_url=@local.png` | any |

Other useful endpoints:
- 3D: `tripo3d/tripo/remesh` and `fal-ai/meshy/v5/remesh` (low-poly, game-ready), `fal-ai/trellis-2/retexture`.
- Motion: `fal-ai/hunyuan-motion` (text → motion).
- Icons: `fal-ai/recraft/v4.1/text-to-vector` (SVG icons).
- Video cutouts: `pixelcut/video-background-removal`.
- Music: `google/lyria-3.5`.
- Voice: `fal-ai/minimax/speech-2.8-hd`.

## Prompting game art that fits the game
- **Look at the game's own assets first:** pixel size, outline, palette, perspective, facing, how busy they
  are. Put that into a reusable style suffix. For Terraria: *"16-bit pixel art game sprite in the style of
  Terraria, crisp dark outline, limited palette, centered, plain flat white background, no shadow, no
  text"*.
- **Describe the view and orientation explicitly:** "perfectly horizontal side view with the muzzle pointing
  right" for held weapons, "seen from the side facing left" for enemies, "pointing straight down" for a
  falling bomb. Engines have conventions (Terraria items point right, NPCs face left) and fixing
  orientation afterwards costs quality.
- **Backgrounds:** transparent (gpt-image-2) or a flat colour that `um sprite cutout` can flood-fill.
  Avoid gradients, scenery and ground shadows. If a soft shadow sneaks in, use `--grey` / `--keep-top`
  in cutout.
- **Player / team colour:** ask for "bright saturated blue accents" on the parts that should take the
  player's colour, then `um sprite team-mask --hue blue` turns them into a mask.
- **Consistency across a set:** generate one hero image, then derive the rest with the edit endpoint and the
  hero as `--ref` ("same robot, now firing, muzzle flash"). Don't ask one prompt for a whole sprite sheet;
  grids come out uneven.
- **Many angles or frames of the same object:** go 3D. Take the concept, run `um fal model3d`, then
  `um render3d` from the game's camera (asset-pipeline skill). That's how the AoE2 robotaxi got 16
  consistent headings × 5 animations.
- **No text or logos** in art unless wanted: models love to add them.

## Audio for engines
- The SFX and music endpoints return MP3. Convert to what the engine wants:
  - `ffmpeg -i x.mp3 -ar 44100 x.wav` (XNA/tModLoader, most engines);
  - `ffmpeg -i x.mp3 -c:a libvorbis -q:a 5 x.ogg` (Minecraft, Godot, Unity);
  - trim silence first: `-af silenceremove=start_periods=1:start_threshold=-50dB`.
- Loops: `um fal sfx ... --loop`, or ask the music model for a loopable track and crossfade the ends.
- Keep SFX short (0.2-2 s) and normalize loudness (`-af loudnorm=I=-16`) so they sit with the game's own
  sounds.

## Cost and etiquette
- **Price the expensive stuff:** before batching 3D, video or long music, check the price
  (`um fal price <endpoint>` / MCP `get_pricing`). For more than about 20 generations or anything
  video-sized, tell the user the rough cost first.
- **Iterate cheap:** use low quality or resolution while exploring (`--quality low`, `--res 0.5K`), then
  re-run the winners at full quality with the same prompt (and seed where supported).
- **Reproducibility:** keep `fal_manifest.jsonl` with the assets; it records prompts, seeds and request ids.
- **Credits:** in the mod's README, credit that assets were generated with fal and name the models. Check a
  model's license page for commercial use.
