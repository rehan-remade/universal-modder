# The AI modding knowledge base

Field notes on how games were actually modded, decompiled and reverse-engineered. **Written by agents for
the next agent**, reviewed through pull requests. Each note records what one project learned the hard way:
the exact versions that worked, the route, what the engine really does, how it was verified, and most of all
the **gotchas** (symptom → cause → fix). The next agent that touches the same game or engine starts with
that instead of rediscovering it.

- [`INDEX.md`](INDEX.md) lists every note (`index.json` is the same data for tools).
- `games/<game>/<note>.md` holds one project each. Mashups live under the host game.
- `techniques/<note>.md` holds cross-game methods: oracles, recording, safe input, passthrough, decomp
  loops...
- Engine playbooks (routes and tools per engine) live with the skills, in
  [`../skills/mod-any-game/references/engines/`](../skills/mod-any-game/references/engines/).

## Before you start a mod: search
```bash
um kb search "<game>"                      # works in a clone, or anywhere (it syncs this folder from GitHub)
um kb search unreal pak --route loader-api
um kb show games/gta-v/minecraft-passthrough.md
```
No `um`? Read [`INDEX.md`](INDEX.md) on GitHub, or fetch
`https://raw.githubusercontent.com/rehan-remade/universal-modder/main/knowledge/index.json`.

## After you finish (or get stuck): write it up and open a PR
A note is worth writing whenever you learned something the next agent would otherwise lose an hour to,
even if the mod isn't finished. `status: in-progress` and `abandoned` are welcome; dead ends are knowledge.

```bash
um kb new --game "<game>" --title "<what you built>" --from-scan "<game>" --agent "<agent (model)>"
# fill it in: Setup (exact versions), Route and why, How the game works, Build steps, Verification, Gotchas
um kb check knowledge/games/<game>/<note>.md
um kb pr knowledge/games/<game>/<note>.md          # dry run; add --yes once your human agrees
```
The full rules for contributors (human or AI) are in [`../CONTRIBUTING.md`](../CONTRIBUTING.md). In short:
- every game is welcome, multiplayer and servers you host included;
- no game files, no pasted decompiled code, no secrets, no cheating other players;
- describe what you learned in your own words;
- name the agent and model;
- say honestly what you did and didn't verify.

## What makes a good note
- **Versions.** "tModLoader 2026.07 on Terraria 1.4.4.9" beats "latest".
- **Gotchas with causes.** "Colour readback fails after a depth readback, because the GL backend leaves the
  read buffer at GL_NONE" is reusable; "rendering was broken" isn't.
- **The oracle.** How you knew it worked, so the next agent can re-verify after a game update.
- **Short code.** A snippet of *your own* code is fine. Link to the repo for the rest.
