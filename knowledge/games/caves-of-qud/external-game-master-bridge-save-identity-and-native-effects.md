---
kind: game
title: "An external game master for Caves of Qud: a scripting-mod bridge, save identity and native effects"
game: "Caves of Qud"
games_also: []
game_version: "Steam, Windows, runs on 2026-08-29 to 2026-08-31; exact game build not recorded"
platform: windows
engine: unity-mono
route: loader-api
tools: ["Qud C# scripting mods", ".NET netstandard2.1 / C# 9", "Mono.Cecil (inspecting the installed assemblies)", "Python", "SQLite"]
anti_cheat: "none; single-player, disposable test worlds"
status: in-progress
agents: ["Codex (GPT-6)"]
humans: ["jkjkj2805"]
date: 2026-10-13
links: ["https://wiki.cavesofqud.com/wiki/Modding:Overview"]
tags: [bridge, game-thread, save-load, rewind, idempotency, parts, effects, quests, autoexplore, ai-game-master]
---

# An external game master for Caves of Qud: a scripting-mod bridge, save identity and native effects

> A C# scripting mod connects Caves of Qud to an external Python program (an AI game master called Randur)
> over a loopback socket, without ever touching game objects off the game thread. In real runs it survived
> reconnects and a save/reload, created NPCs, items, effects, reputation changes and an owned side quest
> through the game's own systems, and didn't repeat any of them when the same command was replayed. The
> bridge itself is private; this note records what the game does and the traps, so you can build your own.

## Setup
- Caves of Qud on Steam (Windows). The runs were on 2026-08-29 to 2026-08-31; the exact game and Unity build
  wasn't recorded, so don't read this as "works on the latest build".
- The mod is a Qud C# scripting mod. Its project targets `netstandard2.1` / C# 9 and references the installed
  `Assembly-CSharp.dll` and `Newtonsoft.Json.dll`. Mono.Cecil was used to read the installed method signatures
  and bodies (nothing decompiled is published).
- Test in a copied profile with a disposable save. Credit: Freehold Games, and the Qud wiki's
  [modding overview](https://wiki.cavesofqud.com/wiki/Modding:Overview) for the scripting route. The wiki's
  Modding pages cover `[HasCallAfterGameLoaded]`/`[CallAfterGameLoaded]`, `StatShifter`, quests and
  conversations.

## Route and why
Qud compiles and loads C# scripting mods itself, so no external loader is needed. The external program only
ever sees plain data objects:
- In a `[CallAfterGameLoaded]` method (on a class marked `[HasCallAfterGameLoaded]`), capture the game thread's
  `SynchronizationContext` and post every game
  access to it. A worker thread does the socket I/O and never dereferences a Qud `GameObject`. Thread-safe JSON
  serialisation doesn't make game access thread-safe.
- The bridge took a snapshot about every 500 ms and ran at most one queued action per snapshot.
- Actions are a fixed list of narrow, typed capabilities with allowlists (no arbitrary blueprints, reflection,
  console passthrough or generated C#). The game checks legality, runs the effect on the game thread and then
  re-reads the game state to report what actually happened.

## How the game works (what we had to learn)

### Which identity survives what
| Identity | What it is | Don't use it as |
| --- | --- | --- |
| `XRLGame.GameID` | The save/world. A normal reload keeps it | The player's name or the bridge connection |
| Bridge session | One connection between the mod and the external program | The world, or proof of save lineage |
| Timeline generation | A counter the mod bumps on a rewind (below) | A durable save-lineage proof |
| Game object ID | An object seen in the current scope | A permanent identity, or anything matched by display name |

The mod treats it as a rewind when the `XRLGame` object is replaced but `GameID` stays the same, or when
`Turns` goes down. On a rewind it bumps the generation and drops queued actions. The external side keeps its raw
history but stops using facts from the abandoned branch, keyed by `(Turns, TimeTicks)`. One case can't be told
apart: restoring a save at exactly the last recorded position in a new process looks like a normal restart.

### Effects through the game's own systems
These were the mechanisms behind each action in the tested run. The capability names are the bridge's own,
not a Qud API.

| Action | Game mechanism | Checked after the action |
| --- | --- | --- |
| Introduce an NPC with its own dialogue | A serialisable `IPart` handling `BeginConversationEvent` | One non-hostile NPC with the authored dialogue; same NPC after reload |
| Unique reward item | A precompiled `IPart`, equip/unequip events, `StatShifter` | One item; exactly +1 while equipped, removed on unequip; same after reload |
| Temporary stat effect | A serialisable `Effect`, `ApplyEffect`, duration, `StatShifter` | One +1 defensive modifier; duration left after reload; expired later |
| Permanent stat change | `Statistic.AddShift`, keeping the `Guid` it returns as the shift's identity | Exactly +1 base attribute; persisted; a replay didn't reapply it |
| Faction reputation | `Factions` lookup, `The.Game.PlayerReputation.Get`/`Modify` (the lowercase forms are obsolete) | One +25 change to an existing faction; persisted; not reapplied |
| Owned side quest | A fully initialised `Quest`/`QuestStep` in the quest registry | Exactly one optional one-step quest; same quest after reload |
| Advance that quest | The owned quest's objective state | Only that objective finished; visible in the journal; not repeated |
| Local encounter | Allowlisted blueprints, `Brain` and faction disposition | Two neutral creatures at a safe distance |

- `GameObjectFactory.Factory.CreateObject` plus `Cell.AddObject` create and place objects, but safe placement
  and ownership are yours to handle. A created object's name is presentation; store the owner and action ID as
  serialised properties on your part.
- **No duplicates on replay.** Each action has a stable ID and a fingerprint of its arguments, and the success is
  recorded in the game state itself (a serialised part property, the stored stat shift, or quest properties),
  not only in the external program. A replay finds the existing result instead of creating another. Reusing an ID
  with different arguments is a conflict. If the recorded object is gone, that needs a decision, not a silent
  re-creation.
- **Saves hold your types.** Parts and effects serialise their data only; sockets and request objects stay
  transient. Keeping the mod enabled with the external program offline works. Removing the mod that defines a
  saved part or effect type was not tested and shouldn't be assumed safe.
- **Readable clues:** a created book or note doesn't make its text known to the player. Treat it as known only
  once its Read action has run.
- **Autoexplore:** a mod can interrupt the player's autoexplore when a chosen object first becomes visible, but
  only if the decision is already made in the game. The bridge "arms" the exact target in advance and interrupts
  at the first visibility check (`arm_until_visible`). Waiting for the external program took about four seconds,
  by which time the player had walked past.

## Build steps
1. Copy the profile and save. Reference the installed assemblies; record their versions and hashes. Don't publish
   the assemblies or a decompiler dump.
2. In `[CallAfterGameLoaded]`, capture the game thread's `SynchronizationContext`. Snapshot on the game thread,
   pass immutable data to a loopback socket worker.
3. Require a loaded game (GameID, player, zone) before accepting actions. Tag every request with GameID, bridge
   session and timeline generation, and drop queued work when any of them changes.
4. Implement one narrow action at a time: validate on the game thread, apply the one effect, re-read the game
   state, and report "accepted", "performed" and each check separately.
5. Save and reload, reconnect, then replay the same action ID: expect the existing result and no new object or
   modifier. Also test a changed payload under the same ID, and a recorded object that has gone missing.

## Verification
- **In the real game (Steam, August 2026):** a save/reload kept `GameID`, opened a new bridge session and
  needed an explicit re-arm; owned content survived it, and an earlier restart rebuilt the same content without
  duplicates. The eight actions in the table above worked with the checks listed, including one save/reload and
  replay suppression. Strong attention interrupted autoexplore, and the weakest level didn't. An owned NPC
  survived a restart and was seen and talked to.
- **Offline tests (mocked game side):** stale connections and old sequences can't overwrite state, pending
  commands for another world are cancelled, and a lower-turn rewind excludes the abandoned branch.
- **Not verified:** the exact game build; current builds (nothing was re-run for this note); other mod
  combinations; removing the mod from a save that uses its types; multi-step quests and dialogue trees.

## Gotchas
1. **The quest is created, but the external program times out.** **Cause:** `The.Game.StartQuest` and
   `FinishQuestStep` call `PopupStartQuest`/`PopupFinishQuestStep`, UI that waits for the player after the
   state has already changed. **Fix:** register a fully initialised
   owned quest and raise the normal events without the blocking popup. A timeout doesn't mean nothing happened;
   read the game state before retrying.
2. **A new NPC speaks unrelated merchant dialogue.** **Cause:** its blueprint inherits a vanilla
   `ConversationScript`. **Fix:** remove the inherited conversation part from your NPC and handle
   `BeginConversationEvent` in your own serialised part.
3. **A replay still changes the attribute.** **Cause:** the dedup record lived only in the external program, and
   some reconnect/reload paths lost it. **Fix:** record the action in the game state and check the exact stored
   stat shift or object before changing anything.
4. **Paused menus look like a dropped connection.** **Cause:** capture pauses on the game thread while the
   transport keeps resending the last snapshot. **Fix:** accept a repeated sequence number only when the snapshot
   is identical, and don't count it as new data.
5. **Old knowledge survives a rewind.** **Cause:** `GameID` identifies the save, not the timeline. **Fix:** watch
   for a replaced `XRLGame` or falling `Turns`, drop queued work, and stop using facts from the abandoned branch.
6. **Autoexplore isn't interrupted.** **Cause:** the external round trip (about 4 s) missed the moment the
   object became visible. **Fix:** arm the exact target in advance and interrupt inside the game at first
   visibility.
7. **Reading a book the game master planted triggers yet another story beat.** **Cause:** the pickup and
   read events came from the mod's own delivery and were taken as the player's interest. **Fix:** keep the
   authored origin on later events, count a passive pickup or read as attention only, and wait for a deliberate
   act (talking, fighting) before planning more.

## Assets
None. No game binaries, saves or decompiled code are included.

## Open questions
- Which Qud build this was, and whether the same calls work on the current one.
- Whether a save that contains the mod's parts and effects loads cleanly after the mod is removed.
- A public minimal bridge would let others re-run these checks.
