---
kind: technique
title: "Reading TrackMania GBX containers and getting meshes out without Nadeo tooling"
tags: [trackmania, maniaplanet, gbx, nadeopak, mesh-extraction, noesis, file-formats]
date: 2026-10-06
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
---

# Reading TrackMania GBX containers and getting meshes out without Nadeo tooling

> TrackMania and ManiaPlanet ship their content in `GBX` containers and encrypted `NadeoPak`
> archives. This note records what the container looks like, which parts of the ecosystem are
> open and which are not, and the routes for turning level parts and car meshes into OBJ.
> The first thing to try is GBX.NET; the two Noesis/dxripper routes are XeNTaX-era routes.
> Nothing here was re-verified in-game: the facts are distilled from the XeNTaX-era
> community threads and the tm-wiki PAK page, so treat the numbers as a starting point to check
> against your own files.

## When to use it

- You have `.Map.Gbx`, `.Replay.Gbx`, `.Pack.Gbx` or decompressed car `*.Gbx` meshes and need
  to know what you are holding and whether any public tool can read it.
- You want level geometry or car meshes out without writing a parser from scratch.
- You are deciding whether a Pak archive is worth attacking, before spending a day on it.

## How

### Container basics

| Property | Value |
| --- | --- |
| Magic | ASCII `GBX`, 3 bytes at offset 0 |
| Payload | Serialized object graph; the header names the main object type |
| Variants | Binary for levels/replays/models; ASCII text variants exist in older games (the TM Nations ESWC-era config files) |
| Extension case | Both `.Gbx` and `.gbx` are seen in the wild |

The double extension is meaningful, not decoration:

| Extension | Contents |
| --- | --- |
| `.Map.Gbx` | map |
| `.Challenge.Gbx` | map in pre-ManiaPlanet games (TrackMania Original/Sunrise era) |
| `.Replay.Gbx` | replay |
| `.Pack.Gbx` | title or content pack (this is the Pak format; it does not carry the `GBX` magic, see below) |

### NadeoPak archives

`.Pack.Gbx` is a `NadeoPak` archive, not a `GBX` object graph: those files start with the ASCII
magic `NadeoPak`, so check the first bytes before trying a GBX parser on one. TrackMania Turbo
(2016, ManiaPlanet engine) ships `NadeoPak r18` containers. The header is readable; the payload
is encrypted with a key, reported in the 2016 threads as Blowfish. At the time, the community
wiki documented the layout while the only forum tool could read headers and show no content, and
car audio stayed locked inside the same container. Plan on the Pak being closed unless you bring
your own analysis, and do not build a workflow that depends on someone passing a key around.

For content already installed in your own copy, the current in-game route is Openplanet's
developer-mode pack explorer (`Fids::Extract`), which enumerates and extracts the game's own
packs offline — no key passing and no reverse engineering needed for your own install.

### Route 1: GBX.NET for `Mesh.Gbx` and `CPlugSolid2Model`

GBX.NET (BigBang1112; MIT, though its LZO package is GPL-3) is a maintained .NET library that
reads and writes `Mesh.Gbx` and `CPlugSolid2Model` across TrackMania Forever, ManiaPlanet and
TrackMania 2020. Try it first: it covers the GBX object graph and the mesh models directly, and
the Blendermania Blender add-on is built on it. The two XeNTaX-era routes below are kept
for the cases where they still help.

### Route 2: dxripper for whole-level geometry (XeNTaX-era route)

dxripper captures a TrackMania 2 level as a single mesh. You get geometry, but not per-part
files with their original names, so it is a viewer/rip path rather than an asset pipeline.

### Route 3: Noesis plugin for GBX meshes (XeNTaX-era route)

A Noesis `.gbx` plugin by Tuliopilloto (posted on the vg-resource forums) imports GBX models and
exports OBJ. It was tested against a single sample file, which matches its failure profile:

| Limitation | Symptom |
| --- | --- |
| ASCII GBX | Plugin fails outright on the text variants |
| Decompressed GBX | Reads many/most cars partially; `uv size` style errors |
| One sub-mesh only | Shakotay2's patched script loads a single sub mesh, then fails on `MainbodyHigh.Solid.Decompressed.Gbx` |
| Clumped geometry | Every vertex lands at the same location, because the vertices need the bone transformation info applied |
| Mesh count | A user-side patch fixed the count, the other problems stayed |

### Mesh layout worked out from the patched script

This is what shakotay2's patched script assumes, useful as an entry point for your own parser:

```
GBX magic (3 bytes)
seek +0x89 from the start -> NumMeshes (uint32)
per mesh:
  pattern search 0E 60 00 09 38 00 00  -> mesh block
  MaterialName: 8 bytes ASCII
  VCount:       uint32
  UVs:          VCount * 8 bytes (float2, stride 8)
  VertexBuffer: FVF size 40 bytes per vertex
  FCount:       uint32
  Indices:      FCount * 2 bytes (uint16, triangles)
```

40 bytes per vertex and uint16 indices, with the material name as a fixed 8-byte field, are the
numbers to verify first against a file you can read end to end.

### Textures are not in the GBX

Meshes reference textures that live outside the container. Samples pulled from map packs often
contain no embedded texture data at all, so a successful mesh import still leaves you looking
for the texture set.

## Gotchas

1. **Plugin reads nothing, no error.** ASCII GBX variant. The plugin only handles the binary
   form; check the first bytes and the file's origin before blaming the plugin.
2. **`uv size` error on a car.** Decompressed GBX. The plugin's decompressed-path support is
   partial; try the undecompressed original first, or only the parts that parse.
3. **All vertices at one point after import.** Missing bone transformation. A reported cause from
   the 2022 thread, not re-verified here: the vertex data is stored in bone space, so a raw import
   collapses; apply the skeleton/bone transforms or import through a tool that does.
4. **Import dies on `MainbodyHigh.Solid.Decompressed.Gbx`.** Known failure of the patched script,
   which was shipped without a sample file, so nobody could debug it further.
5. **Mesh imports, no texture.** Expected: textures are separate assets, not embedded.
6. **Pak archive yields headers only.** The container is encrypted; a header reader is not an
   extractor. As of the 2016 threads there was no public Pak unpacker; for your own install, use
   Openplanet's developer-mode pack explorer (`Fids::Extract`) instead of parsing the container.

## What this does not prove

- None of these paths were re-run here and none were confirmed in-game; the mesh layout numbers
  come from a script patched against a single sample.
- The Blowfish identification is a 2016 forum report about `r18`, not a confirmed cipher spec.
- The 2016 threads reported no working public extractor for ManiaPlanet Paks, but absence of a
  published tool is not proof that none exists; Openplanet's developer mode extracts your own
  copy's packs without one.
- Importing a mesh says nothing about whether the game will accept a modified one; that needs its
  own round-trip test.

## Seen in

Distilled from the XeNTaX thread t=24378 (shakotay2 and fajNYgosciu1234, 2022–23), the 2016
TrackMania Turbo pak thread, Tuliopilloto's vg-resource thread, and the tm-wiki PAK page.
