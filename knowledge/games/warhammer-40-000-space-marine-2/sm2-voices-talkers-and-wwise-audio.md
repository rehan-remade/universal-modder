---
kind: game
title: "Space Marine 2 voices: custom talkers, mission voice routes, media bundles, Wwise bank edits and grunt matching"
game: "Warhammer 40,000: Space Marine 2"
games_also: []
game_version: "Steam build 25799387 (Patch 15.1, Oct 2026); earlier findings on Patch 14.x (Sep-Oct 2026). Wwise 2019.2 for encoding"
platform: windows
engine: unknown
route: data
tools: ["Wwise 2019.2 (WwiseConsole, conversion matching the game's mono voice preset)", "wwiser (bank dumps)", "ww2ogg + revorb (extraction)", "ffmpeg", "Python 3 (struct, numpy; own bank and bundle writers)", "AI text-to-speech (ElevenLabs) for new lines"]
anti_cheat: "EasyAntiCheat. Everything here uses Saber's official mods folder (client_pc/root/mods), which flags the session 'Mods Detected' (private lobbies, separate progression). No injection, no EAC interaction, PvE only."
status: working
agents: ["Claude Code (Opus 5.5)"]
humans: []
date: 2026-10-15
links: []
tags: [space-marine-2, saber, voice, vo, talker, wwise, bnk, wem, media-bundle, subtitles, grunts, audio, chatter]
---

# Space Marine 2 voices: custom talkers, mission voice routes, media bundles, Wwise bank edits and grunt matching

> How we added complete new player voices to Space Marine 2 (selectable in the armoury voice list, ~1,800 lines each:
> combat chatter, ability calls, social wheel, emote chant, mission dialogue, plus grunts), made one of them a modded
> class's default voice, cloned an ability's shout as new Wwise events, and played an intro line from a mission
> script. This note covers the mechanics only: talkers, routing, bundles, banks, loudness and the in-game helmet
> radio effect. Builds on [the foundations note](sm2-modding-foundations-paks-tools-and-crash-triage.md); the class
> side of a default voice is in [the class note](sm2-new-playable-class-on-character-mod-slot.md). Verified in game
> unless marked otherwise.

## Setup
- Steam build 25799387 (Patch 15.1). Voice media: `sounds/desktop/*.zip` + `.header` bundles; banks (`.bnk`) in the
  sound paks (`default_sound*.pak`); manifests (`.sound_media_bundle.resource`, `.sound_event.resource`,
  `english.sound_localization.resource`) in `resources.pak`; subtitles in `texts/strings_english.str` (UTF-16LE).
- Wwise 2019.2 (WwiseConsole) to encode `.wem`, with a mono Vorbis conversion setting; the game's banks come from the
  2019 generation, so we stayed on it.
- wwiser to dump a bank's object tree; ww2ogg + revorb to extract retail lines for reference (never as a sample to
  clone a voice from).

## Route and why
Data route. A voice is a talker (text data) whose events resolve to media in a bundle listed in the localization
manifest; mission dialogue picks talkers through scenario graphs. Everything can be added without code. The one thing
that cannot be added is a new compiled class: a voice integration that shipped its own blueprint node class (own
sslbin + `.ssc.resource` + brand `.sso`) crashed at boot (reading 0x48, an object of an unregistered class).

## How the game works (what we had to learn)

### Talkers: base vs custom
- Every speaking character has a talker id: the class voices (e.g. `soldier` for Tactical), companions, DLC voice
  packs (`vp_wolf`, `vp_salam`, `vp_templar`, `vp_blangel`) and any new id you add. A talker's sound descs point at
  Wwise events named like `vo_ext_talker_chatter_<talker>` / `vo_ext_talker_story_<talker>`; a new talker can simply
  point at the soldier's events (that also gives it the in-game helmet effect, below).
- **BASE talker** = the class's own voice. It is server-authoritative: each class sets `talkerRef` in BOTH
  `<class>_authority.cls` (`prop_talker_marine_authority`) and `<class>_server.cls` (`prop_talker_marine_server`), and the
  server syncs it to clients. Setting only the authority file left the social wheel on the old voice. Base talkers
  drive chatter, ability calls, the social wheel and subtitles.
- **CUSTOM talker** = the voice picked in the armoury voice list (applied with net sync). Retail's
  `BlueprintNodeSetTalker` sets the BASE talker locally, which breaks mission speaker selection - don't use it to
  "force" a voice. There is no data field for a per-class default custom talker; a class default is done through the
  base `talkerRef`.
- **The voice list** shows `customizableTalkers` entries (order, name key in `customizationTalkersLocalization`, an
  optional lock). DLC packs carry a `DlcLockReason`; class voices are unlocked through an Honor Shop bundle
  (`RewardObjectTalker`, locks are per item). An entry with no lock is selectable by everyone. The unnamed "..." entry
  is the class's built-in default and plays the class's base voice.

### Mission dialogue routing
- Mission lines are chosen in scenario graphs (13+ scenario files and two shared library graphs:
  `pass_dlg_to_random_talker_pve`, `scenario_dlg_event_pve`). Speaker selection uses BASE talkers
  (`SelectAvailablePveBaseTalker` returns one of the 7 class voices), then `BlueprintNodeSwitchPveBaseTalker` branches
  per class. That switch has no default output: an unknown talker means the line is silently dropped.
- To give a custom voice its own mission lines, put a check "custom talker == <id>" in front of each route and play
  that voice's line, falling back to the base route. Several custom voices are CHAINED (each check after the previous
  voice's), so custom voices win and base voices remain the fallback. One full voice meant ~6,000 route edits across
  14 files; generate them with a script that asserts nothing is integrated twice. The horde/siege level has its own
  dialogue groups.
- To make a new talker a class's BASE voice: `talkerRef` in both class files, plus a "talker == <id> -> that class's
  outputs" mapping in front of every `SwitchPveBaseTalker` (inline and in the two library graphs).

### Media bundles and the localization list
- `sounds/localization/english.sound_localization.resource` lists every media bundle the game loads
  (`- res://sounds/media_bundles/<name>.sound_media_bundle.resource`). It is ONE shared file: the first-sorting pak's
  copy wins, so every mod that ships one must list every other mod's bundles too, or those voices go silent. A listed
  bundle whose resource is not shipped crashes at the title screen (the resource loader walks the links and reads
  null, 0x20).
- A bundle = `sounds/desktop/<name>.zip` (the `.wem` files) + `<name>.header` (u32 count, then per entry: u32 name
  length, name, u64 data offset, u64 size, in zip order) + `.sound_media_bundle.resource`. Entries are named after the
  line ids: chatter `vo_chatter_<talker>_<event>_NN`, mission/story lines with their own prefixes. Story/cinematic
  lines of the base game sit in `external_sources_vorbis_english` bundles (e.g. prologue lines
  `vo_story_intro_<speaker>_NNN`; the prologue's squad leader speaks as `kill_team_leader`, not under the hero's id).
- An event without a line of its own can reuse another entry (an alias: e.g. a battle-cry ability call reusing a
  generic line).
- Subtitles: one key per line in `texts/strings_english.str` (format in the foundations note). Social wheel labels
  are `UI_SOCIAL_COMMAND_*` keys.
- Encoding that worked: mono `.wem` from Wwise 2019.2 with the game's mono voice conversion, normalised to about
  -27 LUFS integrated.
- Mission scripts can play an external line directly: `BlueprintNodePlayStoryVoiceover` with `useExternal True`, the
  line name as `eventNameRef` (`ExternalSoundRefParam`) and a `talkerUidRef` (a retail operation does this for its
  narrator). Needs the bundle, its localization entry and the subtitle key.

### VO categories and triggers
- Chatter category `human_battle_chatter` is SKIP-type with a ~5 s per-actor cooldown: lines get dropped by design.
  `BlueprintNodePlayStoryVoiceoverPackage` refuses to play while its speaker is still set, which is only cleared when
  a line ENDS - a skipped line blocks that node forever. What worked: `StopVoiceOver` before each play, and the unused
  retail category `esd_no_subs` (REPLACE, no cooldown, priority 150).
- VO triggers for the Marine live in `ssl/sounds/voiceover/prop_voiceover_marine_client.prop` (e.g. the "Reloading!"
  call, ability triggers); an `ownerCondition` can suppress a trigger. A cloned ability needs its VO trigger cloned too.
- Emote shouts are NOT voice lines: they are Morpheme duration events on the emote clip that play character-bank
  sounds through the Marine's sound blueprint. Mute one for a specific ability with a `BlueprintNodeGate` opened/closed
  by `BlueprintNodeSubscribeOnAbility` `OnActivated` / `OnDeactivated`.

### Wwise banks: adding and replacing sounds
- A sound event is a resource: `sounds/events/<name>.sound_event.resource` (banks, 3D flag, priority, durations, and
  `startAudioIDs` = the Sound object ids); a blueprint or class loads it through `linksSound` in its `.resource`.
- **New event in an existing bank (verified in game):** add a HIRC Sound object, a Play action and an Event whose id
  is the 32-bit FNV-1 hash of the lowercase event name; add the media to DIDX/DATA (entries 16-byte aligned, sorted by
  id); add the Sound to its parent actor-mixer's child list; write the `.sound_event.resource`. A writer that
  round-trips retail banks byte-exactly is the safety net.
- **Replacing media in place** keeps every id: swap the media and patch the Sound objects' in-memory media size. The
  scope is every event that uses that media - swapping a shared shout changed another character's shout as well.
  Weapon-exclusive media (one gun family) is a safe target; shared media is not.
- Media sizes and loudness: judge against retail in the SAME in-game recording chain; offline targets taken from a
  single 2D layer mislead, because retail spreads a sound over several 2D/3D layers.

### The helmet radio effect is applied at runtime
- Every player voice event (`vo_ext_talker_chatter_<talker>`, `vo_ext_talker_story_<talker>`) plays through a
  Parametric EQ (low shelf about +3.5 dB at ~730 Hz, a peaking band that is switched off, low-pass ~9.7 kHz), a Matrix
  Reverb, an aux send to a radio-processing bus and volume/obstruction/occlusion RTPCs. Class and DLC voice chains are
  identical. Cinematics have their own helmet events.
- **Never bake a helmet/radio effect into new lines or grunts**: a custom talker pointing at the soldier events gets
  the chain live, so a baked effect is applied twice. For previews, approximate it (EQ + low-pass + short room reverb).

### Grunts (effort sounds) for a new voice
- Grunts are ~21 chatter events (melee effort, hits, charges ...) inside the voice's bundle. Building them from a
  retail class voice's grunts (pitch-shifted, EQ-matched, or copied as-is) works.
- Measured: retail grunts sit ~1.3-1.7x the speaking pitch (Tactical ~174 -> 291 Hz, Bulwark ~232 -> 356 Hz); some DLC
  packs grunt unusually low or growl. YIN grunt medians (Hz): Tactical 291, Assault 314, Vanguard 267, Bulwark 356,
  Sniper 271, Heavy 154, Techmarine 213, Salamander pack 182.
- **Match the retail grunt pitch to the new voice's SHOUTED lines** (war cries, charges), not its calm speech; also match
  voice size (formants) and the long-term tone curve. Even then the number came out low by ear: render previews at
  0 / +1 / +2 semitones through the approximate helmet chain and let a human pick.

### Writing a whole voice
- The event list is the retail class chatter (strings `vo_chatter_<talker>_*`), ~1,800 rows in 17 queues once
  mission and siege lines are included. Keep one id scheme per voice (chatter `vo_chatter_<talker>_<event>_NN`, mission
  lines a short per-voice prefix) and mirror ids 1:1 between voices so routing scripts can be reused.
- The emote chant has two alternating takes (`social_emote_chant_01` / `_02`); retail ships only `_01`, so add `_02`
  (or copy `_01` into it). The social wheel is six command lines with UI labels.
- With AI TTS (private builds only: Saber's mod rules forbid AI-generated content, see the foundations note), use a
  stock or designed voice, never a clone of a real person such as one of the game's voice actors. (The voices built
  for these notes were cloned from a voice actor's original performance; that route is dropped, see Assets.) Generate
  the few lines that contain hard proper nouns first and fix their spelling for pronunciation; record two takes per
  line and pick; keep a lock on lines the human has approved so later re-voicing cannot change them (assert byte
  equality at build time).

## Build steps
1. Script -> recorded/selected lines -> loudness-normalise (~-27 LUFS) -> Wwise 2019.2 mono `.wem`.
2. Build the bundle (`.zip` + `.header` + `.sound_media_bundle.resource`), incl. aliases and grunts.
3. Add the bundle to `english.sound_localization.resource` - in EVERY mod pak that ships that file and sorts first.
4. Talker data: talker + sound descs (point at the soldier events), `customizableTalkers` entry (+ name string), no lock
   for a free selectable voice; or base `talkerRef` in authority AND server cls for a class default.
5. Mission routes: chained custom-talker checks in every dialogue route; base-talker switch mappings if it is a base
   voice. Subtitles for every line.
6. Ship ZIP_STORED; check that no earlier-sorting pak shadows the localization list or the VO prop.

## Verification
- In game: a new selectable voice (picker entry, chatter, social wheel, missions), a modded class with a new BASE
  talker (social wheel switched after the server-cls fix), new bank events for a cloned ability (shout heard), the
  title-screen crash from an unshipped bundle link and the boot crash from a new compiled node class, `StopVoiceOver` +
  `esd_no_subs` making scripted lines play every time.
- Not verified in game at writing: the two most recently added voices (built the same way, chained after the first)
  and the scripted intro line on a converted level.

## Gotchas
1. **Boot crash after installing a voice mod.** Cause: it shipped a new compiled blueprint node class. Fix: use
   retail node types only.
2. **Crash at the title screen after removing a voice pak.** Cause: the localization list still links its bundle.
   Fix: keep the list and the shipped bundles in sync.
3. **New voice silent although the bundle is in your pak.** Cause: another pak sorts first and ships its own
   localization list without your bundle. Fix: make every copy a superset.
4. **Social wheel still uses the old voice after changing the class talker.** Cause: base talker set only in the
   authority cls; the server cls syncs its own. Fix: change both.
5. **Custom voice silent in missions.** Cause: mission speaker selection uses base talkers and the base-talker switch
   drops unknown ids. Fix: per-route custom-talker checks, or map the new base talker onto a class output.
6. **Using SetTalker to force a voice broke mission dialogue.** Cause: it sets the BASE talker locally. Fix: base
   `talkerRef` in data, or the picker.
7. **Voice sounds like it went through the helmet twice.** Cause: radio EQ baked into the lines; the game adds it at
   runtime. Fix: ship dry lines.
8. **Grunts sound far too low next to the voice.** Cause: matched to speaking pitch. Fix: match shout pitch; preview
   semitone variants.
9. **Replaced a shout and another character changed too.** Cause: shared media id. Fix: new events (FNV-1 ids) or
   exclusive media only.
10. **Scripted voice line plays once, then never again.** Cause: a SKIP-category line was dropped and the speaker
    stayed set. Fix: `StopVoiceOver` first; a REPLACE category without cooldown.
11. **Vanilla "Reloading!" talks over your custom line.** Cause: the Marine VO trigger prop. Fix: an `ownerCondition`
    in that prop (and keep it merged with any other mod that ships it).

## Assets
New lines were generated with an AI TTS service from scripts written for each voice and recorded/selected by the
human. Disclosure (2026-10-15): the TTS voices used for these notes were cloned from a real voice actor's original
performance, without their consent. That route is dropped: cloning a real person's voice without consent is out,
even for private builds. The mechanics in this note are the same with a stock or designed TTS voice or with recorded
lines. Grunts were transformed retail grunts. No game
audio is attached to this note. Saber's mod rules forbid AI-generated content in mods, so keep TTS voices in private
builds; a released voice pack needs recorded lines.

## Open questions
- A data route for a per-class default CUSTOM talker (only base `talkerRef` was found).
- Whether bundles for other languages need parallel entries for a voice to work outside English.
