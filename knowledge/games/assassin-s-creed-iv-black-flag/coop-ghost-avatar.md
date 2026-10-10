---
kind: game
title: "A visible, driven second character in AC4 single-player (co-op ghost avatar)"
game: "Assassin's Creed IV Black Flag"
games_also: []
game_version: "AC4BFSP.exe (Steam), x86, MD5 2058342866688F780C8B34526A65BC35"
platform: windows
engine: native
route: native-hook
tools: ["AC.PatchFix ASI plugin framework (ported to x86)", "Ghidra 12.1.4", "Cheat Engine 7.5", "Ultimate ASI Loader (x86)", "custom PowerShell WOW64 debugger scripts"]
anti_cheat: "none in single-player; the co-op link is the plugin's own peer-to-peer UDP, not Ubisoft's servers or online services; AC4BFMP.exe only studied statically, never run or injected"
status: working
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: []
date: 2026-10-06
links: ["https://github.com/playday3008/PatchFix", "https://github.com/ThirteenAG/Ultimate-ASI-Loader"]
tags: ["anvilnext", "coop", "avatar", "transform", "wow64-debugging", "hardware-breakpoints", "puppet", "ghost"]
---

# A visible, driven second character in AC4 single-player (co-op ghost avatar)

> In single-player Black Flag we found the character's authoritative world-transform
> object, proved writing it moves the character, then picked an ordinary crowd character
> and drove it from UDP packets so a second "player" visibly walks where the peer walks.
> Verified in-game: a fake peer script made an NPC circle the player, and the NPC
> returned to its own AI when the packets stopped.

## Setup

- Game: Steam AC4BFSP.exe, x86, pinned build above (fixed RVAs; image base 0x400000).
- Plugin: an ASI loaded by the 32-bit Ultimate ASI Loader (dinput8.dll), hooked at the
  camera update and running per frame on the game thread.
- Analysis: Ghidra 12.1.4 (20 GB heap for the 43 MB x86 exe), Cheat Engine 7.5 for
  breakpoint hunting, plus custom PowerShell scripts that attach as a WOW64 debugger
  for INT3 captures and hardware watches.

## Route and why

- Chose `native-hook` + fixed addresses over pattern scanning: single pinned build, and
  all addresses are re-resolved live anyway (heap objects move per session).
- The avatar is NOT spawned. The game has no reachable spawn/duplicate path from a plugin,
  so the remote body is a *hijacked crowd character* whose transform is overwritten each
  frame. Engine-side spawning exists (the graphic factory is table-registry driven) but is
  a separate, larger project.
- Networking is the plugin's own: each copy of AC4BFSP.exe sends and receives 72-byte pose packets over UDP,
  peer to peer (tested over Radmin VPN between two PCs). Nothing goes through Ubisoft Connect, Ubisoft's servers
  or AC4BFMP.exe.

## How the game works (what we had to learn)

**Camera -> target chain.** The camera manager global (`0x02ABE588`) -> `+0x4C` -> holder
-> camera object -> `+0x68` -> a camera-target block. The block's `+0x174` points at a
per-target "provider" object whose `+0x100` is a quaternion and `+0x110` the target's
feet position. The block's `+0x50` is a smoothed "eye" copy (feet + ~1.2 m). All of this
is *derived*: writes there snap back.

**The character root node.** The provider copies from a single source object per
character: class vtable `0x01E4CE90`, allocation size exactly `0x100` bytes.
Layout (fixed, offsets < 0x100):

- `+0x00` vtable, `+0x04` id (a global allocation counter, not a type)
- `+0x08` player-only identity-matrix pointer (null on every civilian)
- `+0x10` 4x4 matrix; row 3 (`+0x40`) is the **feet position** — write this to move them
- `+0x60` children array pointer, `+0x66` child count (= the rig), `+0x68` handle marker
  constant `0x04DD5F8C`, `+0x7C` exactly `-0.50` for humanoids
- `+0xC8` per-character object, `+0xE8` behavior-controller object (different classes for
  player vs civilian)
- Everything at `>= 0x100` belongs to *neighbouring heap objects*, not this object.

**Which bodies are real.** Class instances come in flavours: the player (rig 27 parts), real
crowd characters (rig 18-20), and inactive proxies (rig 1, or 8-14) that exist in memory but
never render. Writing an inactive proxy moves nothing visible. Filter: `f7c == -0.50` AND
child count >= 16 AND within reach of the target position; exclude anything within ~2.5 m of
the local player so you never grab the player's own body.

**Writing the body each frame.** In-process per-frame writes (from a hook) win the render
frame; the puppet's own AI keeps running and takes back over the moment writes stop. Add
yaw by rewriting matrix rows 0/1 as a Z-rotation from the peer's quaternion.

## Build steps

1. Read the local player's feet (provider `+0x110`) and facing (`+0x100`) every frame in an
   existing per-frame hook; publish over UDP with a small envelope+payload protocol.
2. Receive the peer sample (same protocol, binary, 72-byte packets).
3. In the same hook: if peer data is fresh (< 2 s), scan for a drivable body (incremental
   scan, a few MB per frame), smoothing the body toward the peer position (lerp ~0.3/frame,
   hard snap past ~20 m), and release on timeout.
4. Config in an ini; the plugin reloads it live (sockets re-bind on the fly).

## Verification

- **Oracle 1 (self):** captured the smoother's breakpoint (INT3 at the instruction copying
  the source transform) and confirmed the captured source object's matrix translation equals
  the camera-chain feet within 0.04 m.
- **Oracle 2 (eye-witness):** a write of +20 m to the matrix X made the player character
  visibly teleport — user-confirmed ("watched him teleport").
- **Oracle 3 (eye-witness):** a scripted fake peer circled the real player's position; an
  NPC visibly teleported in and walked the circle, and was released (walked off) when packets
  stopped ("yup he's circling"). Loop counter: 2,839/2,839 UDP packets both ways.
- **Oracle 4 (two machines, eye-witness, 2026-10-06):** real Radmin VPN run between two PCs
  (~105 ms ping). Both players saw each other's driven crowd body in-game; log showed
  `peer=1 body=1@<addr> fresh=1 d=13.8..18.9` with the body picked 61.5 m from the peer and
  tracked while walking. Facing replica confirmed ("he turns to match") — validates the +Y
  forward convention used for both placement and body yaw. Both sides hit a stuck UDP port
  (bind 10048, a dead process owning it); changing LocalPort and mirroring RemotePort fixed it
  live (the ini hot-reload re-binds without restart). Watch items: tracking slightly choppy
  (20 Hz + latency + the crowd AI); peer climbs show as vertical teleports (no animation/parkour
  linkage yet).
- Not verified: animations/parkour events and true model replacement.

## Gotchas

1. **Debugger-attached game dies on a breakpoint that looks unknown.** 64-bit debuggers
   receive WOW64 breakpoints as `0x4000001F` (STATUS_WX86_BREAKPOINT), not `0x80000003`;
   returning it to the app as "not handled" terminates it. **Fix:** treat both codes as
   breakpoints, continue with DBG_CONTINUE, and always restore the patched byte plus fix EIP.
2. **A hardware write breakpoint on the visible position never fires.** The visible value is
   a derived copy; its writer only runs when the source updates. **Fix:** watch the true
   source, or find the writer via the breakpoint on the copy routine itself.
3. **Fields past the object's allocation size are other objects.** Reads at `+0x110`/`+0x170`
   looked like vtables and were neighbours. **Fix:** get the allocation size from the
   constructor's allocator call (here `0x100`) and ignore everything beyond it.
4. **Writes snap back when the character is moving.** The movement system rewrites the
   transform while it has velocity. **Fix:** write per frame from in-process; it wins the
   render and the AI takes over when you stop.
5. **Quiet-looking bodies that accept writes but never render.** Inactive proxies share the
   class. **Fix:** child-count + `f7c == -0.50` filter.
6. **A game that "pauses" the world when unfocused.** Any scan while the chat window has
   focus sees a frozen world and a zeroed camera. **Fix:** poll until the player position
   actually changes before sampling.
7. **Kernel-held UDP ports.** Some crashed sessions leave a dead process still owning the
   bound UDP port (bind fails with 10048 even after the process is gone). **Fix:** use a
   fresh local port per session, or reboot — worth doing before any two-machine test.
8. **PowerShell name collisions broke our scripts repeatedly**: `rd`, `rp`, `rm`, `dir` are
   aliases; short helper names must be avoided in Windows-focused tooling.

## Assets

None — v0.1 hijacks an existing crowd character. Model replacement needs the multiplayer
"skin"/morph system (see below).

## Cost and time

One long session: recon of the transform chain, breakpoint capture, class census, body
picker, plugin write path, and a working loopback demo.

## Open questions

- **True model swap (make the ghost look like the protagonist).** The world puppet is a
  0x100-byte node whose rig (children) is built per model by the animation/graphics system;
  SP only has outfits *for the player*. The runtime character-model swap exists in the
  engine but in `AC4BFMP.exe` (`CharacterSkinsComponent`, `ActionSwapSkin`, `HIJACK_SKIN`,
  morph events). Next step: port that apply-skin path, or call SP's graphic factory
  (table-registry driven) for a puppet with the protagonist's definition.
- Animation/parkour event replication is next (the two-machine link is done — see Oracle 4).
