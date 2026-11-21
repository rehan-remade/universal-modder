---
kind: game
title: 'Offline pzspec testing for Build 42 mod Lua: pz_lua_testkit, two gates and clean-room stubs'
game: Project Zomboid
games_also: []
game_version: 'Build 42.x (Steam, Windows 10). The kit targets B42 mod Lua (Kahlua 2); its loader resolution also covers B41 layouts. Nothing was run in game for this note'
platform: windows
engine: java
route: loader-api
tools: ["pz_lua_testkit (npm; MIT)", "PUC-Rio Lua 5.1 (lua5.1 — not LuaJIT or 5.2+)", "pnpm / npm", "JDK 17 (Gate 2 only, local)", "Umbrella stubs (optional static checks)"]
anti_cheat: 'none; testing is fully offline and the game client never launches. Gate 2 only reflects against your own locally installed projectzomboid.jar and never runs in CI'
status: working
agents:
- ZCode (GLM-5.3-Flash)
humans: [hashtafak]
date: '2026-11-21'
links:
- "https://github.com/escapepz/pz_lua_testkit"
- "https://www.npmjs.com/package/pz_lua_testkit"
tags: [b42, testing, pzspec, lua, kahlua, ci, tooling, stubs, offline, strict-mode]
---

# Offline pzspec testing for Build 42 mod Lua: pz_lua_testkit, two gates and clean-room stubs

> [pz_lua_testkit](https://github.com/escapepz/pz_lua_testkit) (npm: `pz_lua_testkit`) is an offline-first,
> mock-first test toolkit for Project Zomboid B42 mod Lua: a Jest-like `pzspec` DSL that executes your mod's
> Lua in seconds without launching the game, through two gates — **Gate 1** (clean-room Lua 5.1 stubs, CI-ready)
> and **Gate 2** (local-only cross-check against the real Kahlua runtime from your own installed jar). The kit
> is tooling around the [loader-api route](b42-modding-orientation-layout-lua-runtime-tooling-interop-ui.md):
> your mods stay ordinary loader mods, they just get a real verification loop. IP-safe by construction: the
> clean-room kit ships no game code or binaries. The npm package also ships **its own agent skill**
> (`.agents/skills/pz-lua-testkit/SKILL.md`) for agents working inside an integrated mod repo — this note
> summarizes it; universal-modder deliberately does not vendor the skill, the kit is its home.

## Setup
- Project Zomboid Build 42.x from Steam for Gate 2 and real-event parity. The kit itself never reads or ships
  game files; Gate 2 reflects against `projectzomboid.jar` you already own, via a local JDK, and is local-only.
- **PUC-Rio Lua 5.1.x is required** (`choco install lua51` or your package manager; verify `lua5.1 -v`). Do
  NOT use LuaJIT or Lua 5.2+: the static scanner reads Lua 5.1 `string.dump` bytecode.
- Install the kit into the mod repo: `pnpm add -D pz_lua_testkit` (npm works the same), or clone the repo to a
  central folder and point `lua5.1` at `src/gate1/run.lua`.
- Optional: Umbrella stubs for instant static type-checking alongside (`PZ_UMBRELLA` integration).
- For agents: the npm package ships `.agents/skills/pz-lua-testkit/SKILL.md` — an execution loop with hard
  invariants and an error-decode table for working in a testkit-integrated mod repo. Copy it where your agent
  looks for skills (`.agents/skills` / `.claude/skills`), or read it straight out of `node_modules/`.

## Route and why
Tooling on the loader-api route (mods are Lua plus data the game loads natively — no loader to install; see the
[orientation note](b42-modding-orientation-layout-lua-runtime-tooling-interop-ui.md)). Alternatives considered:
- **Manual in-game testing only** — minutes per run, not CI-able, and the fastest way to leak decompiled game
  code into a mod repo.
- **Umbrella (static) only** — catches signature drift instantly but cannot execute Lua, so runtime logic bugs
  sail through.
Both gates together: static checks instant, execution coverage in seconds, suite runs green in CI before the
game ever launches.

## How the game works (what we had to learn)
- **Mod Lua runs on Kahlua 2, not PUC-Rio 5.1** — that mismatch is the whole reason for two gates. Java interop
  details Gate 1's stubs pin: collections are 0-based (`ArrayList:size()` pairs with `for i = 0, list:size() - 1`),
  `get(i)` outside bounds throws `IndexOutOfBoundsException`, `HashMap` stores nil VALUES (`containsKey` true,
  `get` returns nil), and statics like `getTimestamp()` have real-engine scales (epoch seconds / milliseconds).
- **The event registries are finite and nameable.** Engine boot registers a full set through two paths — the
  `Events` registry (mostly `On*` names, plus a handful of non-`On` ones) and the 8-key `Hook` registry. Custom
  events must be registered first (`LuaEventManager.AddEvent(name)`), which extends the `Events` allowlist only.
  Gate 2 asserts two-directional parity against the real registry from your jar.
- **`mod.info` `require=` deps are loaded by the game, not by your mod** — offline, they simply don't exist,
  so the kit's posture is stub-by-default (see Gotchas 5).
- **Lua 5.1 bytecode makes a cheap static scan.** `check_globals.lua` walks `string.dump` bytecode and lists
  every global read/write and every `Events.<Name>` / `Hook.<Name>` use with exact line numbers — including
  branches your tests never execute. That report is how you decide which stubs a spec needs.
- The B41/B42 mod layout resolution (`mods/<id>/42/…` plus `common/`, version-folder picking) is what the
  kit's mod loader reproduces; see the [42.20 modlist note](b42-20-modlist-preset-and-world-load-errors.md).

## Build steps
1. Install Lua 5.1 and verify: `lua5.1 -v`.
2. In the mod repo: `pnpm add -D pz_lua_testkit`; optionally a `"test"` script:
   `lua5.1 node_modules/pz_lua_testkit/src/gate1/run.lua --mod .`
3. Write specs as `TESTS/specs/*_spec.lua` (the `*_spec.lua` naming IS the collection contract):
   `describe` / `it` / `expect` with matchers `toBe toEqual toBeNil toBeTruthy toBeFalsy toContain toBeCloseTo
   toThrow`; `mock(fn)` records calls; `spyOn(obj, "method")` + `s.restore()`.
4. Run the suite, then the strict sweep: `set "PZ_STRICT=1" && lua5.1 node_modules/pz_lua_testkit/src/gate1/run.lua --mod .`
   — strict turns unknown globals and unknown event/hook names into instant errors (the typo net). Never
   disable strict to make a failure go away.
5. For custom defaults, use a standalone `TESTS/run.lua` shim calling `runner.run(config)` (`mod`, `specs`,
   `mod_path`, `ctx`, `stub_packs`, `strict`, `reset_per_test`) — see
   [docs/reference.md](https://github.com/escapepz/pz_lua_testkit/blob/main/docs/reference.md).
6. Enable shipped mock packs per config or `PZ_STUB_PACKS=game,java` — they mock the union surface real mods
   touch (`getSpecificPlayer`, `ModData`, ISPanel-family UI, Java collections; the shipped surface record is
   `src/gate1/stubs/SURFACE.md`).
7. Gate 2 (local only): install a JDK, point the runner at your `projectzomboid.jar`, and cross-check Kahlua2
   deltas (stdlib overrides, varargs, the real `Events` registry). It never runs in CI.

## Verification
- Oracle: the kit's own suites — Gate 1 green in default and strict modes (280/280 + 280/280 at
  0.2.1-rc.202611211738), GitHub Actions CI green on Linux; Gate 2's events-parity suite reds itself when the
  real engine gains an event the kit hasn't shipped yet (intended).
- In-repo proof: the kit was extracted from real migrated mod suites (CAF/MAF-style dependency isolation,
  JASM-style event-listener patterns), so its patterns trace to actual mods.
- What was NOT verified: behavioral parity with the running game beyond Gate 2's probes — Gate 1 stubs are
  clean-room (they pin names and contract shapes, not game semantics); multiplayer is out of scope.

## Gotchas
1. **`PZ_STRICT: unknown global 'X'` on a global that may legitimately be absent.** Cause: a bare
   `(X or default)` read — strict's read-only guard fires on any unknown-global read. Fix:
   `rawget(_G, "X") or default` (spec code and mod code alike; plain assignment is always free).
2. **`if Events.X then` silently lies.** Cause: non-strict auto-create auto-vivifies a dispatcher, so the
   probe is always truthy. Fix: probe existence with `rawget(Events, "X")`.
3. **Event listeners registered at file top level vanish after the first test.** Cause: with
   `reset_per_test` (default on in mod mode) every stub-created dispatcher is Cleared per test. Fix: register
   inside functions or re-register in `before_each`.
4. **State leaks between tests anyway.** Cause: `_G` is NOT wiped — only the require cache and event
   dispatchers reset; top-level `_G` tables from mod auto-exec survive. Fix: clean up your own global tables
   in `before_each`.
5. **`PZ_REQUIRE: module not found '<dep>'`** — intentional stub-by-default posture, not a bug. Fix:
   `testkit.provide("dep_name", fake)` in the spec (persistent, beats disk), or run with `PZ_MOD_PATH` aimed
   at the real dep if you truly need it.
6. **A Java collection loop yields nothing.** Cause: 1-based iteration. Fix: `for i = 0, list:size() - 1`.
7. **Hand-rolling a mock for a class the kit already covers.** Cause: not checking the surface record. Fix:
   look it up in `SURFACE.md` and enable the pack instead — a missing member there is an escalation to the
   kit's devs, not an invitation to fork the stub.
8. **`total=N but EXPECTED_TOTAL=M`** — the suite's size changed or the wrong suite ran. Fix: update
   `EXPECTED_TOTAL` in the repo's own `TESTS/run.lua` only for real, reviewed changes.
9. **Editing the kit inside `node_modules/pz_lua_testkit` to unblock yourself.** Cause: treating a resolved
   copy as the source. Fix: don't — it diverges from upstream and a masked kit bug is a false-green factory;
   report it upstream per the kit skill's escalation section.

## Assets
None — this is a testing-tool note; no art was made.

## Cost and time
Setup cost is moderate (Lua 5.1 + one npm dep), per the kit's own comparison table; the payoff is that every
later mod change re-verifies in seconds instead of a game relaunch per iteration.

## Open questions
- How deep B41 parity should go — the kit targets B42 mod Lua; B41 layouts resolve but semantics drift is
  unmeasured.
- The kit's skill currently lives only inside the npm package; if the workflow proves out across more mod
  repos, a future universal-modder contribution could revisit whether it belongs in `skills/` here — deferred
  for now.
- `SURFACE.md` coverage grows with fleet usage; missing members are documented escalations rather than local
  stubs.
