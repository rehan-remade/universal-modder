---
kind: game
title: Slow in-game clock and slower need decay per need (drops only, optional Energy refill %), as a Cheat Engine table
game: The Sims Legacy Collection
games_also: [The Sims]
game_version: Steam 3314060, Sims.exe PE timestamp 0x67e72e1b, changelist.txt 936127
platform: windows
engine: native
route: native-hook
tools: [Cheat Engine, Python ctypes (ReadProcessMemory/WriteProcessMemory), capstone, keystone]
anti_cheat: none (offline game); Sims.exe is wrapped in SteamStub (see Gotchas)
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-11-15'
links:
- https://github.com/riperiperi/FreeSO
- https://github.com/cheat-engine/cheat-engine
tags: [the-sims, simantics, clock, time-scale, motives, need-decay, cheat-engine, steamstub, x86]
---
# Slow in-game clock and slower need decay per need (drops only, optional Energy refill %), as a Cheat Engine table

> The Sims 1 (Legacy Collection) clock runs so fast that washing a face costs 30 game minutes and cooking plus
> eating costs 2 hours. This mod slows only the clock (50% by default, down to 5% or any 50%/N) while ticks,
> animations and need decay keep their real-time speed. Everything that reads the clock (day/night, carpool,
> work hours, wake hour) follows the slower clock. It is a Cheat Engine Auto Assembler hook; no game file is
> changed. The hook was measured live (game seconds per tick 2.00 -> 1.00 -> 0.10, tick rate unchanged) and the
> user played with it at 5% and then confirmed the finished .CT table works in game.
> A second section of the same table slows need decay: a global % plus an optional own % per need (Hunger,
> Comfort, Hygiene, Bladder, Energy, Fun, Social). Only drops are scaled, so eating, showers, the toilet and so on
> refill at normal speed. Energy's sleep refill (which the game does inside the decay step) gets its own % or can
> follow the Energy decay %. User-verified in game.

## Setup
- The Sims Legacy Collection, Steam app 3314060, Windows 10 22H2 x64. `Sims.exe` is 32-bit, PE timestamp
  0x67e72e1b, `changelist.txt` = 936127. ASLR is on (image base moves every run), so all addresses below are
  RVAs (offsets from the module base, i.e. `Sims.exe+RVA` in Cheat Engine). Steam's public build has been
  17905164 since 2025-04-03 (SteamCMD), which fits the PE timestamp (2025-03-28).
- No mods or loaders installed. Cheat Engine 7.x for the final table.
- Analysis: Python 3 with capstone (disassembly) and keystone (assembling the test hook); see Gotcha 1 for why
  the analysis reads the running process instead of the file.

## Route and why
- Considered: an on-disk exe patch (one byte). Rejected: `.text` is encrypted on disk (SteamStub), and the user
  wanted no exe changes for this game.
- Considered: data/SimAntics edits (halving every interaction's duration). Rejected: hundreds of objects, and the
  real issue is one engine rate.
- Chosen: a code hook in memory, delivered as a Cheat Engine table (AOB scan, so it survives ASLR).

## How the game works (what we had to learn)
- **Globals / clock object.** A singleton pointer at RVA 0x667044; `[singleton+0x1c]` is the object that holds
  the SimAntics globals as 16-bit values at `+0x10 + 2*index`. Index 0 = hour, 4 = time-of-day period
  (night/morning/day/evening, recomputed when the hour changes), 5 = minute, 6 = minute fraction ("seconds",
  0..59). `+0x98` of the same object is the sim tick counter. A generic "set global" setter is at RVA 0x157340;
  the `set_hour` cheat calls RVA 0x157260.
- **Clock step.** The sim loop (RVA 0x157480) calls the clock tick (RVA 0x1576f0). If the sim step (RVA
  0x157a00) actually ran, the tick counter is incremented and global 6 gains **2** (`add ax,2` at RVA
  0x15773d). At 60 it wraps into a minute (and fires a "new minute" event), minutes wrap into hours, hours into
  days/months. So vanilla is 30 ticks per game minute, i.e. 1 game minute per real second at normal speed,
  24 real minutes per game day. The open-source reimplementation FreeSO uses the same 30 ticks/minute for TS1.
- **Need decay is tick based.** The sim step passes the tick counter to every object's update (vtable slot
  +0x14). The person update (RVA 0x1f4f90) runs the motive decay step (RVA 0x2833f0) when the tick counter has
  advanced 60 past the value it stored last time (`[person+0x814]`). 60 ticks = 2 game minutes in vanilla, which
  matches FreeSO's "decay every 2 game minutes", but in the real exe it is counted in ticks, not clock minutes.
  So slowing the clock does not slow need decay in real time. The decay step reads the clock only for hour
  checks (wake hour, daytime energy drift).
- **Motive tuning** (energy span 180, wake hours 16, wake hour 7, energy drift, hunger/bladder/hygiene/social/
  fun/comfort rates, three variants selected by a person flag) is loaded by name with these defaults around RVA
  0x282fc0 into float arrays at RVA 0x67e240..0x67e330. Useful if someone wants to rebalance decay instead.
- **Motive block.** Each Sim has 16 floats (range -100..100) at `person+0x790`, indexed like FreeSO's `VMMotive`
  enum: 5 Energy `+0x14`, 6 Comfort `+0x18`, 7 Hunger `+0x1C`, 8 Hygiene `+0x20`, 9 Bladder `+0x24`, 11 sleep
  state `+0x2C`, 13 Room, 14 Social `+0x38`, 15 Fun `+0x3C`. `+0x40..+0x7C` holds a copy of the values at the end
  of the previous decay step; `+0x80` points back to the person.
- **What one decay step (RVA 0x2833f0, ecx = motive block) does, in order:**
  - Energy: adds the awake rate (minus energy span / wake hours, scaled per step) or, while asleep, the asleep
    rate, which is **positive: the basic sleep refill is part of the decay step**. A small drift is subtracted
    while asleep inside the wake-hour window.
  - Bladder: if Hunger rose since the previous step (the Sim ate), Bladder drops by 0.3 x that rise.
  - Comfort: drops by a base plus a personality-weighted amount (a person-data field at `person+0x596`).
  - Hunger: drops by ratio x (100 + Hunger), so a full Sim gets hungry faster than an empty one.
  - Social (awake only): drops by a base plus outgoing-personality x multiplier (`person+0x59C`).
  - Hygiene, Bladder: awake or asleep rates. Fun: an awake rate, or multiplied by a factor while asleep.
  - Then a loop clamps all 16 to -100..100 and copies them to `+0x40..`, and it tail-jumps to the mood update.
  - Activity costs (working out, hours at work) and all refills from objects are SimAntics/motive-change code,
    not part of this step.
- **Game speed buttons** change how many sim ticks run per real second; the clock step per tick is unchanged.
  So the mod's percentage applies at every game speed.

## Build steps
1. Cheat Engine: attach to `Sims.exe`. The block below is an Auto Assembler script, not a `.CT` file: open
   Memory View > Tools > Auto Assemble, paste it, use File > Assign to current cheat table, name the entry
   "Slow clock" and save the table as `Sims Slow Clock.CT`. Tick "Slow clock". Default 50% (48 real minutes per
   game day at normal speed).
2. The child entry "Clock speed" (`sc_div`) picks the rate: 1 = 50%, 2 = 25%, 4 = 12.5%, 10 = 5%; any whole N
   gives 50%/N. Untick for vanilla.

The hook replaces `mov ax,[edi+1C]; add ax,2` (8 bytes) with a jump to a cave that adds `sc_step` (1) to the
minute fraction only every `sc_div` ticks, then jumps back to the original wrap check (`+0x0F`). On skipped
ticks it jumps to the code after the whole minute/hour block (`+0x17A`, the same target as the original `jl`).

```
[ENABLE]
aobscanmodule(simsclock,Sims.exe,66 8B 47 1C 66 83 C0 02 0F B7 C0 66 89 47 1C 66 83 F8 3C 0F 8C)
alloc(sc_mem,$100)
label(sc_skip)
label(sc_count)
label(sc_div)
label(sc_step)
registersymbol(simsclock)
registersymbol(sc_div)
registersymbol(sc_step)

sc_mem:
  inc dword ptr [sc_count]
  mov eax,[sc_count]
  cmp eax,[sc_div]
  jb sc_skip
  mov dword ptr [sc_count],0
  mov ax,[edi+1C]
  add ax,word ptr [sc_step]
  movzx eax,ax
  mov [edi+1C],ax
  jmp simsclock+0F
sc_skip:
  jmp simsclock+17A

sc_count:
  dd 0
sc_div:
  dd 1
sc_step:
  dd 1

simsclock:
  jmp sc_mem
  nop 3

[DISABLE]
simsclock:
  db 66 8B 47 1C 66 83 C0 02

unregistersymbol(simsclock)
unregistersymbol(sc_div)
unregistersymbol(sc_step)
dealloc(sc_mem)
```
### Slower need decay (second script in the same table)
Two hooks on the decay step, both AOB-scanned (both patterns unique in this build):
- Entry (`53 56 57 8B B9 80 00 00 00 33 D2 0F BF 9F 12 06 00 00`, 9 bytes stolen): copy the 16 motive floats to
  a snapshot buffer, run the stolen prologue, jump back to `+9`.
- After the last decay write, before the clamp loop (`8B D1 F3 0F 11 59 3C 33 C0 F3 0F 11 0C 17 5F F3 0F 11 06
  F3 0F 10 0D`, 19 bytes stolen, all position-independent; return to `+0x13`): for each need,
  `new = old + (new - old) * pct / 100`, applied only if `new < old`. For Energy it also applies to rises, using
  "Energy refill %" (default 100) or, if the "refill follows decay" flag is set, the Energy decay %.
- pct = the need's own value when its own flag byte is set, else the global value. Every value is a symbol
  (`nd_all`, `nd_pct+4*k`, `nd_own+k`, `nd_rpct`, `nd_rfollow`), so the table shows them as plain float/byte
  records with dropdowns, and each "own %" checkbox is a tiny AA script that sets its flag byte.
- Hooking before the clamp matters: the clamp loop also writes the "previous values" copy at `+0x40`. Scaling
  after it would leave that copy unscaled, the next step would read the corrected Hunger as "the Sim ate", and
  it would wrongly drop Bladder.

In the .CT, add a 4-byte child record at address `sc_div` with a dropdown list (`1:50%`, `2:25%`, `4:12.5%`,
`10:5%`) and "hide children when deactivated". The AOB is unique in this build.

## Verification
- Oracle: a ReadProcessMemory watcher that samples the tick counter (`+0x98`) and globals 0/5/6 over a fixed
  real-time window and reports game seconds per tick and ticks per second.
  - Vanilla: 2.00 game s/tick. One-byte test (`add ax,1`): 1.00. Hook with div 10: 0.10. Ticks per second were
    the same in all three (about 300/s at the speed the user was playing), so the simulation rate was unchanged.
- Need decay was confirmed tick-based from the code path (tick counter -> person update -> every 60 ticks), not
  by sampling motive values over time.
- The user played with the hook at 5% and confirmed it works (interactions take far fewer game minutes).
- The user loaded the finished .CT in Cheat Engine and confirmed it works in game (2026-11-15).
- Need decay section: the user played with it and confirmed it works as expected, first the drops-only version,
  then the Energy refill options (follow decay / own %). Judged in game by the need bars; motive values were not
  logged.
- NOT verified yet: long-term effects on work shifts, sleep length, bills, plant/food timers, expansion packs' clock-based events
  and save/load while hooked.

## Gotchas
1. **The exe on disk is unreadable (entropy 8.0 in `.text`).** Cause: SteamStub; there is a `.bind` section and
   the entry point is inside it. Fix: for analysis, read the image from the running process after start-up (the
   wrapper has decrypted it by then), and keep any dump of it private, outside any repo. Do not ship a modified
   exe; a memory hook (CE table, live tool) avoids touching the wrapper at all.
2. **Memory dump at 0x400000 gave wrong string addresses.** Cause: ASLR is on (DllCharacteristics 0x8140), the
   image was at 0x270000 that run. Fix: get the module base (EnumProcessModulesEx) and work in RVAs; absolute
   pointers inside the dump are relocated to that run's base.
3. **Setting the step to 0 or below 1 is not possible with the one-byte patch.** Cause: 1 game second per tick
   is the smallest whole step. Fix: the divider hook (advance only every Nth tick).
4. **Reading FreeSO alone would suggest decay follows the clock.** FreeSO's TS1 decay checks the clock minute
   (every 2 game minutes). The real exe counts 60 ticks instead, so the clock can be slowed without touching
   decay. Check the exe before adding a decay compensation.
5. **Slowing Energy decay alone makes a short nap last all day.** Cause: the sleep refill is inside the same
   decay step and a "drops only" rule leaves it at full speed while the drain is slower. Fix: let Energy rises
   use their own % or follow the Energy decay % (user's choice, a checkbox).
6. **Bladder at 0% also stops "eating fills the bladder".** Cause: that bladder drop happens in the decay step.
   It is intended here (it is a drop), but worth knowing.
7. **Live tool and CE table conflict.** If a hook is already in place (or the one-byte test changed `02` to
   `01`), the CE AOB scan fails. Restore the original 8 bytes first.

## Assets
None.

## Cost and time
One session: about two hours to a working live hook and the clock table, about one more hour for the need decay section.

## Open questions
- Sleep: with the slow clock a night is shorter in game hours (refill is tick based); the Energy refill % now
  lets the player compensate. Do beds also add energy through their own object script (that part is not scaled)?
- Work shifts last longer in real time; are motive changes at work applied per game hour (fine) or per tick?
- Do any expansion-pack objects time things in ticks while expecting clock minutes (e.g. food spoilage, plants)?
