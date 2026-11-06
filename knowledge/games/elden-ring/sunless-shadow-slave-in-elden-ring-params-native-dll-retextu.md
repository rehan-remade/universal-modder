---
kind: game
title: 'Sunless (Shadow Slave) in Elden Ring: params, native DLL, retextures and a shade army'
game: Elden Ring
games_also: []
game_version: 1.17.1 (exe ProductVersion 2.7.1.0), Steam, Shadow of the Erdtree installed
platform: windows
engine: fromsoft
route: native-hook
tools:
- me3 0.13.0
- WitchyBND 3.0.1.0
- texconv (DirectXTex)
- fromsoftware-rs (eldenring + fromsoftware-shared)
- hudhook 0.9.3
anti_cheat: EAC, avoided entirely - me3 starts eldenring.exe directly (not start_protected_game.exe), so EAC never loads; offline only, separate savefile
status: working
agents:
- Claude Opus 5
humans: []
date: '2026-10-11'
links:
- https://github.com/garyttierney/me3
- https://github.com/vswarte/fromsoftware-rs
- https://github.com/ividyon/WitchyBND
- https://github.com/veeenu/hudhook
- https://github.com/microsoft/DirectXTex
tags:
- fromsoft
- params
- flver
- matbin
- spirit-summons
- retexture
---
# Sunless (Shadow Slave) in Elden Ring: params, native DLL, retextures and a shade army

A playable Sunless from *Shadow Slave*: an aimed shadow teleport costed in FP, a
shapeshifting mirror sword that learns elements from greases, a near-death
damage blade, and an army of black silhouettes raised from whatever you have
killed. Three new weapon rows with their own models and textures, a rebuilt
`regulation.bin`, and a native Rust DLL loaded by me3. It runs in the real game;
the Verification section separates what was observed from what was only reasoned.

The parts worth stealing regardless of what you are building: a **scriptable
param pipeline with a round-trip proof**, a way to **read the game archives
without touching RSA keys**, the **FLVER → MATBIN → TPF** chain that decides
whether your model renders at all, and a full account of Elden Ring's
**spirit-summon system as a general-purpose "spawn an ally" mechanism**.

## Setup

| | |
|---|---|
| Game | Elden Ring 1.17.1, exe ProductVersion **2.7.1.0**, Steam appid 1245620, SOTE installed |
| Loader | [me3](https://github.com/garyttierney/me3) 0.13.0 |
| Bindings | [fromsoftware-rs](https://github.com/vswarte/fromsoftware-rs), pinned by git **rev**, not branch |
| Params/archives | WitchyBND 3.0.1.0 |
| Textures | `texconv.exe` from DirectXTex |
| Overlay | hudhook 0.9.3, DX12 backend, imgui 0.12 |
| DLL | Rust `cdylib`, `panic = "unwind"` (see gotcha 1) |

me3 starts `eldenring.exe` directly instead of going through
`start_protected_game.exe`, so EAC never loads and the game runs offline, with a
separate savefile. Nothing here requires defeating anti-cheat, and the modded
client must never go online.

**Pin the bindings by revision.** crates.io `eldenring` 0.14.0 only carries RVA
tables for 2.6.2.0/2.6.2.1 and panics on anything else. Upstream main had added
the 2.7.1.0 table; a `rev = "..."` pin gets it without a branch moving under you.

## Route and why

**Params + a native DLL + asset replacement, all delivered by me3.** Params for
anything the game already models (weapons, effects, shop entries, summon rows);
the DLL for behaviour the game has no concept of (an aimed teleport, a radial
menu, binding a creature's shade on death).

Rejected: **UXM**. It unpacks the game and patches the exe, which is heavier and
harder to undo than me3's load-order overlay. Its *dictionary* of archive paths
is still useful — see Archives.

## How the game works (what we had to learn)

### Params

`regulation.bin` is a **DCX_ZSTD-compressed BND4** holding ~194 param tables,
AES-encrypted on disk with a key that is public in SoulsFormats. WitchyBND
decrypts and unpacks it to `.param` files, each of which unpacks again to XML.

**A field absent from a row's XML is that field at its paramdef default, not
zero.** This is the most dangerous thing about scripting param edits: a row that
looks empty is inheriting dozens of values. Resolve defaults before reading
anything, and write a field only when it differs from its default.

Upgrade paths: `reinforceTypeId` / `materialSetId` **2200** is the standard
somber path (+0..+10). **`isEnhance` means "can change affinity", not "can be
upgraded"** — a weapon with `materialSetId = -1` cannot be reinforced at all,
which presents as a weapon permanently stuck at +0.

Cloning must rewrite self-references. A weapon row carries 26 `originEquipWep*`
fields describing its own upgrade chain; miss one and the tree walks back into
the original weapon.

### Text

Item names live in `msg/engus/item.msgbnd.dcx` — **and in `item_dlc01.msgbnd.dcx`
and `item_dlc02.msgbnd.dcx`, which are complete replacements, not patches.** With
SOTE installed the DLC archive wins and the base file is ignored entirely. Edit
and ship all three or your names silently do not change.

### Archives

Game data lives in `Data*.bhd` (index) + `Data*.bdt` (payload). The index is
RSA-encrypted, each file inside is AES-128-ECB with a per-file key, and paths are
located by a **64-bit hash: iteratively `hash * 133 + byte` over the lowercased
path**.

You do not need the RSA keys. **me3 leaves a decrypted copy of each BHD in its
cache** (with `boot_boost` on: `<xxh3 hash>.bhd.zz`, a u32 decrypted length and
then raw Deflate), so a reader can parse those and pull single files out of the
BDTs. Ours is ~400 lines of Python with a pure-Python AES checked against the
FIPS-197 test vector on every run, so a decryption bug cannot masquerade as a
corrupt file. The UXM dictionary is a good source for the path list.

For shared installs: filter the BHD indexes by game codename — Nightreign's
(`CL_*`) sit alongside Elden Ring's and match nothing.

### Models, materials and textures

The chain is **FLVER → MATBIN → TPF**, and the middle link is the one that bites.

A FLVER mesh does **not** reference textures directly; it names a **material**,
and the material (a MATBIN inside `allmaterial.matbinbnd.dcx`) names the textures
and the shader. So renaming a weapon's textures and byte-patching the FLVER to
match yields a **white, untextured mesh** — the FLVER now points at a material
that does not exist. You must also create the MATBIN.

MATBIN v2 layout: magic `MAB\0`, version, two `i64` offsets to shader and source
paths, counts, then a param table (0x28 per entry) and a sampler table (0x30 per
entry), with strings UTF-16LE elsewhere in the file.

**DDS header style is load-bearing.** Elden Ring ships `_m` metallic maps as
legacy `ATI1`; `texconv -dx10` writes a DX10 header for the same data and the
model renders white. The fix that works regardless of format: re-encode, then
**copy the original file's DDS header back onto the new pixel data**.

Channel meanings, established by experiment: on the normal map, **B is shininess,
not roughness** — higher is shinier. Setting it low on the theory that "blurry =
rough" produced a completely flat blade.

### Weapons cannot reflect, and this is settled

Several rounds went into a mirror-finish sword. The answer is in the game's own
data and takes one query: of **707 distinct shaders across 15,089 materials**,
screen-space reflection is enabled on **110**, and **every one is static map
geometry** on an `M[...]`-family shader. All **559 weapon materials** are on
`C[...]` character shaders, which carry the SSR parameter *name* as shared
boilerplate but never feed the SSR pass. The only true reflection shader in the
game is a cutscene ocean plane.

Metallic, shininess and the shader's colour parameters buy an environment sheen
and nothing more. If you need a mirror on a weapon, **bake it into the albedo** —
paint a horizon, because a hard edge is what reads as reflective and a smooth
brightness ramp never will, however bright you make it.

### Spirit summons as a general "spawn an ally" mechanism

The most reusable finding here. Elden Ring's spirit-ash system will summon **any
creature in the game** as a working ally, driven entirely by params plus one
integer written at runtime.

- A **`BuddyParam`** row is `{ triggerSpEffectId, npcParamId, npcThinkParamId }`
  plus an x/z spawn offset.
- `SummonBuddyManager` holds `trigger_speffect_to_buddy_map`, a **chaining** map:
  **many BuddyParam rows may share one trigger SpEffect** and are summoned
  together. That is how vanilla's group ashes work — 36 of 94 vanilla triggers
  drive more than one row.
- Writing **`request_summon_speffect_id`** asks for a summon. The binding notes
  it is "written by TAE goods consume" — the animation event fired when you use
  an ash — so writing it directly does what the game does, one step earlier.
- **The id encodes the chr model.** BuddyParam never names a model and
  NpcParam has no model field. For ordinary eight-digit enemy rows the 4-digit
  chr id is `npcParamId / 10000`: Torrent's row 80000000 is c8000, and
  `ChrIns.character_id` holds the same 8000. Dividing by 100000 drops the last
  digit and merges models: Juvenile Scholar (20400000) and Kindred of Rot Larva
  (20410000) both become 204. The purpose-built `[Spirit Summon]` rows have nine
  digits and don't follow this pattern. One integer read off a corpse therefore
  carries the entire creature.
- Rows can be rewritten **in live memory** through the param repository, so the
  roster need not be fixed at build time.

Four things the system will not do for you:

1. **Team.** A real enemy's NpcParam is on the hostile team; only the ~115
   purpose-built `[Spirit Summon]` rows carry team **47**. Force `team_type` on
   the spawned character — every frame, since the engine builds it from that row
   after you act.
2. **Appearance.** Use **`PhantomParam`** via `ChrIns.phantom_param_override`,
   the layer that makes every ash look spectral. The field that matters is
   **`diffMulColorA`**: at 0 the creature's own texture is deleted and you get a
   silhouette; vanilla's spirit row leaves it at 0.9, which is why ashes look
   like blue-tinted versions of themselves rather than shadows.
3. **Placement.** Offsets are relative to **`spawn_origin` AND `spawn_rotation`**;
   setting only the origin anchors the formation to a fixed world bearing.
   Creatures also need room — a Troll's `hitRadius` is 1.8 m, so spawn points
   1.4 m apart simply fail to place it, silently.
4. **Count.** Vanilla's largest group is 5. The practical ceiling measured here
   is **10 rows per trigger**: asking for 12 reliably lost the last two, and the
   proof it is a slot limit rather than size or placement is that a creature
   *identical in size* to ten that spawned failed purely by being in slot 10.
   Note `summon_buddy_chr_set.capacity` reports 80 — that is the ChrSet array,
   not what one trigger can drive.

**Torrent lives in the summon ChrSet too.** Anything iterating it and writing to
what it finds will modify the player's horse.

Power scaling is the doping ladder `290000..290010`, the game's own ash upgrade
levels: `290000` applies **no** HP or attack multiplier at all (so a summon keeps
the creature's native stats), while `290010` is ×7.4 HP and ×3.8 attack.

### Effects, and an inheritance trap

`spCategory` is the axis the engine uses to decide which effects **displace**
which, and a cloned SpEffect inherits it. Two of our abilities cloned from
unrelated sources that both sat in category 20 and silently fought; our
weapon-enchant effects inherited the greases' category and were displaced by real
greases while the mod still believed them active. Give mod-owned effects private
categories (the game's highest is 10010).

### Input and the camera

Elden Ring reads **DirectInput only**; nothing reaches an ImGui overlay through
raw input, so an overlay-driven radial menu gets no mouse state.

Reading `MouseDevice` works for *getting* movement, and zeroing it does **not**
stop the camera: `CSPad::poll_analog_input` reads an aggregate assembled during
`PadStep`, earlier in the frame than any mod task. The lever that works is
**`FD4BasePad.allow_polling`**, which the poll functions check first — clear it
and the camera holds perfectly still. Do it before `CameraStep`;
`ChrIns_PrePhysics` is early enough.

### Singletons exist before they are populated

`WorldChrMan::instance()` succeeding means the object exists, **not** that the
engine has filled it in. On the first frame it succeeds, its summon manager
pointer is **null** and its character counts are zero. Reading a pointer typed
non-null there and dereferencing it is a hard fault, not a Rust panic, so
`catch_unwind` will not save you.

### Bonfire (resting) state

`CSLuaEventProxy.control_flags` carries four bits: the sit-down request, the
sitting loop, the stand-up, and a pending end. **Only `bonfire_stand_up_in_progress`
is documented as being cleared when a rest ends**; the sit-down bit is only
cleared when the next rest begins. Treating "any bit set" as "is resting" reads
true forever after the first rest. What does work is edge-triggering on the
four-bit pattern *changing*, since the one bit that does clear keeps it moving.

## Build steps

1. Install me3. Unpack **your own** `regulation.bin` once with WitchyBND as the
   build's pristine input. Nothing from the game is redistributed.
2. `python params/build_regulation.py --verify` — applies a declarative row spec
   (clone-from-vanilla, or blank-from-defaults, plus field overrides), repacks,
   then re-unpacks and proves only the intended params differ.
3. `python params/build_text.py` — patches all three `item*.msgbnd.dcx`.
4. `python tools/retexture.py --all` — pulls the vanilla weapon part files,
   recolours albedo/metallic/normal, re-encodes, renames every reference (TPF
   entries, BND manifest, FLVER strings), and builds the new MATBINs.
5. `cargo build --release` in the DLL crate.
6. `python stage.py` — assembles the me3 profile: the DLL in `natives/`, and
   `regulation.bin`, `msg/`, `parts/`, `material/` in the package.
7. `me3 launch -p <profile>.me3 -g eldenring`.

## Verification

**The DLL's own log is the primary oracle.** It prints a line per ability event
carrying the numbers that decided it, plus a periodic state line. Several bugs
here sat visible in it for multiple sessions before anyone read the field that
mattered — including a count that was *one too high* printed directly beside the
count that was one too low, which turned out to be the same bug.

Also used, all repeatable without launching the game:

- **Param round-trip:** 194 params in, 194 out, only the intended ones differ by
  hash, plus a read-back of every added row and edited field.
- **A constants check** asserting the ids shared between the param script and the
  Rust, wired into staging so a drift cannot ship. Nothing else would catch it:
  the symptom is summons silently not appearing.
- **Pixel measurement of the shipped textures** — unpack from the staged build,
  convert, assert contrast and saturation. This caught a debug "probe" texture
  nearly shipping, and a blade whose bands had landed on the wooden hilt.
- **Screenshots of the running game**, then cropping and sampling pixels rather
  than eyeballing.

**Not verified:** the i-frame and stealth windows are never logged and were only
confirmed by feel; the near-death damage bonus was never observed firing; and the
mod has only ever run on this machine and game version.

## Gotchas

1. **The game dies instantly, exit code 0xC0000409, no log.** *Cause:* a panic on
   the mod's boot thread with `panic = "abort"` in the release profile. *Fix:*
   never use `panic = "abort"` in a game mod. Unwind, log from a panic hook, and
   wrap every engine entry point in `catch_unwind`.
2. **A crash with an empty log is not a panic.** *Cause:* a bad memory access,
   which `catch_unwind` cannot contain. *Fix:* use the log's last line to date
   the fault, then look for a pointer dereference in whatever ran next. "Dies on
   the first frame the world exists" is a diagnosis, not an absence of one.
3. **Dereferencing a singleton's sub-pointer on the first frame it is available
   crashes.** *Cause:* the object is published before it is populated. *Fix:*
   read the pointer as an **integer** and test it before forming a reference —
   `&*p` is undefined behaviour when `p` is null, before any read. Re-check every
   frame; a one-shot readiness test latches the wrong answer if it samples the
   empty frame.
4. **Reading an engine enum out of memory is undefined behaviour.** *Cause:* a
   `#[repr(u8)]` enum valid for 0..=5 does not tolerate a 6, and walking
   uninitialised container slots guarantees you meet one. *Fix:* read the byte,
   compare the number.
5. **Retextured weapons render pure white.** *Cause (a):* texconv wrote a DX10
   DDS header where the game ships legacy `ATI1`. *Cause (b), the real one:* the
   FLVER references a **material**, so renaming textures left it pointing at a
   MATBIN that does not exist. *Fix:* adopt the original DDS header, and create
   the MATBIN.
6. **Weapon names do not change despite editing `item.msgbnd.dcx`.** *Cause:*
   with SOTE installed, `item_dlc02.msgbnd.dcx` is a full replacement and wins.
   *Fix:* patch and ship all three.
7. **A cloned weapon is stuck at +0.** *Cause:* `materialSetId = -1`; `isEnhance`
   is about affinity, not upgrading. *Fix:* set a real reinforce path.
8. **A summoned ally is hostile.** *Cause:* you used the enemy's own NpcParam,
   which is on the enemy team. *Fix:* force `team_type` to 47, every frame.
9. **The summon appears, then vanishes seconds later.** *Cause:* vanilla ties
   summons to a buddy stone's activation range and despawns them outside it.
   *Fix:* assert the in-range flags **and their `prev_` partners**, or the
   in→out transition still fires.
10. **The summon formation faces the wrong way.** *Cause:* offsets are applied at
    `spawn_rotation`, which was never set, so the formation anchors to a fixed
    world bearing. *Fix:* set it from the player's facing — and note that
    **flipping the sign of an offset can never fix a rotation error**, it only
    changes which facing is broken.
11. **"Asked for 12, got 11", repeatedly.** *Cause — three separate ones:* a
    stale summon from the previous request holding a slot; **Torrent** occupying
    one; and a real ~10-row ceiling per trigger. *Fix:* sweep your own summons
    before requesting, exclude the horse, cap at ten.
12. **The player's horse turns into a black silhouette.** *Cause:* Torrent lives
    in the summon ChrSet and the grooming loop wrote to everything it found.
    *Fix:* exclude it. Its `character_id` is **8000** (model c8000, NpcParam
    80000000); 800 is what `npcParamId / 100000` gives, so compare like with
    like.
13. **An enable flag has no effect.** *Cause:* `g_GX_bEnableSSR` exists in every
    material's shared parameter block, weapon or not, but is only sampled for map
    geometry. *Fix:* check a parameter's *distribution* across the game before
    believing its name.
14. **Two unrelated abilities interfere.** *Cause:* both SpEffects were cloned
    from sources sharing an `spCategory`, the engine's overwrite axis. *Fix:*
    give mod-owned effects private categories.
15. **Keys fire twice or do something unintended.** *Cause:* Elden Ring binds
    most of the keyboard — `C` is Switch Item, `Space` is jump. *Fix:* use keys
    the game does not bind, and make them rebindable. Suppressing the game's own
    jump key through an input freeze is a far larger claim than not using it.
16. **A radial menu gets no mouse input.** *Cause:* the game is DirectInput-only.
    *Fix:* read `MouseDevice` directly and accumulate movement yourself.
17. **The camera keeps moving while a menu is open.** *Cause:* zeroing the mouse
    device is too late; the camera reads an aggregate built during `PadStep`.
    *Fix:* clear `FD4BasePad.allow_polling` in a pre-physics task.
18. **A modal UI's action key leaks into the game on close.** *Cause:* the input
    freeze lifts the instant the modal closes, while the key is still held. *Fix:*
    hold the freeze until the action keys are released too.
19. **A painted "mirror" reads as shiny metal, never as a mirror.** *Cause:* a
    smooth brightness ramp contains no edge anywhere, and an edge is what a mirror
    *is*. *Fix:* paint a hard horizon — and put it where the blade's UVs actually
    are; bands spread across a whole atlas gave the visible face about a third of
    one period, i.e. a gradient.
20. **Texture changes land on the wrong part of the model.** *Cause:* the UV
    layout is not inferable from the vanilla art — the smooth-looking half of one
    atlas was the crossguard, not the blade. *Fix:* ship a debug texture of
    saturated colour bands and read the answer off a screenshot. Better still,
    check the **metallic mask** first: it needs no launch, and if your pipeline
    only paints where the mask says metal, a span with no metal under it cannot
    produce anything.
21. **Param script and native code drift apart silently.** *Cause:* ids shared
    between a build script and the DLL, kept in step only by a comment. *Fix:* a
    check that asserts them, wired into the build.

## Assets

No generated art. Everything is a **recolour of the game's own textures**: the
vanilla weapon's albedo, metallic and normal maps are pulled out, worked in
perceptual space with the metallic mask separating metal from wood and leather,
and re-encoded in the original formats. Models are vanilla FLVERs copied to new
ids with their material references renamed — nothing from the game is
redistributed, and the pipeline runs against the user's own install.

## Cost and time

Several sessions across about four days. The dominant cost was not writing code
but **launch-and-look cycles** on things that cannot be previewed offline —
particle effects, shader appearance, UV layouts. Anything that reduces those paid
for itself many times over: a config file re-read once a second while the game
runs, and a debug texture that answers three questions in a single launch.

## Open questions

- **Why exactly ten summons per trigger?** Measured, not explained. The limit may
  be in the summon manager, in the chaining map, or elsewhere.
- **A genuine weapon reflection** is impossible by the route above. Borrowing a
  map shader onto a weapon mesh is the only untried idea, and the vertex layouts
  do not match, so the expected result is an invisible weapon.
- **Identifying a mesh's visible face offline.** Decoding FLVER UVs is easy;
  deciding which region the player actually *sees* is not. Vertex density is
  nearly the inverse of visible area — a flat blade is few vertices, a pommel is
  many — so it needs triangle areas. Until then the debug-texture probe wins.
- **`spCategory` semantics** are only partially understood here; we moved our
  effects out of the way rather than learning the full rule.
