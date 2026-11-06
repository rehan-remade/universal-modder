# Minecraft x Outer Wilds: real Minecraft inside Outer Wilds

Drafted 2026-10-19 with the universal-modder toolkit (`mashup-mods` skill).
Route: **Pattern 2, passthrough** — frame compositing + state exchange.

> **Status note, added later:** this plan was carried out, and the passthrough works (see `README.md`).
> It is kept here because it records *why* the route was chosen and what the abandoned content-port plan
> was, which the code alone does not explain. The "awaiting go-ahead" framing below is the state at the
> time of writing.

## What was found on this machine (recon)

- **Outer Wilds** (Steam 753640) is installed and is a **Windows build running under
  Proton** (`OuterWilds.exe`, PE32+; `compatdata/753640` prefix exists). It is **already
  modded**: OWML 2.16.3 with HarmonyX is installed, and `Assembly-CSharp.dll` in the game's
  `Managed/` is already patched.
- OWML's mods folder here is native Linux:
  `~/.local/share/OuterWildsModManager/OWML/Mods/`. It renders it into the prefix as `Z:\...`.
- **`SvenTheRedPanda.BlockCraft` already exists and has already run in the game.** Log
  (`OWML/Logs/latest.txt`, 2026-10-19 16:18-16:21) shows `BlockCraft loaded`,
  `block tool added to the loop`, `block tool ready: equip key Digit6, block size 1.00 m`.
  Source is in `~/Downloads/blockcraft-outer-wilds-1.0.0/` (763 lines C#, net48, OWML 2.16.3).
  It is a **Pattern 1 content port**: textured Minecraft-style cubes you place and break in the
  real Outer Wilds world. Minecraft itself never runs.
- **Minecraft Java is set up natively**: Modrinth App (flatpak 0.21.9) with a Fabric profile
  running **Minecraft 26.3 + Fabric Loader 0.19.5**. Native Linux JRE 17/21/25 are bundled by
  Modrinth.
- **Toolchain**: `dotnet` 6.0.136 only (not 8). `mono`/`mcs` present. NuGet reachable.
  Note: the BlockCraft `csproj` targets net48 and *built* here, so a C# OWML mod is buildable
  (needs confirming which SDK/ref pack path it used).

## The one fact that decides the architecture

The earlier plan (`~/Downloads/blockcraft-outer-wilds-1.0.0/MODDING_PLAN.md`) recommended
Route B (content port) and **rejected the live passthrough as "the flakiest option by far"**
because "the graphics passthrough in the toolkit examples is Windows D3D shared memory end to
end; on Arch with two Proton prefixes ... not recommended".

That reasoning held only while **both** sides were thought to live in Proton prefixes. It does
not hold now:

- The **host** (Outer Wilds) is a Windows Unity build under Proton -> the compositing side is
  **not** a D3D hook. It is a Unity `Camera.onPreCull` + RenderTexture + full-screen quad, all
  inside the OWML C# mod. That is exactly what the verified portal-gun example already does,
  and it needs **no D3D, no ReShade, no swapchain hook and no native DLL**.
- The **guest** (Minecraft 26.3 Fabric) runs **natively on Linux**, so its frame export is a
  plain JVM write into a file-backed shared mapping — the pattern the CrossOver/MHW/ER bridges
  used precisely so a native JVM and a Wine process can share memory.

So the two-prefix objection is gone. Cross-process sharing is `mmap` on a file both a native
Linux JVM and a Wine process can open (Wine maps Linux files at `Z:\`), with named POSIX
semaphores or a seqlock for sync — no Windows named objects required.

## Chosen route: Pattern 2 passthrough, frame compositing + state

```
Outer Wilds (Proton, Unity 2019.4 Mono)            Minecraft 26.3 + Fabric (native Linux)
  SvenTheRedPanda.BlockCraft  --- WebSocket 127.0.0.1:25599 ---> camera / ground / keys / commands
       (OWML C# mod)          <--------------------------------  explosions, hits, mob events
  compositor: UI/Default full-screen quad  <-- mmap file "blockcraft.frame" --  world RGBA + depth + hand/HUD
       depth-tested vs OW depth + stencil
```

### Why not the alternatives (re-checked)
- **Pattern 1 (content port only):** that is what BlockCraft 1.0.0 already is. It delivers
  "Minecraft blocks in Outer Wilds", not "real Minecraft gameplay inside Outer Wilds", which is
  what was asked for.
- **Pattern 3 (embed a decomp):** no Minecraft decomp to link; MC is Java.
- **Pattern 5 (reimplement MC's rules headless):** far too much surface area, and it stops being
  Minecraft.
- **Geometry transfer:** would need the host to parse and draw MC's chunk meshes. Minecraft's
  own renderer already works; compositing its picture is strictly less work and keeps MC's
  lighting correct on the guest side.

## Guardrails this specific setup triggers
- Outer Wilds is **single-player**, no anti-cheat: safe to hook.
- Minecraft Java 26.3 is launched by Modrinth with the user's own **Microsoft account**. The mod
  must run in a **dedicated passthrough profile with its own `gameDir`**, in an **offline/
  single-player world only**, and never log in alongside a hooked process going online. Prefer a
  Fabric profile with no online play for the lab; the real client stays in a local world.
- Nothing from Minecraft or Outer Wilds ships in the repo: no textures, no jar contents, no
  decompiled code. Textures come from the user's own jar at install time (the portal-gun pattern).
- Kill processes by exact PID; `um backup` the Outer Wilds saves before modded launches.

## Units, ownership and axes (draft contract; full version in docs/CONTRACT.md)
- **1 Outer Wilds metre = 1 block** (matches BlockCraft's existing 1.00 m default).
- **Outer Wilds owns the camera and the player's position.** Minecraft renders from the mapped
  pose; MC's own input drives movement only when the bridge is in "MC drives" mode.
- **Minecraft owns the guest simulation**: blocks, mobs, inventory, crafting. Outer Wilds owns
  the solar system, the ship, the loop.
- Frame format and channel semantics are versioned; the layout mirrors the GTA V example
  (world RGBA + depth, separate hand/HUD layer) so the already-written Fabric-side code can be
  reused.

## First slice (proves the route, before any Minecraft content)
1. Outer Wilds draws one Minecraft cube, depth-tested, at a known world position on Timber
   Hearth, occluded correctly by a rock and lit by the scene — checked by screenshot.
2. The pose used is logged on both sides with a frame counter; walking and the loop reset are
   shown not to desync.
No mobs, no inventory, no Nether, until (1) and (2) hold in the real game.

## Oracles
- Reuse the existing BlockCraft **mod-side command file** bridge pattern (the portal-gun
  example's `dev.enabled` / `dev_commands.txt` / `dev_log.txt` / `shots/`) — so the agent can
  drive Outer Wilds without touching the user's mouse and keyboard.
- A **fake host** (known geometry + synthetic depth) on the OW side and a **fake guest** frame
  producer, so most work happens with neither real game running — the GTA V example's method.
- Headless check on the Fabric side (server-only mixin test) plus a client game test.

## Open questions before building
1. **Build target confirmation:** the BlockCraft csproj is net48 and reportedly already built
   here, but the only SDK present is dotnet 6.0. Confirm how it built (mono ref pack? `-p`
   override?) or pin the toolchain.
2. **Does the MC profile stay native Linux?** (Chosen so far.) If Minecraft must instead run
   under Wine to match the host, the transport changes — say so now.
3. **Frame budget:** OW at 3440x1440 already drops ~93/82 FPS with a portal; cap the guest frame
   at ~1080p by area and triple-buffer, per the frame-compositing note.
4. **User's own pack:** run the passthrough in a **fresh, dedicated Fabric profile** (separate
   `gameDir`), never in the All the Mods 11 / Fabulously Optimized profiles.

## Deliverables
- OW side: extend `SvenTheRedPanda.BlockCraft` (bridge + compositor) — or a sibling mod if the
  user prefers to keep 1.0.0 clean.
- MC side: a Fabric mod for 26.3, forked from `examples/minecraft-gta5-passthrough/mc`.
- `docs/CONTRACT.md`, `MODLOG.md`, a headless test, a fake-host test, and a field note + PR at
  the end.
