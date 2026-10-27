---
kind: game
title: 'Rebuilding a cut gatekeeper with generated plugin records: dialogue branches, shared voice lines, force-greets'
game: Skyrim Special Edition
games_also: []
game_version: '1.7.104 (Steam), Creation Kit 1.7.99; no SKSE needed'
platform: windows
engine: creation
route: data
tools: ["Python plugin writer (own, ~600 lines)", "Creation Kit PapyrusCompiler", "SSEEdit (read-only checks)", "LipGenerator + FonixData.cdf", "MO2 2.5.2"]
anti_cheat: 'none (single-player)'
status: working
agents:
- Claude Code (Opus 5.5)
humans: []
date: '2026-10-24'
links: []
tags: [dialogue, quests, papyrus, force-greet, shared-info, voice-files, esl, cut-content, packages, exclusive-branch, debugging, quest-priority, shouts]
---
# Rebuilding a cut gatekeeper with generated plugin records: dialogue branches, shared voice lines, force-greets

> The first segment of a College of Winterhold overhaul: Nirya takes the bridge at night (20:00–8:00) and
> Faralda by day, with Nirya's own entrance exam. She force-greets with a warning, gives a random note naming
> one of First Lessons' five test spells (it must be read first), and can be persuaded or failed, in which case
> Faralda takes over. There's also a Dragonborn route and an escort that lights the wells. All of it uses her
> vanilla and cut recordings. The plugin is written by a Python script, not the Creation Kit, and every
> behaviour below was tested in game over ~68 builds. About half of them went on one bug: after the player
> got in, Nirya never talked again (gotcha 19; read it before making any dialogue branch exclusive).

## Setup
- Skyrim SE **1.7.104** (Steam), Creation Kit **1.7.99**, its `PapyrusCompiler.exe` with
  `TESV_Papyrus_Flags.flg` and the vanilla sources in `Data\Source\Scripts`.
- SKSE isn't needed. The install had SKSE 2.2.3, a build for runtime 1.6.640, which can't load on 1.7.104
  (skse.silverlock.org lists 2.3.1 for 1.7.104).
- MO2 2.5.2 test profile: USSEP, Cut Content Restoration (incl. its optional Saarthal Miners plugin), College
  of Winterhold - Quest Expansion, Alternate Start, SkyUI. None of them touch the bridge.
- The plugin: an **ESL-flagged ESP**, master Skyrim.esm only, not localized. A Python builder clones vanilla
  records and writes groups, VMAD, conditions and voice files. Staging copies the whole build into MO2.

## Route and why
Plugin data plus Papyrus (`route: data`). Everything reuses vanilla systems: First Lessons' (MG01) own test
stages, objectives and spell checks, vanilla packages, vanilla dialogue lines. Rejected:
- **Adding objectives to MG01:** quest records don't merge, and USSEP and Quest Expansion both override MG01.
- **SKSE:** not needed. The spell list became vanilla's five test spells instead of "any Apprentice spell".

## How the game works (what we had to learn)
- **First Lessons already contains the whole entrance exam, originally built for Nirya.**
  - Stages 20–24: Magelight, Flame Atronach, Firebolt, Fear, Healing Hands. Each stage's fragment shows its
    own objective, and stage 30 completes them and opens the gate.
  - Vanilla checks set `MG01QuestScript.NiryaSpellSuccess = 1`: `MG01StoneScript` on the seal stone
    (alias 6, 00051190), `MG01AtronachTriggerScript`, and `MG01NiryaScript` on alias 1 (= Nirya) and 11
    (Faralda).
  - So a mod can run its own variant just by setting the stage and polling that variable.
- **The cut Nirya content still in MG01:**
  - `MG01NiryaForcegreet` (00037996) is an unused pass force-greet that walks to the player. Its topic is
    `MG01NiryaStage20BranchTopic`, conditions stage < 30 and `NiryaSpellSuccess == 1`.
  - Faralda's escort is `MG01NiryaTravel1–5` (Escort) interleaved with `MG01NiryaCastMageLight1–5`
    (UseMagic at `MG01NiryaCastMarker1–5`), conditioned on MG01 == 30.
- **The wells:** three CollisionMarker refs (0010BF7A, -7B, -7C) carry `MG01WellCollisionScript`. Its OnHit,
  for Magelight from the Faralda alias only, sets `fmagicburnamount` on the linked well and disables itself.
- **Dialogue branches (DLBR DNAM):** 0x1 top-level, 0x2 blocking, 0x4 exclusive.
  - *Blocking* = opens any conversation the player starts.
  - *Exclusive* = while in it, only its topics show.
  - Vanilla force-greet topics are mostly in blocking branches (283 of 339).
  - **Use blocking only (0x2) for an NPC's greeting branch**, as vanilla Faralda's own bridge branches do,
    and hide her other topics with a condition on those vanilla lines. We first used 0x6 (blocking +
    exclusive, as the `dunMossMother*` branches do) to hide them, and it eventually muted Nirya for good
    (gotcha 19).
  - Top-level + exclusive (0x5) only takes over while a force-greet package is running.
- **Shared info (INFO DNAM) also requires the borrowed INFO's own conditions to pass**, and very likely its
  quest to be running. Lines from `DialogueGeneric`'s shared and hello topics have no conditions, so they
  play. We still made our *Goodbye* lines own copies rather than shares while chasing gotcha 19. It's
  unproven that sharing them mattered (one run), but a copy rules it out for the cost of one `.fuz`.
- **Voice file names:** `sound/voice/<plugin>/<voicetype>/<quest>_<topic>_<formid>_<n>.fuz`.
  - `<plugin>` is the record's file of *origin*, so an INFO re-created in your plugin (e.g. one deleted
    from Skyrim.esm) looks under your plugin's folder.
  - `<quest>`/`<topic>` are the EDIDs, lowercase, sharing **25 characters**. All vanilla samples fit "the
    quest keeps at least 10 when both are long", but two different rules fit them for a 26-character pair,
    so keep yours ≤ 25.
  - `<formid>`: for an ESL, the **low 12 bits**, zero-padded to 8 (`00000c42`), even for a record with
    master index 00.
  - `<n>` is the TRDT **response-number field**, not the response's position: 000C9F06 has one response
    numbered 3, so its file is `_3`.
- **Skyrim.esm is localized.** Copied FULL/NAM1/RNAM hold string-table IDs; a non-localized plugin must
  store the text (from `strings/skyrim_english.*` in `Skyrim - Interface.bsa`).
- **Persuasion:** vanilla compares `GetActorValue Speechcraft` against a difficulty global
  (`SpeechVeryHard`, … `SpeechAverage` = 50) with the "use global" op flag (0x04), OR'd with an Amulet of
  Articulation check. `FavorDialogueScript.Persuade()` gives the XP.
- **Faralda's vanilla flow** waits on the bridge trigger's `BridgeWarning` (on
  `MG05WinterholdUpdateTriggerScript`, ref 00050785). Setting it to 1 at start switches off the cut warning
  scene, but also lets her force-greet from far away; add a distance condition.

## Build steps
1. Clone vanilla records in a script, never by hand. Assign your own IDs from 0x800 for an ESL.
2. Give the quest a SEQ file if it's start-game and has dialogue.
3. Compile Papyrus with the CK compiler: `-all -f=TESV_Papyrus_Flags.flg -i="Data\Source\Scripts;<yours>"`.
4. For each own-voice line, copy its INFO's TRDT/NAM1 (delocalized) instead of DNAM, and copy the recording
   from `Skyrim - Voices_en0.bsa` under the rule above. Assert quest + topic EDID ≤ 25.
   These `.fuz` copies are Bethesda's files: fine in your own build, but a published mod must not include them.
   Give a release an install step that copies them from the player's own `Skyrim - Voices_en0.bsa` (and adds
   any generated lip data), or reuse the line through shared info where its conditions pass.
5. Stage **everything** into the mod folder every time (plugin, Seq, Sound replaced, .pex, sources).
6. Test on a new character.

## Verification
Oracle: the real game, a new character per build, console reads (`getstage MG01`, `getglobalvalue …`,
`prid 50785` + `sv`), and a numbered checklist the human ticked per build. Later, a dev-only **test power**: a
lesser power the quest gives only while a debug global is 1. One key opens message-box menus that set up each
test (put the gatekeeper on watch, give the note, count the spell as cast, Speech 100, let me in, the stage-30
check, status, and a Dragonborn set-up). The Dragonborn button sets Elder Knowledge (MQ205) to stage 50 and
teaches and equips Unrelenting Force. MQ205 has no start-up stage, so `SetStage(50)` on a new game only starts
MGMainQuestBridge and completes two objectives. Message-box buttons are laid out side by side, so keep labels
short and split them into small menus. A Papyrus user log names every line as it's said (begin fragments log the
INFO, and a table written by the build maps IDs to text). Skyrim rotates user logs on every load, so do at most
four runs between reads. Verified: every behaviour in the summary, including voice and lip sync on copied lines,
and both gatekeepers staying put mid-exam across a shift change (Nirya's note at night then waiting into day;
Faralda's test by day then waiting into night). Less certain: Faralda's behaviour when her takeover starts at a
spell stage (it worked, but was tried only a few times). Nirya's force-greets: every run since gotchas 13 and 22
were fixed worked, but that's a handful of runs.

## Gotchas
1. **NPCs got stuck at the College gate at a shift change.** **Cause:** the gate is "requires key" with no
   key. **Fix:** walk to a gate marker, wait until the player has no line of sight (max 15 s), then
   `MoveTo` through. Set the "inside" global *before* the move, or her dialogue briefly thinks she's still
   inside.
2. **Second warning line needed a click.** **Cause:** our writer ignored the INFO flags; also a visible
   "(continue)" prompt. **Fix:** ENAM 0x40 (invisible continue), and the continuation topic has **no FULL**,
   like vanilla's.
3. **Talking first got her vanilla opener ("It's lies…").** **Cause:** it's in a *blocking* branch, which wins
   player-started conversations. **Fix:** override that INFO with a "First Lessons stage 30 done" condition
   (`GetStageDone`, which survives the quest stopping), and give your own greeting a blocking branch with a
   higher topic priority. Don't make it exclusive (gotcha 19).
4. **Subtitle showed garbage ("xA…").** **Cause:** copied vanilla text fields held string-table IDs. **Fix:**
   delocalize on copy, and sweep the plugin for 4-byte text fields.
5. **Re-created cut line silent.** **Cause:** the file must sit under *your* plugin's voice folder, with the
   ESL low-12-bit ID. **Fix:** put a copy of the vanilla `.fuz` there (from the player's own BSA, see build
   step 4), with generated lip data spliced in (the vanilla one had 0 bytes of lip).
6. **Persuasion option vanished at Speech 50+.** **Cause:** the success line borrowed 0006B942, conditioned
   on DGArrestQuest's alias. **Fix:** a copy of the text and recording instead of shared info.
7. **The whole Dragonborn route missing at MQ205 stage 50.** **Cause:** its lines were shared from
   MGMainQuestBridge, which isn't running and needs stage 2 for some lines. **Fix:** copies.
8. **Own voice copy silent twice.** **Cause:** guessed EDID shortening for a 26-character quest + topic.
   **Fix:** rename the topic so the pair is ≤ 25. Then once more after a rebuild: a record ID moved and MO2
   kept stale files. **Fix:** stage everything, every time.
9. **Force-greet spoke its line but opened no conversation.** **Cause:** our "no talking mid-walk" script
   `BlockActivation`s her when she's 300+ units off her spot, and a force-greet walks her to the player.
   **Fix:** exempt force-greet packages and in-dialogue, and stop blocking once her spell has succeeded.
10. **Force-greet never reached the player.** **Cause:** we'd cloned Faralda's bridge force-greet (000AF0F1),
    which waits near itself. **Fix:** clone vanilla's approach-the-player one (00037996).
11. **Force-greet only fired if you stood around.** **Cause:** package conditions are only rechecked at
    routine AI evaluations. **Fix:** `EvaluatePackage()` when the player enters range (vanilla does this from
    triggers).
12. **Script-spoken lines (`Say()`) silent** (pass line, Shout reaction). **Fix:** make them dialogue opened
    by a force-greet, with the fragment doing the work.
13. **Pass force-greet: she said her line, but no conversation opened (no camera lock; the player could
    walk off).** **Cause:** her greeting was a single Goodbye INFO, and a Goodbye greeting is spoken like a
    hello and never opens the dialogue. (Earlier, a plain line with no links stayed open with "...".)
    **Fix:** vanilla Faralda's structure (0001F811 → 000B8119). The first line is a plain one with Invisible
    Continue (ENAM 0x40), linking a promptless topic whose one line is the Goodbye, and the let-in goes in
    that line's end fragment. A two-response vanilla line becomes two own-voice copies, one per response.
14. **"End fragments on Goodbye lines don't fire" was wrong, and we believed it for weeks.** They fire:
    Faralda's sale line has used one since, and a test build moved every Goodbye line of the bridge branch to
    end fragments with all their effects intact. The early "it didn't fire" was most likely gotcha 19.
    Vanilla mostly uses end fragments on Goodbye lines (686 end vs 113 begin in blocking branches).
15. **Wells didn't light for Nirya's Magelight.** **Cause:** the vanilla well script checks for Faralda's
    alias. **Fix:** forced-ref aliases on the three collision markers, with our own OnHit doing the same for
    Nirya.
16. **"I don't know that spell" checked the wrong spell for Healing Hands.** **Cause:** vanilla's own cut
    dialogue and Faralda's sale use `HealOther` (00012FD2, "Heal Other"). Healing Hands is 0004D3F2 (tome
    000A271E). The vanilla *cast* check is right (it uses Healing Hands' effect).
17. **Exclusive branch hid her College topics during the escort, but "help me" still showed.** That's vanilla
    `FreeformWinterholdCollegeA`, not a mod. A blocking + exclusive escort branch hides it too. That escort
    branch has no Goodbye lines and never caused gotcha 19; with Goodbye lines, prefer conditions.
18. **Toggling an unrelated plugin "fixed" a bug.** It was coincidence: intermittent AI timing. Read the
    plugin's records before believing it.
19. **After the pass, Nirya never talked again: hello barks only, no menu, not even "It's lies".** It
    survived `stopquest` of our quest, save/load, `disable`/`enable` and `resetai`, and any save made after
    the trigger carried it. Before the pass she seemed fine, because her bridge branch still opened.
    - **Established, by single-variable tests on new games:**
      - It needs her greeting branch to be **blocking + exclusive**. Set blocking only (0x2) and it never
        happens. That's the fix.
      - It needs a conversation in that branch to **end on a Goodbye line picked from her menu** ("It's all
        in this note.", the successful persuasion). Leaving with Tab never triggered it, and neither did a
        force-greet Goodbye greeting with no menu.
      - There's a third ingredient specific to her branch: Faralda's takeover branch is also blocking +
        exclusive with a menu-picked Goodbye line, and Faralda was fine. **Not found.**
    - **Ruled out (each with exclusive on):** a link from the exclusive branch to another quest's topic (all
      58 links that leave an exclusive branch in Skyrim.esm stay in their own quest, so it looked unique);
      the scripted opening and its Invisible Continue line; begin vs end fragments; what the fragment does,
      latent waits in it, or where its work runs; flags changing mid-conversation on their own.
    - **The symptom shows long after the trigger.** The note conversation broke her; it only became visible
      when the pass switched the branch off. For weeks we tested the pass.
    - **How it was found:** bisect, not theories.
      - Vanilla at the same stage (`setstage MG01 30`, mod off) talked.
      - A fresh game with the mod, straight to stage 30, talked.
      - Then one conversation step at a time from new games, with our quest stopped and First Lessons set
        to 30 as the check.

      About ten theory builds before that each fit part of the logs and were wrong.
20. **The test itself can lie.** A save made after the trigger fails every test, whatever the build. And a
    logging fragment we added to the "It's lies" override broke the very check that relied on that line.
    Use new games only, and never instrument the thing your check depends on.
21. **Papyrus timing traps.**
    - `IsInDialogueWithPlayer()` already reads false while an NPC speaks a Goodbye line, or a greeting that
      opened no conversation.
    - `GetDialogueTarget()` stays on whoever she last spoke to (her hello barks set it too), so it's no "in
      conversation" check.
    - `RegisterForSingleUpdate` doesn't tick in menus, and a busy update takes far longer than its interval:
      time things with `Utility.GetCurrentRealTime()`, not by counting ticks.
    - A begin fragment on a shared line fires once per response.
    - A type name can't be a variable name: `action`, `shout` (Action and Shout are types).
22. **After the Shout she said "You do indeed have the power…", but nothing followed until the player talked
    to her.** **Cause:** another quest's alias package won.
    - Alias packages are ranked by quest priority.
    - Vanilla MGMainQuestBridge (priority 80; Elder Knowledge's stage 50 starts it) has its own Nirya
      force-greet for the shout, `MGMQBridgeNiryaForcegreet`, valid at its stage 5.
    - That force-greet names no topic, so her greeting was spoken like a hello (as in gotcha 13).
    - Ours, in a priority-75 quest, never ran.

    **Fix:** override the vanilla package with one more condition, so it stands aside while ours is due (our
    "Shout seen" global is 2). Nothing else in that quest's package stack for her applies at stage 5. When an
    NPC says the line but nothing follows, check in the log which package actually started, and every quest
    whose alias holds that NPC.
23. **Detecting the Shout.**
    - `OnSpellCast` passes the shout word's spell, so `akSpell as Shout` is never true.
    - Vanilla's own check (`MG01ShoutUpdate`, a story-manager quest) waits 3 s before it flags the shout.
      Vanilla's force-greet in gotcha 22 starts at once, so she could arrive before we knew.

    **Fix:** the player's `GetVoiceRecoveryTime()` jumps up on a shout and otherwise only runs down. Record it
    when the wait starts, and compare it on every `OnSpellCast` and every poll.
24. **Once it all worked, every step felt slow.** The waits added while chasing gotcha 19 were no longer
    needed: changes applied 2 s after a conversation, and the let-in 8 s after her last line.
    - **Fix:** put the Goodbye lines' work in end fragments (they fire once she has finished speaking), then
      wait 0.5 s and 1 s.
    - **Walking speed:** a package's speed is PKDT flag 0x2000 ("preferred speed") plus byte 6 (0 walk, 1 jog,
      2 run, 3 fast walk). Without the flag, byte 6 is ignored: 4386 vanilla packages hold 2 there and walk.

## Assets
None generated. Voice: vanilla recordings copied from `Skyrim - Voices_en0.bsa` into the local mod folder
(restored audio, credited). They're game files, so a public release copies them from the player's own install
at install time instead of shipping them (build step 4). One lip file was generated with the CK's LipGenerator
for a `.fuz` that had none.

## Cost and time
Several long sessions, about 68 test builds for segment 1. Most of the time went on dialogue-engine
behaviour (gotchas 2–3 and 6–14), and the largest single share on gotcha 19.

## Open questions
- Gotcha 19's third ingredient. Untested differences between Nirya's branch (breaks) and Faralda's (fine):
  - her start topic also holds Goodbye greetings, while Faralda's holds one plain line;
  - the same speaker has a second exclusive branch in the quest (the escort);
  - hers is much bigger, with menu links fanning out to many topics.

  Vanilla has 11 Goodbye lines in blocking + exclusive branches (Moss Mother, Karliah, Delphine…), and they
  work.
- Whether Nirya's force-greets are now fully reliable: every run since gotchas 13 and 22 were fixed worked,
  but that's a handful of runs. The earlier "occasionally unreliable" may well have been those two.
- The exact EDID shortening rule for quest + topic over 25 characters: a vanilla example with a 26–30
  character pair and a short quest name would settle it.
- Whether shared info fails on the borrowed INFO's conditions only, or also on its quest not running
  (gotcha 7 had both).
