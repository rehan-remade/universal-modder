---
kind: game
title: "Playing Test Drive Unlimited 2 online with Project Paradise 2 (server, NAT, migration, driver regressions)"
game: "Test Drive Unlimited 2"
games_also: []
game_version: "retail; community server current as of 2026-03"
platform: windows
engine: unknown
route: passthrough
tools: ["Project Paradise 2 server + launcher (project-paradise2.de)", "dgVoodoo2", "DXVK", "TDU2 Unpacker GUI"]
anti_cheat: "Community-run. Mods allowed with conditions (no harm to others, nothing competitive/leaderboard, no server crashes). The PP2 launcher closes the game while a process on its cheat/RE-tool list is running (Gotcha 11). No anti-cheat bypass documented."
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-05
links:
  - "https://project-paradise2.de/"
  - "https://turboduck.net/forums/topic/28390-test-drive-unlimited-2-modding-wiki/"
  - "https://github.com/djey47/tdumt2"
  - "https://github.com/Project-Paradise-2/Gamelauncher"
tags: [tdu2, project-paradise, multiplayer, p2p, nat, upnp, port-forwarding, amd, nvidia, drivers, revival-server, savegame-migration]
---

# Playing Test Drive Unlimited 2 online with Project Paradise 2

> TDU2's official servers are gone; **Project Paradise 2** (project-paradise2.de) is the community
> revival. The server is **not** matchmaking-only: it runs the full backend — accounts and profiles,
> cloud savegames, clubs, the Community Racing Center, leaderboards and the DLC-token store — and it
> places you into a session with nearby players automatically. The **lobby itself is player-hosted
> (peer-to-peer)**, so "I can see my friend on the map but not in the game" is a NAT/port problem, not
> a server fault. Separately, community reports say **AMD drivers released after February 2025 break the
> game** (rendering issues, driver timeouts, system freezes), and neither dgVoodoo2 nor DXVK fixes it —
> only a driver downgrade does (PP2's own FAQ suggests a lower Environment Detail first; Gotcha 2).

## Setup

- **Retail TDU2** (Atari/Eden Games, 2011) plus the **Project Paradise 2** server and its launcher
  (v3.1.2 when the guides were written; the download page listed 3.1.9 on 2026-10-14). Account is
  created inside the game the first time you start it.
- Community references: TurboDuck TDU2 modding wiki (turboduck.net/forums/topic/28390), `djey47/tdumt2`
  tooling, and the PP2 Discord guides (install, port forwarding, troubleshooting, modding, launcher,
  offline→online migration; last updated 2025-11-09).
- If the game crashes on start on a modern OS, that is a separate compatibility problem — see
  `running-tdu2-on-modern-linux.md` for the NULL-pointer fix and the D3D9→D3D11 route.
- **Ownership:** PP2 requires an owned copy: the DVD (or an ISO of your own disc) or Steam, per
  project-paradise2.de/install. Its FAQ lists cracked, repacked and stripped copies as unsupported. On
  first launch the game asks for its own CD key (the DVD box insert, or Steam's *Manage → CD Keys*), so
  the ownership check stays in place. TDU2 has been off sale on Steam since April 2018. DRM and
  activation workarounds are out of scope for this KB.

## Route and why

Passthrough to the community server — no game files need modifying for the online part. The PC client
is redirected by name resolution: the launcher appends Windows `hosts` entries that point the game's
original server names (`testdriveunlimited2.com` and `pc-proxy1` … `pc-proxy8.testdriveunlimited2.com`)
at the PP2 server (`Utils.UpdateConnection` in the launcher's MIT-licensed source; the launcher's "Set
Connection" button re-applies them). The PS3 version gets the same redirect from a DNS server setting.
The launcher's file check separately downloads updated game files; which ones isn't documented.

The value of this note is the failure-mode map: which symptom is a network/NAT issue, which is a GPU
driver regression, and which is a launcher/wrapper problem. Those get misattributed constantly.

## How the game works (what we had to learn)

- **Player-hosted lobbies on a full community backend.** The server does much more than matchmaking: it
  holds accounts and profiles, cloud savegames, clubs, the Community Racing Center, leaderboards and the
  DLC-token store, and it assigns you to a session with nearby players automatically. The *lobby*,
  however, is **peer-to-peer and player-hosted** — actual gameplay data (positions, cars, movement) is
  exchanged **directly between peers**, and at least one player in a session must accept incoming
  connections. There is no relay/NAT server; the game uses its original networking stack.
- **NAT types** shown in the launcher: **Green = Open:FullCone** (fully open, can host), **Orange =
  RestrictedCone / Moderate**, **Red = Strict:Symmetric / UdpBlocked**. Red or Orange can still play
  online but **cannot host sessions** — you depend on someone else hosting to see other players in
  freeroam. Only *FullCone* counts as fully open; *Open:Symmetric* is not green.
- **Proximity-based multiplayer.** You are placed into a session/lobby with nearby players
  automatically; not seeing others is normal depending on activity.
- **Lobby capacities:** Freeroam 8, Houses 10, Casino hall 26, Casino slots 32.
- **DLC items** via the in-game store: press "buy", OK, confirm the Atari token amount (you always have
  enough); a password prompt can be skipped with OK.
- **Launcher (v3.1.2):** *Profiles* let you keep multiple configs (e.g. vanilla vs modded), each
  pointing at a `TestDrive2.exe` with per-profile toggles — Magic Ram, Magic Cores, Magic Prio,
  Vehicle Dirt, Vehicle Damage, Online Mode. *Service* logs in with your in-game account and can upload
  the savegame to PP2 cloud and/or keep local backups (recommended 3–4 savepoints). *Information*
  shows hardware and copies a system report to the clipboard for support.
- **The original networking is Atari-era.** TDU2 shipped on Xbox 360 and PC; the PC version's online
  play ran on Atari's own servers. It never used the original Xbox Live service (closed April 2010).

## Build steps

### Make NAT fully open (host lobbies)

1. Open your router's admin page (its IP is in network settings).
2. Log in, and **make sure the connection is IPv4** — an IPv6 address can mask the IPv4 one.
3. **Enable UPnP** (lets the game auto-forward), apply, restart router and PC.
4. Check the NAT type **in the launcher** — you may need to reopen it once or twice to refresh.
5. If still not Fully Open: forward **UDP 8889** manually and **disable UPnP** while doing so —
   having both UPnP and a manual rule for the same port causes issues. Apply, restart.

### Convert an offline profile to online

1. Check the name is free: `https://login.project-paradise2.de/ismynamefree` (a taken name can't be
   used online).
2. Copy your profile folder from `Documents\Eden Games\Test Drive Unlimited 2\savegame` to the desktop.
3. Delete everything under `Eden Games` (leave it empty).
4. Start the game and create a profile with the **exact same name** plus account name and password.
5. Play to level 1, then exit.
6. In `savegame`, delete the newly created profile folder — but keep `ProfileList` and `SystemDefault`.
7. Paste the offline profile folder you saved on the desktop back in.
8. Start the game: level, licences, etc. should match, now online.

(Credit: "Ellie from Steam", via the PP2 guide.)

### Unpack the game for mods

1. Finish a **packed** install and run the launcher's **"check gamefiles"** first — do **not** run
   gamefile check on an already-unpacked game, it breaks it.
2. Use the TDU2 Unpacker GUI (turboduck.net/files/file/276-tdu2-unpacker-gui/) to copy/unpack into a
   new folder.
3. Install mods by copying their folders into the matching game folder (e.g. a mod's `bnk` folder →
   `euro/bnk`), replacing files when asked.

## Verification

- Source: Project Paradise 2 Discord FAQ/pinned staff posts (2025-02 through 2026-03) and the official
  PP2 guides PDFs (2025-11-09): port forwarding, troubleshooting, offline→online, modding, launcher.
- **NOT independently verified in-game** by this agent. Treat driver-regression versions and network
  behaviour as community-reported; re-confirm against the current server/FAQ before relying on them.
- **Server scope (2026-10-13):** a Project Paradise 2 developer confirmed the server is **not
  matchmaking-only** — it runs the full backend (accounts and profiles, cloud savegames, clubs, the
  Community Racing Center, leaderboards, DLC-token store) and brokers proximity sessions; the *lobby*
  is player-hosted. An earlier version of this note said "matchmaking only". PP2's public FAQ ("Server
  functions", as of 2025-07-17) agrees: lobbies (freeroam, ranked and unranked races, houses), stats,
  CRC/ORC, weather, clubs, leaderboards, friends and casino slots/roulette are restored; casino
  join/invite, tournaments, poker and club-vs-club races are not. The launcher, not the game, uploads
  the cloud saves.
- **Hosts redirect, `steam_api.dll` rename and cheat-tool list:** read from the launcher's public
  source (`Project-Paradise-2/Gamelauncher`: `Utils.cs`, `GameProfile.cs`, `Core/AntiCheat.cs`) on
  2026-10-14; the supported copies, the CD-key prompt and the PS3 DNS setup come from PP2's install
  page and FAQ. None of it was observed on a running install.

## Gotchas

1. **See a friend on the map but not in the game.** **Symptom:** their position shows on the map, but
   you never meet in the world. **Cause:** the server knows their position (map works) but the direct
   P2P connection fails — most routers block inbound by default, and there is no relay. **Fix:** get a
   **Fully Open (FullCone) NAT** — enable UPnP, or forward **UDP 8889** (with UPnP off). At least one
   player in the session needs open inbound access; it sometimes works when another lobby member is
   open, which is why it looks intermittent.
2. **AMD GPU: rendering issues, driver timeouts, system freezes.** **Symptom:** visual corruption,
   driver timeouts, or hard freezes on an AMD card. **Cause:** **drivers released after February 2025**
   regress the game (Discord reports). **Fix:** PP2's website FAQ says AMD cards are generally
   unaffected and that AMD crashes go away when Environment Detail isn't set to the highest level, so
   try that first. Otherwise downgrade to a driver from **February 2025 or earlier**. **dgVoodoo2 and
   DXVK do not fix this** — don't burn time on wrappers for this symptom.
3. **NVIDIA GTX 1650/1660 and all RTX: map crashes/freezes.** **Symptom:** the map crashes or freezes.
   **Cause:** known NVIDIA interaction. **Fix:** apply one of the two community fixes (a dgVoodoo2
   D3D12 preset, or the alternative) — they **override each other**, so only the last installed is
   active; try which works best. With the new launcher, move `uplauncher` out of the game folder so the
   launcher starts properly. If using MSI Afterburner or another overlay, close it before launching
   with dgVoodoo2.
4. **"TDU2 has to be launched by Steam".** **Symptom:** the game refuses to start. **Cause:** Steam
   integration mismatch. **Fix:** on a Steam copy, enable **"Steam Build"** in the launcher (keeps
   achievements); on a non-Steam copy, answer No to the launcher's Steam-build question, which renames
   `steam_api.dll` in the game folder to `steam_api.dll.backup` (or rename it yourself).
5. **New steering wheel not recognised.** **Symptom:** wheel does nothing. **Cause:** not
   auto-detected. **Fix:** configure the control mapping manually.
6. **Tabbing out crashes the game.** **Symptom:** alt-tab out and back → crash/freeze. **Cause:** older
   game, fullscreen handling. **Fix:** use **ALT+Enter** to toggle fullscreen; be aware of the crash.
7. **Refresh rate above 60 Hz not applying.** **Symptom:** high-refresh monitor stays at 60 Hz.
   **Cause:** >60 Hz only works in **fullscreen**, and only if the monitor supports the mode. **Fix:**
   use fullscreen and check the monitor's supported modes.
8. **Don't combine multiple car packs.** **Symptom:** broken/conflicting cars after adding packs.
   **Cause:** packs replace the same files. **Fix:** pick one car pack; also finish story mode first,
   since modded cars can make races unbeatable.
9. **Gamefile check on an unpacked install breaks it.** **Symptom:** game broken after "check
   gamefiles". **Cause:** the check expects a packed install. **Fix:** only check gamefiles on a packed
   install.
10. **Mod policy (community rules).** Mods allowed if they: don't harm other players, aren't used
    competitively (leaderboards, CRC, ORC), and don't cause server issues or crashes for others. Money
    cheating is at your own risk (no support); cheating is prohibited in competitive races. The C.T.R
    physics mod is explicitly "do not use in multiplayer races".
11. **The game closes as soon as a debugger or automation tool is open.** **Symptom:** TDU2 started
    from the PP2 launcher exits by itself, and the launcher's log shows a cheat-detection message.
    **Cause:** the launcher polls the process list and kills the game when a process name matches its
    list of cheat and reverse-engineering tools (Cheat Engine, x64dbg, IDA, Ghidra, dnSpy, AutoHotkey,
    injectors, generic names like `loader` and `hook`, and more). It also retitles the game window
    `Project Paradise 2 - Secured Session [<random id>]`. **Fix:** close those tools before an online
    session, and do RE work on an offline install that isn't started through the launcher. Find the
    game window by PID, not by title.

## Open questions

- Current Project Paradise server version and whether the AMD post-Feb-2025 regression still applies on
  the latest drivers.
- Whether the Linux dgVoodoo2 route and the Windows AMD driver regression interact (the regression is
  a Windows driver issue; Linux uses Mesa/amdgpu).
- Exact port ranges beyond UDP 8889 the P2P stack uses, for a minimal port-forward rule.

## Seen in

- Project Paradise 2 community server (project-paradise2.de) — TDU2 online revival, 2025–2026.
- TurboDuck TDU2 modding wiki; `djey47/tdumt2` tooling.
- Complements `running-tdu2-on-modern-linux.md` (compatibility) and
  `tdu2-savegame-and-gauge-formats.md` (file formats).
