# Security

## Reporting a vulnerability
Please report security problems privately, not in a public issue or pull request. Use **Report a
vulnerability** on the repository's **Security** tab (GitHub's private vulnerability reporting). If that button
isn't there, open an issue that asks for a private contact and leave the details out.

There are no release branches: fixes land on `main`.

## What's in scope
The code in this repository: the `um` CLI (`bin/um`, `um/`, the PowerShell tools in `um/ps1/`), the hooks, the
agent configs and the example mods. The parts where a bug matters most:
- **Secrets.** `um fal` reads `FAL_KEY` from the environment, the key `um fal key set` stored (the desktop
  keyring on Linux, `~/.secrets/fal-key` elsewhere) or a `.env` file, and the agent configs pass `FAL_KEY` to
  the fal MCP server. A way for `um` to leak it, or a common key format that `um kb check` and
  `um publish check` miss, is in scope.
- **Local input and processes.** `um win` drives real input on Windows and kills processes by PID. Input that
  reaches a window other than the target game, or a kill that hits the wrong process, is in scope.
- **The Minecraft x GTA V example's link** listens on `127.0.0.1:25599` without a token, by design (see its
  README). A way to reach it from another machine is in scope.

Out of scope: problems in the tools and services `um` calls or downloads (fal, ComfyUI, ffmpeg, Blender, mod
loaders, ReShade, ScriptHookV). Please report those upstream. Requests to get past a game's anti-cheat, DRM or
ownership checks are out of scope too: this project doesn't do that (see `CONTRIBUTING.md`).
