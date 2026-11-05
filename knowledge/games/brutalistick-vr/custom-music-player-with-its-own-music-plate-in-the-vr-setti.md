---
kind: game
title: Custom music player with its own Music plate in the VR settings menu
game: Brutalistick VR
games_also: []
game_version: 'Steam app 2669380, Unity 6000.0.59f2 (IL2CPP x64), MelonLoader 0.7.3 Open-Beta / .NET 6'
platform: windows
engine: unity-il2cpp
route: loader-api
tools:
- MelonLoader 0.7.3 Open-Beta
- Il2CppDumper (dump.cs)
- dotnet 6 SDK (net6.0 class library)
- ffmpeg (generated test tones)
- Thunderstore CLI-less flow: upload the zip by hand
anti_cheat: none; single-player VR sandbox, nothing to bypass
status: released
agents:
- OpenCode (DeepSeek V4.1 Flash)
humans: []
date: '2026-11-05'
links:
- https://github.com/Skibidi41Rizz/CustomMusic
- https://thunderstore.io/c/brutalistick-vr/p/SkIbidiRizTEAM/CustomMusic/
tags: [audio, music, mci, winmm, harmony, ui, settings-menu, melonloader, il2cpp, vr, thunderstore]
---
# Custom music player with its own Music plate in the VR settings menu

> A MelonLoader DLL that replaces the game's soundtrack with the player's own MP3/WAV/OGG files and adds a
> **Music** plate to the VR settings menu: play/pause, prev/next, shuffle, loop modes, volume, and a paged
> playlist. Built as a managed Harmony mod (route `loader-api`) because the IL2CPP build has no way to
> construct an `AudioClip`; playback goes through Windows MCI instead. Verified in the real game — MelonLoader
> logs show `MCI open ... type=waveaudio` with the position advancing — and live on Thunderstore as
> `SkIbidiRizTEAM-CustomMusic` (1.0.7 live, 1.0.8 the cleaned-up build described here).

## Setup

- Game: BRUTALISTICK VR, Steam app **2669380**, Unity **6000.0.59f2**, IL2CPP x64, no anti-cheat.
- Loader: **MelonLoader 0.7.3 Open-Beta**, .NET 6 runtime. The game folder gets `version.dll`
  (MelonLoader.Bootstrap) plus `MelonLoader\`, `Mods\`, `UserLibs\`, `UserData\`.
- Reference assemblies: `MelonLoader\net6\{MelonLoader,0Harmony,Il2CppInterop.Runtime}.dll` and
  `MelonLoader\Il2CppAssemblies\{Assembly-CSharp,Il2Cppmscorlib,Il2CppSystem,UnityEngine.*}.dll`. All are
  referenced with `Private=false` — none of them ship with the mod.
- Build: `dotnet build -c Release` with `GameDir` as an MSBuild property, output `net6.0` DLL.
- Symbols/doc: `dump.cs` from Il2CppDumper; the music and menu classes are readable there.
- Install layouts that matter: a manual install loads `Mods\<anything>.dll`; Thunderstore Mod Manager (TMM)
  loads `Mods\<Team>-<Package>\CustomMusic.dll` and roots `UserData` at
  `%APPDATA%\Thunderstore Mod Manager\DataFolder\BrutalistickVr\profiles\<profile>\UserData`.

## Route and why

- **loader-api + managed Harmony patches** (chosen): everything needed is reachable from managed code —
  `MusicManager.StartMusic` to silence the stock soundtrack, `MenuUIManager.ChangeActiveTab` and
  `Button.OnPointerClick` to host and drive a settings plate. No native hook, no asset bundle.
- **Asset bundle for the UI** (rejected): needs a Unity project matching 6000.0.59f2 plus the game's shader
  variants; cloning the game's own settings panel at runtime needs neither (see the technique note
  `techniques/an-in-game-settings-menu-in-an-il2cpp-unity-game-clone-the-g.md`).
- **Unity audio** (rejected after testing): the shipped IL2CPP build has every `AudioClip` creation method
  stripped — `Create`, `Construct_Internal`, `CreateUserSound` all fail, so PCM cannot become a clip. This is
  why earlier versions "worked" in the log and played nothing.
- **MCI (`winmm.dll`)** (chosen for playback): Windows plays the file itself, it survives scene loads and
  needs no game audio objects. Trade-off: volume handling is device-dependent and there is a disk cache.

## How the game works (what we had to learn)

**Music.** `MusicManager` (singleton, `currentMusicManager`) holds `mainMenuClip`, a `musicClips[]` playlist,
`introClip`, `loopClip` and a mixer group. It starts music from a `SceneManager.sceneLoaded` handler, not from
`Awake`/`Start`, so **disabling the component does not stop it** — the handler still calls the start method.
The method to intercept is `MusicManager.StartMusic(bool isMainMenu)`:

```csharp
static bool StartMusicPrefix(bool __0)          // Harmony prefix on MusicManager.StartMusic
{
    if (!Enabled || !ReplaceStock) return true;  // let the game do its thing
    if (TrackLibrary.Files.Count == 0) return true; // no user tracks -> keep vanilla music
    return false;                                 // skip the original: stock music never starts
}
```

The "no user tracks → allow stock" line is what keeps the mod from leaving a silent game.

**Audio.** MP3 and OGG are decoded in managed code (NLayer 1.16.0 and NVorbis 0.10.5, embedded as DLL
resources and loaded through `AppDomain.AssemblyResolve`) into a 16-bit PCM WAV under
`UserData\CustomMusicCache\<sha1 of path+size>.wav`; plain WAV files play directly. The MCI device:

- `open "<path>" type mpegvideo alias cm_track` — DirectShow, also accepts `setaudio ... volume to 0..1000`;
- `open "<path>" type waveaudio alias cm_track` — for cached WAVs; volume falls back to `waveOutSetVolume`;
- `play`, `pause`, `resume`, `stop`, `seek ... to start`, `status ... mode|position|length`;
- commands are synchronous and must run on the main thread; poll `mode`/`position` at most ~5 Hz.

**Settings UI.** `MenuUIManager` exposes `settingsTabs[]` (panels), `settingsTabButtons[]` (tab buttons),
`ChangeActiveTab(int)`, and the open panels `settingsTab`, `mainOptionsTab`, `cheatsTab`. Panels and tab
buttons are ordinary prefab clones, labels are `TextMeshProUGUI`, and every click passes through
`Button.OnPointerClick(PointerEventData)`. Adding a plate = clone `settingsTabs[0]` and
`settingsTabButtons[0]`, append both to the arrays, postfix `ChangeActiveTab` to hide/show, and dispatch
clicks by `Button.GetInstanceID()`. Full recipe with code in the technique note above.

**Config.** `MelonPreferences` writes `UserData\MelonPreferences.cfg`, section `[CustomMusic]`. A `Schema`
entry lets a new default reach old configs; note that it does **not** overwrite the user's other values.

**Where user files live.** `MelonEnvironment.UserDataDirectory` follows whatever launched MelonLoader: with
TMM it is the profile folder, with a manual launch it is the game folder. `Application.dataPath` always
points at the *game* install, so it must not be used to find user files.

## Build steps

1. Create a `net6.0` class library named `CustomMusic`; reference MelonLoader, 0Harmony,
   Il2CppInterop.Runtime and the Il2Cpp assemblies by path, all `Private=false`.
2. `MelonInfo(typeof(CustomMusicMod), "CustomMusic", "1.0.8", "author")`, `MelonGame("Kubunautilus",
   "BrutalistickVR")`, `MelonPriority(-100)` so the stock-music patch runs before other mods.
3. Embed the two decoder DLLs and the cassette SFX as resources; resolve them in `AssemblyResolve` from
   `CustomMusic.libs.<name>.dll` only — no lookup in `UserLibs`/`Mods` (see Gotcha 5).
4. Root = `Path.Combine(MelonEnvironment.UserDataDirectory, "CustomMusic")`. Create it, write a `README.txt`
   with the path, scan it **recursively** for `*.mp3|*.ogg|*.wav`, skip `sfx\` and `CustomMusicCache`, and
   sort by file name with numeric comparison (`2` before `10`).
5. Patch `StartMusic` (prefix), `ChangeActiveTab` (postfix) and `Button.OnPointerClick` (postfix).
6. Player: prepare the track in a `Task` from a coroutine (`TrackLibrary.Prepare`) so VR does not hitch,
   open it in MCI, fade with `setaudio`/`waveOutSetVolume`, poll `mode`/`position` for the panel.
7. Skip unreadable files once: keep a `HashSet<string> bad` and log one line per file, never retry.
8. Package for Thunderstore: **flat** zip — `CustomMusic.dll`, `manifest.json`, `icon.png` (256×256),
   `README.md`, `CHANGELOG.md` — with the version in `MelonInfo` equal to `version_number`, and no audio files.
9. Verify, then upload to the existing package name; a new package name for the same mod is a spam violation.

## Verification

- **Oracle: MelonLoader log plus ears.** `MelonLoader\Latest.log` shows `CustomMusic v1.0.8`, the folder it
  uses, the scanned track list in order, `patched MusicManager.StartMusic / MenuUIManager.ChangeActiveTab /
  Button.OnPointerClick`, then `MCI open '<file>' type=waveaudio length=...ms` and
  `mci mode=playing pos=...`. The author confirmed sound by ear in the menu.
- **Ordering** was checked with three generated tones named `1 - one.wav`, `2 - two.wav`, `10 - ten.wav`:
  the log lists `1, 2, 10`, and playback advances in that order with `Loop = All`, `Shuffle = off`.
- **Both install layouts**: manual (`Mods\CustomMusic.dll`, music under the game folder) and TMM
  (`Mods\SkIbidiRizTEAM-CustomMusic\CustomMusic.dll`, music under the profile) were run; the second is
  proven by a profile log containing `Melon Assembly loaded: '.\Mods\SkIbidiRizTEAM-CustomMusic\CustomMusic.dll'`.
- **Path handling**: a standalone P/Invoke harness opened and played a 167-character path with spaces and
  Unicode directories through MCI (`mode=playing`), so deep TMM profile paths are not a problem; 8.3 short
  names are used when available but are not required.
- **Not verified**: OGG on a Windows install without the Vorbis codec (the decode path is ours, so it should
  be independent, but it was only run on one machine), `setaudio volume` on the `mpegvideo` device on other
  systems, and behaviour when the same track is played from two mod profiles at once.

## Gotchas

1. **Thunderstore rejected the package five times as "Invalid submission".** **Cause:** the early zips
   contained commercial soundtrack files (copyright rule), used a nested `Mods\`/`UserData\` layout, and the
   DLL unpacked decoder DLLs into `UserLibs\` at first launch (non-destructive-install rule); one version also
   did not play audio at all while the README promised it. **Fix:** flat zip with one DLL, no audio, no writes
   outside `UserData\CustomMusic*`, README that matches the build, AI disclosure in README and
   `AssemblyMetadata`. Re-uploading an accepted mod under a second package name was flagged as an exact
   reupload — bump the version inside the same package instead.
2. **Music "works" in the log but nothing plays.** **Cause:** `AudioClip` creation is stripped in this build;
   the clip came back null. **Fix:** do not use Unity audio at all — play the file through MCI.
3. **Disabling `MusicManager` did not stop the menu music.** **Cause:** music is started from a
   `sceneLoaded` handler that re-invokes `StartMusic` regardless of the component state. **Fix:** Harmony
   prefix on `StartMusic`, gated on the mod having tracks.
4. **The game goes silent when the user's music folder is empty.** **Cause:** unconditional prefix that
   always skipped the original. **Fix:** return `true` (run the original) when the playlist is empty.
5. **Two different track lists appear depending on how the game was launched.** **Cause:** the scan collected
   *both* `MelonEnvironment.UserDataDirectory\CustomMusic` and `<GameDir>\UserData\CustomMusic`, so a TMM
   profile and the game folder were merged, and the mod also wrote `sfx\` into the game folder while running
   from a profile. **Fix:** one root only — `UserData` of the running loader — and never touch the other.
6. **The playlist looked shuffled even with an alphabetical library.** **Cause:** `Shuffle` defaulted to
   `true` and the config also had `Loop = 1` (repeat one), so consecutive numbers never matched; sorting also
   used the full path, not the file name. **Fix:** natural sort by file name (`2` before `10`), `Shuffle`
   default `false`, document `Loop All` for sequential playback, and let the Shuffle button opt in.
7. **The decoded WAVs show up as tracks.** **Cause:** the cache lives under `UserData` next to the music
   folder. **Fix:** skip any path containing `CustomMusicCache` in the scan.
8. **A 14 MB MP3 becomes a 100 MB file.** **Cause:** the cache is 16-bit PCM WAV (~10× the compressed size);
   seven tracks came to several hundred MB. **Fix:** document it, keep the cache out of the package, and let
   users delete `UserData\CustomMusicCache` at any time.
9. **One broken file floods the log and blocks playback.** **Cause:** the player retried the failing track
   after every scene load. **Fix:** remember bad paths, skip them in every pick, log one line per file.
10. **Legacy `Input.GetKeyDown` hotkeys spam warnings.** **Cause:** the project is Input-System-only; the old
    `Input` class throws per call. **Fix:** drop keyboard hotkeys and drive everything from the VR plate.
11. **The page shows `v1.0.6` while the manifest says `1.0.7`.** **Cause:** `MelonInfo` was not bumped with
    the manifest, so the log and the Thunderstore page disagree. **Fix:** bump both together; reviewers read
    the log line.
12. **Debug artefacts in user folders.** **Cause:** an early UI probe wrote `ui-dump.txt` into the music
    folder. **Fix:** dump to the loader log, and check the built DLL's strings for such names before shipping.

## Assets

- Cassette click SFX (`tape_insert.wav`, `tape_eject.wav`) synthesized as WAV and embedded as resources; they
  are UI feedback for the play/pause animations, not music.
- Icon: 256×256 PNG in the package root, as Thunderstore requires.
- **No music is bundled.** The zip contains zero audio entries — that is exactly what the copyright rule
  requires, and the mod reads only files the user puts in `UserData\CustomMusic`.

## Cost and time

Multiple sessions across two days: recon of the music system, a dead end on Unity audio, the MCI rewrite, the
settings plate, then the Thunderstore review loop (five rejections) and the 1.0.8 cleanup.

## Open questions

- Volume on the `mpegvideo` path is device-dependent; a per-device fade would need a WASAPI/DirectSound route.
- The cache is never pruned automatically; a size cap or "clear cache" button on the plate is the next step.
- Showing the actual music-folder path inside the plate would remove the most common support question
  ("where do I put the songs?"), which currently lives in the log and a `README.txt` in the folder.
- The plate works, but its layout is positioned by hand from the template's `RectTransform`; a proper
  grid-layout group on the clone would survive game updates that change button sizes.
