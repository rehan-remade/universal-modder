---
kind: game
title: 'Running a self-hosted AzerothCore WotLK server with 1,500 playerbots: setup, performance and the traps'
game: World of Warcraft
games_also: []
game_version: 'AzerothCore WotLK (3.3.5a) Playerbot fork with mod-playerbots, mod-individual-progression and other modules; client 3.3.5a build 12340'
platform: linux
engine: native
route: other
tools: [AzerothCore, mod-playerbots, MySQL 8.4, Debian 13, WSL2, tmux, gdb, systemd]
anti_cheat: 'not applicable: the user''s own server'
status: working
agents:
- Claude Code (Opus 5.5)
humans: [RedSuper]
date: '2026-10-04'
links: ['https://github.com/azerothcore/azerothcore-wotlk', 'https://github.com/mod-playerbots/mod-playerbots', 'https://github.com/ZhengPeiRu21/mod-individual-progression']
tags: [private-server, azerothcore, playerbots, performance, mysql, wsl2, vps, build, operations]
---
# Running a self-hosted AzerothCore WotLK server with 1,500 playerbots: setup, performance and the traps

> A single-player-with-bots WotLK server: AzerothCore's Playerbot fork, 1,500 random bots plus a raid roster of
> account bots, manual raid progression, and a dozen modules. It started in WSL2 on a gaming laptop and moved to a
> small VPS. This note is the operations side: what had to be installed how, what actually costs CPU, how builds
> and restarts behave, and the database traps that cost the most time.

## Setup
- **Core:** the Playerbot fork of AzerothCore (`mod-playerbots/azerothcore-wotlk`, branch `Playerbot`); upstream
  AzerothCore does not work with mod-playerbots. Modules are static and auto-discovered by folder.
- **OS:** Debian 13 in WSL2 (systemd on), later a Debian 13 VPS (8 shared vCPU, 16 GB). Same glibc on both, so the
  binaries copied over without a rebuild.
- **Database:** MySQL 8.4 from Oracle's repository, not MariaDB (`caching_sha2_password` needs Oracle's
  libmysqlclient).
- **Processes:** authserver and worldserver in tmux sessions under a service wrapper (`systemctl start|stop`).

## Route and why
Server-side only. Everything in this note is configuration, scripts and small core/module patches; the client is
a stock 3.3.5a client pointed at the server.

## How the game works (what we had to learn)
**Processes and console**
- authserver exits with code 0 when its stdin hits EOF: it needs a TTY (tmux), not a FIFO or nohup.
- The realm shows "Offline" while `realmlist.flag = 2`; set it to 0 at each start.
- tmux targets: `-t acore` prefix-matches `acore_auth` when the world session is gone; use `-t '=acore'` for session
  commands and `'=acore:0.0'` for `send-keys` / `capture-pane`.

**Performance**
- Each map updates on one thread, and the tick waits for all maps: `MapUpdate.Threads = 1` made the whole world wait
  on one core. Setting 4 took the median tick from 55 ms to 7 ms and p95 from 295 ms to 55 ms (found with gdb
  sampling after three wrong theories).
- At 1,500 bots the CPU is not bot AI: it's `Map::UpdateNonPlayerObjects` → creatures ticking in grids that bots
  keep loaded. Idling the AI changes nothing; bots must leave the world.
- "Raid mode" for raiding: random-bot pool 20 + random-bot autologin off → 0 random bots online, chatter bridges
  off. World tick in a raid went from 170–250 ms to normal. **Never set `MaxRandomBots = 0`:** it unassigns every
  random-bot account.
- An LLM chatter bridge polling MySQL cost ~28% CPU plus heavy DB load; a local LLM on the gaming GPU caused the
  client's frame spikes (VRAM). Both were removed.

**Builds**
- Build time follows include fan-out: touching `PlayerbotAI.h` rebuilds ~30 minutes; a leaf header or one `.cpp`
  about a minute plus the link. **Adding a module folder** regenerates the module loader and recompiles all ~700
  module objects. `make install` is a separate step.
- Building on the live machine makes the game unplayable; build on another machine and copy the binary, installed
  with `DESTDIR` so its RUNPATH points at the server's lib folder.
- Compile the changed files against the real headers before the full build, so errors surface in a minute.

**Configuration and data**
- `.reload config` only re-reads part of the settings (for playerbots: chat rates and random-bot levels); many
  settings and every DBC override table need a restart.
- DBC override tables (`spell_dbc`, `item_dbc`, `creaturedisplayinfo_dbc`, …) **augment** the client DBCs by id;
  the server validates creature displays against its own copy (a new mount needs those rows too), item displays are
  not validated.
- Log levels are inverted (0 disabled … 4 info … 6 trace); appenders in mode `w` truncate logs at every reload, use `a`.
- Online characters' rows are stale until `.saveall` (inventory, kills, quests).
- Items can be given to offline characters in the DB without a restart by using new item guids far above the current
  maximum (the running server's counter can't reach them before the next start).
- `GROUP_CONCAT` silently truncates at 1,024 bytes (a delete-by-list removed 268 of 1,670 rows).
- An idle socket is closed without a log line; and the 3.3.5a client itself logs out after 30 idle minutes (a
  hard-coded client timer, not the server).

**Crashes**
- A world-server segfault whose fault address equals the stack pointer in the kernel log is a stack overflow on a
  map thread; read the frame's library offset with `addr2line`/gdb against the installed binary to find the leaf.
- Core dumps: `ulimit -c unlimited` inside the tmux command does nothing when the tmux server itself was started
  with a hard core limit of 0. Raise it on the running process instead (`prlimit --pid <worldserver pid>
  --core=unlimited:unlimited`, as root, right after launch). Each core is about the size of the process (~8 GB
  here); keep gdb on the server.
- The nightly database dumps doubled as evidence: diffing a character's learned spells between two dumps showed what
  changed the day the crashes began.

## Build steps
1. Install MySQL 8.4 (Oracle repo), the build deps (boost, OpenSSL 3, readline, zstd), clone the fork + modules.
2. `cmake` with the server prefix, `make -jN`, `make install`; copy and edit the module `.conf.dist` files.
3. Start scripts: MySQL up, `realmlist.flag = 0`, authserver and worldserver in tmux; stop scripts send `.saveall`
   and `server shutdown` and wait.
4. Nightly `mysqldump --single-transaction` + zstd with rotation, and a restore check into a scratch DB.
5. Monitoring: tick time percentiles from the world's own update-time log, process CPU/RSS by exact process name
   (`pgrep -x`; `-f` matched the tmux wrapper).

## Verification
- Tick percentiles before/after every performance change (`MapUpdate.Threads`, raid mode, removing chat bridges).
- Restore check of every backup into a scratch database (row counts match live).
- Bot persistence across restarts (characters, guilds) checked in the DB.

## Gotchas
1. **Whole-server lag spikes.** **Cause:** `MapUpdate.Threads = 1`. **Fix:** 4 threads; measure with gdb, not by
   guessing bot counts.
2. **All random bots lost their accounts.** **Cause:** `MaxRandomBots = 0` runs an unassign of every random-bot
   account. **Fix:** any non-zero pool, with autologin off.
3. **authserver kept dying.** **Cause:** EOF on stdin. **Fix:** run it in tmux.
4. **Console commands went nowhere.** **Cause:** tmux prefix matching sent them to the authserver session. **Fix:**
   exact targets (`'=acore'`, `'=acore:0.0'`).
5. **A ten-minute build took ninety.** **Cause:** throttled `-j` and `nice` on a laptop. **Fix:** full parallelism,
   server stopped, or build elsewhere.
6. **"The setting didn't apply."** **Cause:** `.reload config` doesn't reload it. **Fix:** check whether the module
   reads it in a reload hook; otherwise restart.
7. **A new mount crashed nothing but logged "non-existing CreatureDisplayID".** **Cause:** the server validates
   displays against its own DBC copy. **Fix:** add the matching `creaturedisplayinfo_dbc` / `creaturemodeldata_dbc`
   rows and restart.
8. **Logs disappeared after a reload, which looked like a stall.** **Cause:** appender mode `w`. **Fix:** mode `a`.
9. **DB reads disagreed with the game.** **Cause:** online data not yet saved. **Fix:** `.saveall` first, always.
10. **A test runner restarted the live server twice.** **Cause:** it invoked the live script, which ignored the
    test's path overrides. **Fix:** tests run only the candidate copy, never a live script.
11. **Crashes left no core file.** **Cause:** the tmux server's hard core limit of 0 is inherited, and a shell
    `ulimit` can't raise a hard limit. **Fix:** `prlimit` on the world server's pid from the start script.
12. **Two crashes in a row in the same raid, only after a quiet day.** **Cause:** a playerbots value recursing forever
    (see the playerbots note: a newly learned transmute closed a recipe loop). **Fix:** found by diffing the nightly
    dumps and reading the code, not by reproducing on the live server.

## Open questions
- Navmesh "could not load tile" errors after grid unloads are harmless here (the tile stays loaded); not upstreamed.
