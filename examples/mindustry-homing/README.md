# Mindustry: a free single-player homing lab

An original MIT-licensed JSON/JavaScript example for **Mindustry 160.7**. Two copper-fed turrets fire at
identically scripted moving targets with fixed aim. The bullet definitions use `MissileBulletType` and
change `homingPower` from **0** to **0.08**; colours identify the lanes. This is a controlled steering
demonstration, not a normal-play damage benchmark.

## Tested setup and cost

- Mindustry 160.7, official [author's itch.io distribution](https://anuke.itch.io/mindustry), which offers a
  free download. Steam, an external mod loader, paid assets and a fal API key are not required.
- macOS 15.7, Apple M1 Max, official x86_64 app under Rosetta, bundled Java 25.0.1.
- Original case built with Codex (GPT-6) and Universal Modder 0.2.0, revision `8370faa`.
  Knowledge search, scan, backup and publication checks were used. Mac window control used desktop
  automation, not the Windows-only `um win` commands.
- Running the finished mod needs no coding-agent account. Editing with a hosted agent may incur usage
  fees. Other systems and multiplayer have not been tested.

## Package and run

From this repository's root on the tested Mac:

```sh
cd examples/mindustry-homing
python3 -m zipfile -c /tmp/modlab-homing-lab.zip mod.json content scripts sprites README.md LICENSE
```

1. Back up existing game data and use a separate lab profile. Save and exit any other active world.
2. In Mindustry, choose **Mods → Open Folder**, quit, copy the ZIP into that folder, keep it zipped, and
   restart. `mod.json` must be at the archive root. The Mac **Import File** picker did not open during
   testing; that alternative remains unverified.
3. Choose **ModLab Homing Lab [F8]** from the main menu or press F8 (some Macs need Fn+F8). Wait for the
   30-second simulation-time comparison. The helper reads turret `totalShots` and counts real target
   `UnitDamageEvent` events; it writes `modlab-last-run.json` in the game-data folder.
4. F8 restarts this temporary arena; F9 exits. The helper rejects network connections and other active
   worlds. It does not save a campaign.
5. Exit with F9, disable the mod in Mods and restart to remove the lab menu entry. Restore a pre-install
   backup for any existing world that used the new blocks.

## Read the saved run

The helper writes `modlab-last-run.json` to the game-data folder, the parent of the folder that
**Mods → Open Folder** opens. It is plain JSON, written when the 30 seconds are up and again when F9 exits the lab:

- `shots` and `hits` have two entries. Index 0 is the straight baseline lane and index 1 is the homing lane.
  Shots are each turret's `totalShots`; hits are `UnitDamageEvent`s on a lane's target from bullets its own
  turret fired.
- `simulationTicks` and `durationSeconds` (ticks / 60) are simulation time, which stops while the game is
  paused.
- `finished` is `false` if F9 ended the run before 30 seconds. Those counts are not a finished comparison.

A lane with zero shots has no hit percentage. The counts describe this scripted arena only: they don't prove
where a log came from, and they are not a normal-play benchmark.

Optional: ModLab's [run log viewer](https://github.com/liubrain39/universal-modder-run-log-viewer) (MIT, by
this example's author) is a static page that shows both lanes, checks the counts and timing, and previews or
downloads the selected run as CSV. Served locally with `python3 -m http.server`, it reads the file in the
browser and sends it nowhere.

## Recorded verification

The [existing field note](../../knowledge/games/mindustry/mindustry-160-7-a-reproducible-json-and-javascript-homing-la.md)
documents both the original run and a clean-profile installation of the released 0.1.0 ZIP. Each recorded
**25 launches** per lane: **1 target-damage event** for straight bullets and **24** for guided bullets.
The six engine-loaded files here are copied unchanged from that tested mod; this example's README and
packaging are separate from the historical ZIP checksum in [the saved record](evidence/mindustry-verification.json).

Targets have scripted movement and extra health. Engine timing can change the counts. The suggested
`homingPower: 0.02` edit is an unmeasured learner experiment; keep the baseline unchanged and edit one
value before repackaging. Independent learner acceptance and normal automatic-targeting balance remain
unverified. The recorded clip is a montage of actual game-window screenshots, not continuous 24-fps video.

[Recorded workshop, complete installation and recovery](https://modlabguides.online/workshop/mindustry-homing).
The source and geometric turret sprites are original ModLab work under the included MIT license; no
game files or extracted assets are included. ModLab is independent of Mindustry and Universal Modder.
