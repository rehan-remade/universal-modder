---
kind: game
title: "Detroit: Become Human: SEGS/DATA_CONTAINER editing (mesh, animation, cloth) in Blender"
game: "Detroit: Become Human"
games_also: []
game_version: "Detroit: Become Human PC (Epic/Steam) retail install; build not pinned"
platform: windows
engine: native
route: data
tools: ["Blender 4.0+", "Detroit Blender Addon by TheLeonX (Nexus Mods)"]
anti_cheat: "none; single-player, data packages only, executables and DRM untouched"
status: in-progress
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
date: 2026-10-07
links: ["https://www.nexusmods.com/detroitbecomehuman/mods/139"]
tags: [quantic-dream, segs, data-container, meshdata, havok, cloth, animdata, filetext, blender, bigfile, native-container]
---

# Detroit: Become Human: SEGS/DATA_CONTAINER editing in Blender

> Detroit runs Quantic Dream's in-house engine, and its PC data sits in a `QUANTICDREAMTABINDEX`
> archive (`BigFile_PC.idx` plus its data file). Assets are `segs` members: chunked, individually
> compressed blobs, each carrying a native container with `MESHDATA`, `ANIMDATA` or Havok blocks.
> The route below is a Blender 4.0+ add-on, *Detroit: Become Human DATA_CONTAINER / SEGS*, written by
> **TheLeonX** and published on Nexus Mods as
> [Detroit Blender Addon](https://www.nexusmods.com/detroitbecomehuman/mods/139) (downloading it needs a
> Nexus account). It reads those members, lets you rebind a custom mesh to an existing slot, and writes
> the container back in the same layout. This note records the formats and the workflow as the add-on
> implements them (the `.py` files cited below are its modules); we have not yet confirmed its exports in
> the running game, so the export paths are marked unverified below.

## Setup
- Detroit: Become Human, PC release (Epic or Steam). The add-on needs the game's `BigFile_PC.idx`; set it
  in the add-on preferences. An optional folder of converted textures is used when a material points at an
  external image.
- Textures are addressed by **hex resource or material ID**, not by path — the preference help spells it as
  `3AB53.png`. A file with any other name resolves to nothing.
- The geometry and container codec does not import `bpy`; only the operator layer does. That means the same
  codec can be driven headlessly to validate a package without launching Blender.
- The add-on ships a bone-name table and a reference-tool bridge for the skeleton. The bridge builds a
  private, compressed-only copy of an archive for the reference reader and never opens a game archive for
  writing.

## Route
- **Archive index.** `BigFile_PC.idx` starts with `QUANTICDREAMTABINDEX`; the header is 105 bytes and each
  record is 28 bytes (`reference_archive.py`). Parsing just needs that stride and the magic check.
- **SEGS container.** One member is a header `<4sHHII` = magic `segs`, an attributes word, a block count,
  the total unpacked size and the packed span, followed by `<HHI` block entries (packed size, unpacked size,
  offset) at 16-byte alignment (`segs.py`). Blocks are chunked so each stays inside
  the `uint16` size fields; a chunk that fails to shrink is stored raw (`segs.py`,
  `reference_archive.py:compressed_member`).
- **Native container and geometry.** Members wrap a native container whose records point at payloads.
  Geometry is `MESHDATA` **version 41**: variable-buffer, submesh and group tables plus an optional
  `CLUPSKME` block for skinned/cloth metadata and a `BLSHAPES` block. The add-on's source says its decoder
  follows the game's v41 reader (`0x140296B40`); not re-checked in the exe here (`native.py`).
- **Replacement workflow.** Import the `.segs`/DATA_CONTAINER, keep the imported game rig, then select a
  custom mesh and run *Use Selected Mesh as Replacement*. The operator binds the mesh to the named game
  slot, transfers bone weights from the game rig and rebuilds the growing geometry buffers in place
  (`__init__.py`, `native.py`). Unweighted vertices can be given nearest native weights, and a
  mesh can be attached to or detached from a game bone.
- **Animation.** `ANIMDATA` **v13/v14** is read independently: rotations are `XYZW` quaternions and
  positions keep their bind-position coefficient; relative rotations keep track flag `0x40`
  (`animation_codec.py`).
- **Textures.** New images are written as experimental self-contained `FILETEXT` **v24** BGRA8 resources
  with their own SEGS streams rather than BigFile overrides; the author calls out the renderer paths
  `140258050`, `140256310` and `1402580B0` and marks each shader family as needing its own in-game check
  (`texture_export.py`).
- **Cloth.** New-topology cloth is authored without the Havok SDK by copying a donor character's native
  `TYPE` table (Havok 20160200) and rebuilding allocations, item indexes and patch fixups from typed values.
  The route requires a character family that already has exactly one native cloth companion (record kind
  `2150`) and only writes the verified 48-byte native cloth output layout (`cloth_build.py`, `cloth_route.py`).

## Verification
- **Read from the add-on's source (not checked against the exe or game files):** the v41 `MESHDATA` decode,
  including the variant whose flag 1 embeds the first stream after the header, and the game reader
  addresses it cites (`0x140296B40`, `0x140321120`); the SEGS header/entry sizes and 16-byte alignment; the
  `QUANTICDREAMTABINDEX` index layout (105 + 28·n); `ANIMDATA` v13/v14; the cloth donor requirement and its
  record kind; `FILETEXT` v24.
- **Not verified:** no export from this add-on has been confirmed in the running game by us. The author
  labels the texture and new-topology cloth exporters experimental, and the texture path is documented as
  per-shader-family. Treat mesh replacement as the solid part and cloth/texture authoring as trials.
- **Not established:** whether a growing-buffer mesh replacement survives every character family, and what
  the engine does with an oversized rebuilt slot.

## Gotchas
1. **Fixed slots only.** The route replaces content at an existing index; it does not add new resources.
   New textures are the one exception, and that path is experimental.
2. **`uint16` block sizes.** Members are chunked (60,000-byte chunks in the reference path) with a stored
   fallback when compression does not help, because the packed and unpacked sizes live in 16-bit fields.
3. **Texture identity is a hex ID.** `3AB53.png` is a valid name; `aiden_shirt.png` is not. A wrong name
   fails quietly as a missing texture.
4. **Cloth needs a donor.** A character family with no native cloth companion, or more than one, is refused;
   the PN deformation type table comes from the donor and differs between families.
5. **Blender 4.0+.** The operator layer targets Blender 4.0 or newer, but the codec is plain Python, so
   validate exports headlessly before blaming the viewport.
6. **Do not point the reference bridge at your game install for writes.** It makes a private copy for the
   reference reader precisely so the game archives stay untouched.
7. **Keep game files out of notes and repos.** The bone table and index are read from the user's own
   install; nothing extracted from the game belongs in a committed note.
