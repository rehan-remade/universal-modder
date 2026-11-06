# Shadow of War Offline Mode + Local Garrison (v0.12)

Keeps Middle-earth: Shadow of War off WB's online servers, while the **Garrison keeps working locally**: store, list, Details, **Deploy** and **Destroy for gear**.

- **Nothing is sent to WB.** Every WinHTTP request to the WB/Agora domains in `BlockedDomains` is answered inside the game process by a small local stand-in for WB's server. That covers sign-in, telemetry and the Market backend. Steam traffic is untouched.
- **Online play is off.** Online Conquests and Vendettas can't connect.
- **The Garrison is stored locally.** Each orc you send there is saved as a file in `x64\OfflineGarrison\`. Deploying an orc to an empty captain slot works, and so does destroying one for gear. The gear is rolled by the game itself from the orc's equipment.
- **Mirian is kept.** Since the 2018 Market shutdown the game moves your Mirian into an online wallet. That wallet is now `x64\OfflineWallet.txt`, and it mirrors the Mirian in your save.
- **Nothing is unlocked or granted.** The store only gets inert placeholders. No Gold, chests, boosts or products can be bought or received.
- **It isn't a server.** It runs inside the game process and opens no port, so nothing else can connect to it. Online Conquest, Online/Friend Vendettas and Market purchases aren't emulated.
- **The game is untouched.** No game files are changed, and the exe and its DRM aren't modified. The mod is one `winhttp.dll` next to the exe.
  Since v0.12 it also writes one field in the game's memory (the Nemesis id prefix), so captains get ids that stay unique across sessions. `NpcGuidPrefix=0` turns that off.

Tested on Steam build 3095001 (Windows 10 22H2).

## For modders and AI agents: install this first
**Install and run this mod before testing or making any other Shadow of War mod.**
- Shadow of War still has online modes: Online Conquest, Online/Friend Vendettas and the WB Garrison backend.
- A modded game that is signed in to WB could send modded orcs, tribes or gear to other players or to WB's servers.
- That is online testing. The universal-modder rules say to stay offline or on servers you control.
- With this mod running, every WB/Agora request stays on your PC. So you can test Nemesis, tribe, gear and Garrison mods safely, and still use the Garrison to store and move test captains.

Before each test session, check that `x64\OfflineMode.log` starts with `Shadow of War Offline Mode, mode=emulate`.

## Requirements
- Shadow of War on Steam, build 3095001 (other builds are untested).
- **No mod loader is needed.** The mod doesn't use or need **Packet Loader** or the **Dll Loader**. Windows loads `winhttp.dll` from the game folder by itself.
  - The Dll Loader (a `bink2w64.dll` proxy) can stay installed alongside it; that setup was tested.
  - Packet Loader G2 v3.1 crashed at startup about half the time on this build, so it was disabled for all tests. The mod doesn't depend on it either way.
- Any MinGW-w64 GCC to build it. w64devkit was used.

## Build
This folder is source only. Run `build.cmd` (MinGW-w64 GCC; set `GCC=` to its `gcc.exe` if it isn't on PATH) to produce `winhttp.dll`.

## Install
1. Build `winhttp.dll` (above), then close the game.
2. Run `install.ps1`: right-click it, then choose **Run with PowerShell**. If the game isn't at the default path, pass `-Game "<install folder>"`. To install by hand instead, copy `winhttp.dll` into `<Shadow of War>\x64\`, and copy `OfflineMode.ini.txt` there as `OfflineMode.ini`.
3. Start the game. WB Play should show a white dot, and the Garrison should open.

## Uninstall
Run `uninstall.ps1`, or delete `x64\winhttp.dll` and `x64\OfflineMode.ini`.

Keep `OfflineGarrison\` and `OfflineWallet.txt` if you might reinstall. They hold your Garrison and wallet.

## Settings (`x64\OfflineMode.ini`)
| Key | Default | Meaning |
|---|---|---|
| `Mode` | `emulate` | `emulate` answers WB requests locally, which the Garrison needs. `block` just fails them, as if WB were down. |
| `StorePlaceholders` | `1` | One inert item and product, so the store (and the Garrison inside it) counts as open. `0` locks the Garrison. |
| `GarrisonSize` | `50` | Garrison capacity sent to the game. |
| `BlockedDomains` | WB/Agora domains | Hosts handled locally, including subdomains. |
| `Log` | `1` | Writes `x64\OfflineMode.log`. Sign-in data and tokens are redacted. |
| `NpcGuidPrefix` | `1` | Gives new captains Nemesis ids that are unique across offline sessions, which the Garrison needs. `0` turns it off. |

## Your data
- `x64\OfflineGarrison\<id>.agb`: one file per Garrison orc (gear, appearance, traits). Back up this folder to back up your Garrison.
- `x64\OfflineWallet.txt`: `slug=count` lines. `vc-earned` is the Mirian moved online. It changes only through the game's own requests. Don't add slugs by hand: War Chests, boosts and other online inventory items were sold for Gold or are earned online, and this mod doesn't grant them.
- If an orc is ever lost, `tools\log_to_object.py` can rebuild it from the request logged in `OfflineMode.log` when it was sent to the Garrison.

## Known issues
- Clicking **WB Play** still opens a sign-in or registration screen. Ignore it.
- A Steam "Verify integrity" doesn't remove `winhttp.dll`, but check that it's still there after a game update.

## Changes
- **v0.12 (2026-10-20):** unique Nemesis ids offline (fixes "You cannot send this Follower to the Garrison").
  - Offline the game's id prefix for new captains stays empty and its counter restarts every launch, so captains made in
    different sessions get the same `_NPC_<n>` id, and the Garrison refuses a captain whose id another one has.
  - The DLL now writes a random 32-hex prefix into the game's analytics manager, the same place the online session
    GUID goes, after the game's first network request (and only if the field is still empty). New captains get
    `<prefix>_NPC_<n>`. Existing duplicates stay until the save's ids are rewritten.
  - `NpcGuidPrefix=0` in `OfflineMode.ini` turns it off.
  - v0.11 wrote the prefix as soon as the manager pointer existed, before the game's first request; in one session
    the game then made no online requests at all and the Garrison showed a red lock. v0.12 waits.
- **v0.10 (2026-10-12):** Deploy and Destroy for gear work.
  - After removing an orc, the game waits for a `garrison_removal` notification from the server before it places the captain or rolls the gear.
  - The local stand-in now sends that notification and accepts the game's dismissal.
  - Before this, both actions failed after the orc had already been deleted.
- **v0.9 (2026-10-10):** offline sign-in, the store, the local Garrison (store, list, Details) and the local wallet.

## Credits
- **Mod, research and code:** DeimozZarco, with Claude Code (Anthropic, Opus 5.5) as the coding and reverse-engineering agent.
- **Ghidra** (NSA, Apache 2.0) for static analysis, with **Eclipse Temurin JDK 21**.
- **w64devkit** (Christopher Wellons, public domain), whose GCC builds the DLL.
- **QuickBMS** and the `shadow_of_mordor.bms` script by **Luigi Auriemma (aluigi)**, for reading the game archives during research.
- **Shadow of War DLL Loader** (Nexus mod 99) and **Shadow of War Packet Loader** (Nexus mod 49), both by **survivalizeed**. They were on the test PC, but this mod **doesn't use or need** either one.
- **universal-modder** (rehan-remade), the modding toolkit and knowledge base this was built with.

## How it works
Read `src\` (start with `responder.c`) and `knowledge/games/middle-earth-shadow-of-war/offline-mode-and-local-garrison.md`.
- The game talks to WB through the Hydra SDK (`Hydra-Cpp/1.50.1`), over WinHTTP, in a binary format (`application/x-ag-binary`).
- `winhttp.dll` forwards all 70 WinHTTP exports to the system DLL and answers only the blocked hosts itself.
- `src\agb.c` encodes and decodes the binary format.
- `src\responder.c` is the local server.
