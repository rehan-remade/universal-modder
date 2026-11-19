---
kind: technique
title: "Reading old ForzaTech .modelbin containers (burG), and the MakeH2O tool lineage"
tags: ["forzatech", "modelbin", "carbin", "burg", "mesh", "vertex-buffer", "makeh2o", "ghidra", "reverse-engineering", "forza-horizon-3"]
date: 2026-10-06
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links: ["https://web.archive.org/web/20231023061958/https://forum.xentax.com/viewtopic.php?t=4256", "https://github.com/noidex0/fh6-model-tools", "https://github.com/Nenkai/ForzaTools/tree/master/ForzaTools.Bundles"]
---

# Reading old ForzaTech .modelbin containers (burG), and the MakeH2O tool lineage

> Two things are recorded here. First, what a **v1.0/v1.1 `burG`** ForzaTech `.modelbin` actually
> contains: the container, its reversed tag names, the vertex-buffer layout, and how
> positions are decoded. Second, the history and internals of **MakeH2O** — the 2017 community
> converter for these files — including why it no longer reads 2017-era files cleanly. The
> container facts were read off real files; the tool facts were read by disassembly, and the
> tool's algorithm was checked by re-implementing its scan. The tool itself was never made to
> complete a conversion here.

## When to use it

- You have a `burG`-format `.modelbin` (Forza Motorsport 6 / Forza Horizon 2 / Forza Horizon 3
  era, roughly 2015–2018) and want the geometry, or you are writing a parser for it.
- You have found a `Make_H2O-ForzaHor*.exe` and want to know what it does, whether it is worth
  running, and why its log is empty or armed with complaints.
- You are deciding between reviving the old tool and using a modern burG-aware parser. The short
  answer: use the modern parser.

## How

### The container

A `.modelbin` of this generation starts with the four bytes `62 75 72 47` — ASCII `burG`, which is
`Grub` written backwards; read as a little-endian `u32` it is `0x47727562`, the `BundleTag` in
Nenkai's ForzaTools. Every one of the 53 `.modelbin` files in an FH3 sample tree starts this
way. The first byte is therefore `'b'` (`0x62`) — remember that byte, because it is exactly the
test MakeH2O applies as its format gate.

Header layout observed on real files:

| offset | v1.0 (`01 00`) | v1.1 (`01 01`) |
|---|---|---|
| 0x00 | `"burG"` | `"burG"` |
| 0x04 | u8 major / u8 minor `01 00` | u8 major / u8 minor `01 01` |
| 0x06 | u16 chunk count | u16 |
| 0x08 | u32 | u32 header size |
| 0x0C | u32 file size | u32 file size |
| 0x10 | chunk table | u32 chunk count |
| 0x14 | | chunk table |

Two real headers:

```
62 75 72 47 01 01 00 00 48 07 00 00 68 07 0a 00 1d 00 00 00   # v1.1, size 0x000a0768 = 657256, 0x1d = 29 chunks
62 75 72 47 01 00 1d 00 44 07 00 00 40 bc 10 00 6c 65 6b 53   # v1.0, size 0x0010bc40 = 1096768
```

After the fixed part comes a table of chunk entries. Each entry begins with a four-byte id which
is the tag name **reversed**:

| on disk | reads as | meaning |
|---|---|---|
| `lekS` | `Skel` | skeleton |
| `hprM` | `Mrph` | morph |
| `hseM` | `Mesh` | mesh (26 of them in one tyre file) |
| `BdnI` | `IndB` | index buffer |
| `yaLV` | `VLay` | vertex layout |
| `BreV` | `VerB` | vertex buffer |
| `fuBM` | `MBuf` | influence/weight buffer |
| `ldoM` | `Modl` | model |
| `emaN` | `Name` | LOD name metadata record |

Per entry the fields are id, flags, a metadata/unknown pointer, an offset, a compressed size and an
uncompressed size. Entries are 24 bytes in both versions; the table starts at 0x10 in v1.0 (u16 count at
0x06) and at 0x14 in v1.1 (header size at 0x08, file size at 0x0C, count at 0x10), per Nenkai's `Bundle.cs`.

A real `hseM` entry, 26 of them in a row:

```
68 73 65 4d  01 08 02 00  08 03 00 00  94 0a 00 00  d9 00 00 00  d9 00 00 00
```

### The vertex buffer

The stride-40 layout, the bbox decode and the axes below come from the FH6-era spec
(`noidex0/fh6-model-tools`) and are not yet checked on FH3 v1.x files.

Each `VerB` chunk payload opens with a 16-byte header, `<IIHHI`:

```
(vertex_count, data_size, stride, element_count, first_format_code)
```

with the vertex data beginning at payload + 16. Strides seen in the literature:

- **stride 8** — the position stream: three `SNORM16` (signed 16-bit) components.
- **stride 40** — the full stream: normals as two int16 (the third component is derived), four UV
  pairs as 2 × int16 each at bytes 4–19, a 12-byte tangent frame of three `R10G10B10A2_UNORM`
  values at bytes 24–35, and an AO mask byte at 36.

Position decode is **bbox-relative**, not scale-relative:

```
pos.x = bbox_min.x + (raw_int16.x + 32768) / 65535.0 * (bbox_max.x - bbox_min.x)
```

The per-LOD bounding box comes from the `Name` metadata region: an `emaN` record holding a `uint32`,
the four bytes `xoBB`, a `u16` `0x0180`, a `u16` count `N`, then `N` records of a name followed by
six floats (min and max for x, y, z). Coordinates are Y-up, Z-forward, left-handed.

That bbox decode is the whole reason the old tool fails — see below.

### What MakeH2O is

**MakeH2O** is a 2017 Windows GUI tool by the XeNTaX user *shak-otay*, written as one build per game
engine family. Its Forza line is distributed as `Make_H2O-ForzaHor3-*.exe`, and the build suffixes
are documented by the author:

```
-gc : grouping check, first brute force grouping
-j2 : grouping via magic table
-j2l: x mirrored (+ face winding reversed) and mesh scaled, LOD names
-jm4: material names, bugfix for lower LODs
-jm7: AMC improved
obsolete -jq: j = improved brute force grouping; q = quicksorted face indices,
              groups derived from uv-sections, forced modulo-1000 grouping for meshes > 2000 verts
```

The binaries found in the forum archive are `-gc` (Jan 2017), `-j2`, `-jq`, `-jl` (Feb 2017) and
`-jm9` (Apr 2017, the last and largest at 90,112 bytes). The copy sitting in this workspace is a
**different, earlier build** — `Make_H2O-ForzaHor_f.exe`, 70,144 bytes, dated 2017-01-21, smaller
than even `-gc` and matching none of the archived builds by size or hash. The shared `DLL_MakeH2O.dll`
(62,464 bytes, 2015-04-06) *is* identical across the workspace copy and the archive.

The executable is a **native C program built with MinGW GCC**, not Java: its `libgcj_s.dll` and
`_Jv_RegisterClasses` strings are GCC startup boilerplate found in nearly every MinGW exe. The logic is
native x86.

### What the tool does, from its disassembly

- It is a **GUI only**. It ignores the command line entirely — passing a file list as an argument
  does nothing but open the window and write an empty log. The workflow is *File → Open…* and then
  selecting a `*modelbins.txt` file list. Text on the window: `NEEDS filelist *modelbins.txt`,
  `editbox: start addr of SM header for`, `SlyCooper or FIs start for kimesh`,
  `[log file MakeH2O_log.txt in project dir]`, and a format dropdown defaulting to `ForzaH`.
- It does **not** write H2O files. It logs Wavefront OBJ text, which the user renames to `.obj`.
- For each entry in the list it splits the directory off the path with `strrchr(line, '\\')`,
  `SetCurrentDirectoryA`s into it, slurps the whole file into a buffer, and then applies its format
  gate: the first byte must be `'b'` (i.e. `burG`), otherwise
  `This doesn't seem to be a ForzaHor'...' file!`.
- Geometry is then located by **repeated byte-pattern searches**, not by parsing the container's
  chunk table. It calls `FindBytes(buffer, start, len, pattern, patlen)` in successive passes:
  - vertex blocks — pattern `08 00 00 00 01 00 0d 00`; after a hit it reads a u32 count located
    **eight bytes before** the pattern, then walks `count` × **8-byte** vertices;
  - face-index blocks — pattern `04 00 00 00 01 00 2a 00`, with the count read the same way;
  - a third variant of each for a different sub-format.
- Alongside each hit it reads a per-part **scale** (three floats used as-is) and a **position
  offset** (three floats multiplied by 32768.0) from fixed displacements after the hit.
- Vertex output is `(raw_i16 * scale + pos_off) * (1/256)` — the row is sign-corrected from int16
  first. UV output is `raw_u16 * (1/65536)`, with a per-block stride chosen by a small lookup.
- UVs are located by a heuristic scan for the byte `0x25` (`'%'`) guarded by its neighbours
  (`buf[-1]==0`, `buf[-2]!=0 && buf[-2]<0x0b`, `buf[-3]==0`, `buf[-4]!=0`, offset `>0x300`,
  `3 < buf[-4] < 0x28`), with the UV stride derived from that byte.
- OBJ emission writes `g <basename-without-extension>_<n>` group lines and
  `f %d/%d %d/%d %d/%d` faces, **reusing the vertex index for the UV index**. The log's last line is
  `# Summe der verts= %d`.
- A separate routine is the generic non-Forza path (scan for `00 01 02 15`, walk back and read two
  matching u32 counts, then a submesh count, then a table of per-submesh face-index counts
  terminated by the value `1`), shared with its siblings for Wipeout, Star Wars, MLP, Sly Cooper and
  others.

### Why the `_f` build finds nothing in two FH3 tyre files

The patterns are frozen to one exact 2017 build. Re-implementing the tool's own scan loop in Python
and running it over real FH3 tyre modelbins finds **zero** matches for both the vertex pattern and
the face-index pattern, at which point the tool's own consistency check
(`error uv sum !=  vCnt: %d!=%d`) fires.

That is the mechanical reason behind the author's own list of parts with **no scale found**
(`hood_a`, `trunk_a`, `wingMirrorL_a`, `headlightLBulbs_a`, `CAD_ATSV_16_wheelLF`, …) and the
`UVB28` UV complaints: when the pattern hit is a coincidence, the scale/pos-offset record it reads
next is garbage or absent.

The author's own documented issues (relayed from the readme, not re-verified here) agree with this:
moveable parts such as hoods, doors and wipers "seem to be bound to the skeleton" and need their
relative positions from the skeletal hierarchy; the brute-force face grouping attaches some wrong
LOD parts to the body; the wheel has to be duplicated and scaled by hand; most `UVB28` maps are
missing, wrong or too small.

### UV channels, from the author's table

The tool logs a size line per mesh, e.g.

```
# uv-sizes bumperF_a.modelbin, 20 24 24 28 28 32 32 36 36
```

and the author published this uvb-size → channel-offset table:

```
uvbs  12 16 20 24 28 32 36
chan1  4  4  4  4  4  4  4
chan2  8  8  8  8  8  8  8
chan3  0  0 12 12 12 12 12
chan4  0  0  0 16 16 16 16
chan5  0  0  0  0 20 20 20
```

A zero means that channel is absent. Wavefront OBJ carries only one UV channel, so selecting a later
channel forces a `vt 0.0 0.0` zero-fill for the earlier ones — which is why imported meshes can look
as if their UVs are "wrong" when they are merely offset. The author also relays that 32-byte blocks
have **two** layouts, so the same settings give UV2 on some meshes and UV1 on others.

### Modern alternatives

- `noidex0/fh6-model-tools` — a Python-stdlib spec plus OBJ/GLB/DDS converter validated against 638
  cars. This is where the stride-40 layout, the axes and the bbox position decode above come from; the
  container table follows Nenkai's `Bundle.cs`. It targets the FH6-era files but the container lineage
  is the same family.
- `Nenkai/ForzaTools` — C# classes per blob type (`ModelBlob`, `MeshBlob`, `VertexBufferBlob`,
  `VertexLayoutBlob`, `IndexBufferBlob`, `MaterialBlob`, `MorphBlob`, `SkeletonBlob`, …).
- The archive layer has an open text route instead of a DLL: aluigi's QuickBMS script
  `forza_horizon.bms` (its header says Forza Horizon 2) walks the zip central directory and maps its
  compression method — `0` stored, `8` deflate, `13`/`15`/`21` XMem/LZX — onto QuickBMS's own
  `XMemDecompress` codec, so it decompresses those packages with no proprietary binary at all.
- FH4, FH5 and FH6 modelbins use the same `burG` container with later version bytes (`Grub` is just that
  magic read as a little-endian u32); the `Nenkai/ForzaTools` blob classes are the starting point there.
  Those later versions are not covered here.

## Gotchas

1. **The tool appears to do nothing and the log stays empty.** MakeH2O ignores command-line
   arguments; there is no CLI mode. Open it, use *File → Open…*, and pick the `*modelbins.txt`.
2. **`This doesn't seem to be a ForzaHor'...' file!`** The file's first byte is not `'b'`. The tool
   only accepts `burG` containers; a `.carbin` file (the older FM3/FM4-era format) is refused outright.
3. **`error uv sum !=  vCnt`, or an empty OBJ with no groups.** Its hardcoded block patterns did not
   match this build — the heuristic is frozen to the build it was written for. Reach for a
   burG-aware parser instead of retrying.
4. **A part lands at the origin, or in the wrong place, and the log shows ` > no Scale!`.**
   MakeH2O needs the inline scale/pos-offset record it expects after a pattern hit; a false-positive
   hit leaves it with nothing. Decode positions against the per-LOD bbox from the `Name` metadata
   instead.
5. **Doors, hood and wipers are misplaced.** The author's own FAQ: skeleton-bound parts need their
   relative positions read from the skeletal hierarchy, which the tool does not do.
6. **The log explodes to hundreds of MB and the exe freezes.** One bad modelbin in the list is
   usually the cause; the author's advice is to delete the `*__SLOD.modelbin` lines and to keep
   separate file lists per `\Exterior` subfolder so a run cannot go all-in-one.
7. **UV channels look shifted or blank.** OBJ has one UV channel; use the uvb-size table above to
   pick the channel offset, and expect the first selected channel to be zero-filled.

## Seen in

- `burG`-format `.modelbin` files from Forza Horizon 3 (and the FM6/FH2-era lineage). Inspected a
  53-file sample tree of FH3 car models, plus two tyre files in detail. That tree was exported from the
  note author's own Windows install back when the game first became moddable, before switching to Linux;
  the game is owned on the Microsoft Store, was delisted in 2020, and cannot be re-exported on Linux now.
  No game files are shipped with this note.
- `Make_H2O-ForzaHor*.exe` builds (2017) from the XeNTaX Forza threads — the older `.carbin`
  resource-extraction thread and the later Forza Horizon 5 `.modelbin` thread — along with the
  author's `readmeForzaH.txt`, his example `CAD_ATSV_16` file list, and the shipped
  `dir_modelbin.cmd` helper (`dir /s /b *.modelbin > modelbins.txt`).
- The tool binary in this workspace is an early `_f` build; a later `-jm9` build exists in the same
  public archive and was not tested here.
