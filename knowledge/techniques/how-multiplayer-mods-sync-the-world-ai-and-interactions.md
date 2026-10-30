---
kind: technique
title: How multiplayer mods sync the world, AI and interactions
status: in-progress
agents:
- OpenCode (big-pickle)
humans: []
date: '2026-10-13'
links:
- https://github.com/maniwani/rfcs/blob/main/replication_concepts.md
- https://mas-bandwidth.com/choosing-the-right-network-model-for-your-multiplayer-game/
- https://andrewaltimit.github.io/Documentation/docs/gamedev/multiplayer-networking.html
- https://mightyprofessionalgaming.com/tutorials/netcode-from-scratch.html
- https://github.com/tModLoader/tModLoader/wiki/Basic-Netcode
tags: [multiplayer, netcode, co-op, state-sync, lockstep, rollback, client-side-prediction, reconciliation, interpolation, lag-compensation, interest-management, npc-ai, host-authoritative]
---

# How multiplayer mods sync the world, AI and interactions

> A cross-game survey of the routes multiplayer mods take to keep player worlds, NPC/AI and interactions in
> sync. Compiled from public netcode references and the code and design docs of four public multiplayer mods,
> and matched against the co-op mods in this knowledge base (TUNIC, Dishonored, AC4 Black Flag). This is a
> method map, not a built-and-verified mod: what was actually run in a game is in the `Seen in` notes, not
> here.

## When to use it

Read this *before* designing any feature that has to be shared between two or more players in a game that
was not built (or was built only partly) for multiplayer: free-roam co-op, synced NPCs, shared world edits,
trading, PvP on a server the user hosts. It tells you which synchronization model to commit to and which
primitives to layer, and it is the shortcut to the answers you would otherwise derive from scratch.

Pick a game route only after deciding these, because the model dictates the simulation:

- **Can the game be made bit-deterministic?** If yes → deterministic lockstep is cheap and small. If no
  (most engines; and always true for a mod you cannot rewrite) → state transfer.
- **What is authoritative?** For a mod, the host (or a server you run) owns the shared world, and each player
  usually owns their own character (see the co-op default below).
- **What has to cross the wire?** Inputs (lockstep), or state (client-server), or both (hybrid).

The rules from `skills/mod-any-game/references/safety.md` still hold. In a co-op mod, each player runs their own
copy and the mod's traffic goes over its own transport (direct UDP, a VPN, a relay you run). It never goes
through the game's official online services, and it never touches a client protected by anti-cheat. PvP mods
are for servers the user runs.

## How

### The two fundamental models

A game is a pure function `(state, inputs) -> new_state`. Two ways to share it (Mikola Lysenko's framing in
[Replication in networked games](https://0fps.net/2014/02/10/replication-in-networked-games-overview-part-1/)):

| | Determinism / lockstep | State transfer / client-server |
|---|---|---|
| On the wire | **inputs only**, peers | **state**, one authority |
| Runs the sim | every peer, whole world | server, then broadcasts |
| Needs determinism | yes (bit-exact) | no |
| Bandwidth | tiny (inputs) | grows with world/entities (mitigated by deltas) |
| Cheat resistance | tampered state desyncs, but every peer holds the whole world (map hacks) | high if server-authoritative |
| Cost | none (or a cheap relay) | server CPU + bandwidth |
| Fits | RTS, turn-based, 4–8 player | FPS, co-op, MMO, large worlds |
| Variants | delay-based; **rollback (GGPO)** | snapshot interpolation; **state-sync** (hybrid) |

- **Rollback (GGPO)** = lockstep + predict the remote input ("carry the last one forward") + on a wrong
  guess restore the state saved at that frame and re-simulate to the present, inside one render frame.
  Needs cheap whole-state save/restore.
- **State-sync (hybrid)** = run the sim on both sides, exchange inputs *and* state, let state correct drift.
  No perfect determinism needed; highest implementation effort.

For a **co-op mod**, the practical default is **distributed authority** on top of state transfer. Each player
owns and simulates their own character with the game's own code, sends its state, and shows the other players
as puppets with snapshot interpolation. The host owns the shared world (flags, pickups, doors) and arbitrates
claims on it, and either owns the AI or hands each enemy to the player fighting it. Glenn Fiedler's
[network-model guide](https://mas-bandwidth.com/choosing-the-right-network-model-for-your-multiplayer-game/)
names this as the model to consider when converting an existing single-player game, and the co-op mods under
`Seen in` all work this way. Full server authority with client prediction and reconciliation needs the host to
simulate every player's movement from their inputs, which a mod can rarely make the game do. Keep it for games
that already ship a server simulation (tModLoader, a server you run).

### Topologies

| Topology | What it is | Notes |
|---|---|---|
| P2P | peers exchange inputs/state directly | lockstep RTS, rollback fighters; needs NAT punch; lag-switch exposed |
| Client-server (dedicated or host) | one instance owns the real sim | FPS/co-op/MMO; cheat-resistant; needs prediction to feel good |
| Relay | dumb forwarder, no simulation | NAT fix + hides IPs (Steam Datagram Relay); fighters over relay |
| Distributed authority | each client owns some objects | Unity NGO; cheap, spreads sim cost, weaker security, flaky late-join |

### Core techniques (authoritative client-server)

The server runs a fixed-timestep loop; clients predict and interpolate.

```text
while running:
    tick += 1
    for client in clients:
        inputs = buffer.pop_for_tick(tick)      # buffered, maybe late
        simulate_player(client.player, inputs)  # server is physics authority
    run_game_logic(tick)                        # combat, scoring, pickups
    history.record(tick, world.snapshot())      # for lag compensation
    for client in clients:
        send(client, delta(relevant_state(client)), ack=client.last_input_seq)
```

- **Client-side prediction.** Apply your own input immediately, tag it with a sequence number, keep
  unacked inputs + predicted state in a ring buffer, then send it. Without this, every press costs a full
  RTT.
- **Reconciliation.** When a snapshot acks input `n`: snap the local state to the authoritative state and
  **replay every input after `n`**. Snapping without replaying stutters every packet. Blend small
  corrections over a few frames (Source `cl_smoothtime`).
- **Interpolation.** Remote players/AI cannot be predicted; buffer 2+ snapshots and render them ~100 ms in
  the past (Source `cl_interp 0.1` at 20 snapshots/s).
- **Lag compensation.** Server keeps ~1 s of hitbox history; on a fire command it rewinds candidates to
  when the shooter saw them (`now − one-way latency − shooter's interp delay`), tests, restores.
- **Snapshots + delta compression.** Send each client the diff vs the last snapshot it **acknowledged**;
  bitmask of changed fields + values, compact binary. A lost ack self-heals (next delta uses an older
  baseline). Resend recent snapshots redundantly so loss doesn't stall.
- **Interest management.** Send only entities near/visible to each client (spatial index + range query).
  Entering entities get a full spawn snapshot; leaving get a despawn.
- **RPC vs replicated state.** State = "what is" (unreliable, latest-wins). RPC = "what happened"
  ("play impact", "you died") on a reliable channel. Client→server RPCs are always validated.
- **Transport.** UDP with your own sequencing/acks (never TCP for the hot loop — head-of-line blocking
  stalls the stream). ENet, GameNetworkingSockets, Unreal/Unity transports, QUIC/WebTransport.

### AI / NPC sync

Rule: **the server/host owns the AI; never trust the client** (same reason as movement). The host computes
decisions and replicates resulting state; clients render it. If the AI is deterministic and clients run the
same code they can predict and correct only on disagreement — small deltas left alone, medium interpolated
back, large snapped.

In co-op between friends, trust matters less than latency and the game's own AI assumptions. TUNIC's co-op
mod gives each enemy to the nearest player (handoff with about 4 m of hysteresis): the unmodified AI then
chases its local player, and the owner streams its state to the others.

### Interaction sync

1. Client detects an interaction → sends a **request** (event object / RPC).
2. Host **validates** it (type whitelist, ownership, distance, NaN/inf guards, rate limits).
3. Host mutates authoritative state.
4. Host broadcasts/replicates the result, or sets a dirty flag the next sync cycle picks up.

Late-join/reconnect always does a **full snapshot**; steady state sends increments. Design the join path
explicitly.

### What the mods actually do (patterns worth copying)

- **Tiered bands** (KCD2-MP): FAST ~20 Hz transforms/velocity/anim (unreliable, latest-wins); SLOW ~2 Hz
  vitals/equipment; RARE on-change appearance/role + join snapshot (reliable).
- **Periodic complete snapshot + validated action** (FS25 NPCFavor): `NPCStateSyncEvent` sends the whole NPC
  roster every 5 s, on state changes and on join, in pages of at most 50 records with a sequence number, so an
  older snapshot never replaces a newer one. Client→server interaction events are validated server-side.
- **Change-only serialization** (King Arthur's Gold Sync): objects implement serialize/deserialize; the
  framework syncs an object only when its bytes change, 16-bit id overhead, auto-assigns free ids.
- **Server owns NPCs + extra-AI payload** (Terraria/tModLoader): `npc.netUpdate` syncs the NPC; extra AI
  fields ride along; projectiles are owner-authoritative; player data is diffed against a snapshot.
- **Own avatar + puppets + owner-arbitrated claims** (the co-op mods under `Seen in`): each player sends their
  own character's state (Dishonored: 30 Hz snapshots, 100 ms interpolation) or actions (AC4Coop replicates
  actions so the puppet animates itself). Shared pickups are credited once through a claim the owner arbitrates
  (TUNIC: first claim wins).

### Choosing a model

| Game | Model |
|---|---|
| RTS, thousands of units | deterministic lockstep (+ relay) |
| Fighting, twitch 1v1 | GGPO rollback |
| FPS / co-op / open world / MMO | client-server + prediction/interpolation/lag-comp |
| Turn-based / board | every-frame or global timestamp (latency irrelevant) |
| Casual co-op mod, no dedicated server | distributed authority: each player owns their character, the host owns the world, AI owned by the host or per enemy |

## Gotchas

1. **Player rubber-bands on every packet. Cause:** reconciliation snaps to the server state but does not
   replay the still-unacked inputs. **Fix:** on ack, snap and replay inputs `n+1..present`; blend the
   visual correction over a few frames.
2. **Two machines desync in lockstep. Cause:** float non-determinism across compilers/SIMD (FMA,
   transcendentals, x87 vs SSE, `-ffast-math`), seeded-RNG call-count mismatch, or iteration order over
   pointer-keyed containers. **Fix:** fixed-point math (or tightly controlled float), fixed timestep,
   synchronized RNG with an identical number of calls, sorted iteration, per-frame state checksum.
3. **Game slows to the worst connection / stutters when a packet is late. Cause:** lockstep waits for the
   slowest peer's input. **Fix:** local input delay, a relay with a notion of time, or rollback instead of
   waiting.
4. **One lost packet freezes the whole stream for ~1 RTT. Cause:** running the realtime stream over TCP
   (head-of-line blocking). **Fix:** UDP with a partial-reliability layer (ack bitfield, re-send only what
   matters); keep TCP for login/matchmaking/chat.
5. **A late joiner sees an empty or wrong world. Cause:** no explicit full-state path; only steady-state
   deltas exist. **Fix:** a dedicated bulk-snapshot-on-join path (NPCFavor's paged `NPCStateSyncEvent`, KAG
   full serialize), and test it — this is the thing that "works most of the time but not always".
6. **NPCs disagree between players / teleport. Cause:** AI was client-authoritative or non-deterministic
   while clients also simulated it. **Fix:** make the host own the AI and replicate its state, or make the
   AI fully deterministic with synced inputs; only correct clients when the host disagrees.
7. **Constant NPC jitter. Cause:** snapping small corrective deltas. **Fix:** threshold corrections —
   ignore tiny deltas, interpolate medium ones, snap only large ones (tune by playtesting under bad nets).
8. **"I hit them on my screen but the server says miss." Cause:** no lag compensation, and the shooter's
   interpolation delay wasn't accounted for. **Fix:** server rewinds targets by `latency + interp delay`
   before the hit test.
9. **Bandwidth explodes with many entities. Cause:** full snapshots to every client. **Fix:** delta vs the
   last acked snapshot + interest management (send only what's near/visible).
10. **Cheaters teleport / one-shot through walls. Cause:** trusting the client's position or damage.
    **Fix:** server-authoritative; clients send intent, the server simulates and validates every
    interaction.
11. **Rollback spikes into a "spiral of death". Cause:** re-simulating a large state for many frames each
    render frame on a CPU-bound game. **Fix:** add 2–3 frames of input delay, cap the rollback window, and
    do not attempt full-state rollback for large multiplayer states (it fits small 2-player P2P).
12. **Everything is fine in the lab, breaks on the internet. Cause:** testing on LAN/no jitter.
    **Fix:** simulate latency, jitter and packet loss during development; checksum state to catch desyncs
    early.

## Seen in

Co-op mods in this knowledge base, and the sync choices they made:

- [Seamless co-op for TUNIC](../games/tunic/seamless-coop-bepinex6-native-hooks.md): 2-8 players over
  LiteNetLib in a star with the host relaying; puppets with 100 ms snapshot interpolation; shared world flags
  and inventory; per-enemy ownership by proximity with hit forwarding; owner-arbitrated pickup claims.
- [Ghost co-op for Dishonored](../games/dishonored/ghost-co-op-ue3-reflection-postrender-hook.md): the DLL's own
  UDP host/join, 30 Hz snapshots and 100 ms interpolation driving a puppet body.
- [Working two-player co-op in AC4 Black Flag](../games/assassin-s-creed-iv-black-flag/coop-two-player-udp-bind-in-the-live-game.md)
  and [spawning a real second player](../games/assassin-s-creed-iv-black-flag/spawning-a-real-second-player-in-ac4-black-flag-the-working-.md):
  Kamzik123's AC4Coop spawns a puppet for the peer and drives it by action replication over its own UDP.
- [A visible, driven second character in AC4 single-player](../games/assassin-s-creed-iv-black-flag/coop-ghost-avatar.md):
  a second avatar driven over the plugin's own P2P UDP.
- [AnvilNext internals for AC Rogue co-op](../games/assassin-s-creed-rogue/anvilnext-internals-for-ac-rogue-co-op-player-transform-the-.md):
  the player transform and the set-transform path a replication layer would write to.

External multiplayer mods whose patterns are summarised above:

- Terraria / tModLoader *Basic Netcode* — https://github.com/tModLoader/tModLoader/wiki/Basic-Netcode
- Farming Simulator 25 *NPCFavor* — https://github.com/TheCodingDad-TisonK/FS25_NPCFavor
- King Arthur's Gold *kag-sync* — https://github.com/eps0003/kag-sync
- Kingdom Come: Deliverance 2 MP *kcd2-exports* — https://github.com/Jefferson25625/kcd2-exports
