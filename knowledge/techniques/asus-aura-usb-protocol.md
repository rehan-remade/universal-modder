---
kind: technique
title: "ASUS AURA USB protocol: opcodes, zone table and the unresolved TUF X570 4-pin header"
tags: [asus, aura, openrgb, usb-hid, rgb, tuf-x570, reverse-engineering, opcodes]
date: 2026-10-05
agents: ["OpenCode (DeepSeek V4.1 Flash)"]
humans: ["Selene0623"]
links:
  - "https://openrgb-wiki.readthedocs.io/en/latest/asus/ASUS-Aura-USB/"
  - "https://blog.inlart.com/post/openrgb-asus-x570/"
  - "https://github.com/liquidctl/liquidctl/blob/main/docs/asus-aura-led-guide.md"
---

# ASUS AURA USB protocol: opcodes, zone table and the unresolved TUF X570 4-pin header

> The ASUS AURA USB controller is a simple 65-byte HID device driven by four opcode groups
> (SetEffect / SetEffectColor / Commit / Direct). Reverse-engineering the mainboard HAL
> (`Aac3572MbHal_x86.exe`) yields the full opcode set and zone table. Our own attempt to
> drive the TUF X570's two **4-pin 12V RGB headers** with these packets was **unresolved** —
> the packets executed but the header LEDs stayed white — while OpenRGB documents X570 boards
> driving the 12V headers *from this same controller*, so it is not a hardware limit.

## When to use it

Writing or debugging an AURA USB driver (e.g. an OpenRGB fork), or deciding whether a board's RGB
header is reachable over the AURA HID interface.

Game relevance: many games drive motherboard/case RGB through vendor SDKs, so this protocol is the
low layer under in-game lighting effects. AURA's per-zone effect/colour/commit opcodes are the same
shape as MSI Mystic Light (MSI's `MysticLight_SDK`) and Razer Chroma — a game or mod that reacts to
in-game events (health, engine RPM, alerts) ends up issuing exactly these SetEffect / SetEffectColor
/ Commit writes. If a mod needs to reproduce or intercept such effects, this is the transport to
understand.

## How

### Raw materials and extraction

The AURA installers are self-extracting bundles with embedded CABs. The useful binaries:

- **Mainboard HAL:** `Aac3572MbHal_x86.exe` (796 KB) — the COM server that actually writes to the
  HID device via `UsbHidControl::DoWrite`.
- **Type library:** `Aac3572MbHal.tlb` — COM interface signatures.
- **SDK:** `AuraSdk_x86.dll` — a pure COM wrapper over the HAL.

SFX bundles carry CABs at fixed offsets (`0x70E00` small, `0x8D040` mainboard / `0x8CF70` service);
`dd` the CAB out, `7z x` it, then `7z x` the MSI inside to get the PE/TLB.

### COM API surface

Library `Aac3572MbHalLib`. Base interface `IAsusAacLedDeviceHal`, plus `...Hal2`, `IAacMotherboard`
(+`2`), `IAacLedDeviceOpt`, `...VariedLedCount`, `...Temperature`, `...Reset`, `IAacLedDevice2`,
`IAacLedDeviceOpt2`, `IAacMotherboardFunction`.

Key methods: `GetCapability`, **`SetEffect(effectId, colors[], numberOfColors)`**,
`GetEffect`, `Enumerate`, `SetStandbyEffect`, `SetSpeed`, `SetDirection`, `SetEnabled`,
`GetBiosOnOff`, `GetManualLedCount`, `GetTemperature` (1/10 °C), `Reset`, `SetFunction`,
`Synchronize(milliseconds)`. **Parameter order varies** between `(in,in,out)` and `(out,in,in)` —
always read the TLB.

### AURA opcodes (all 65-byte HID packets)

| Opcode | Purpose |
|---|---|
| `EC 35` | SetEffect "open" (device context) |
| `EC 36` | SetEffectColor (LED mask + 52 B colour data) |
| `EC 3F 55` | Commit (apply pending) |
| `EC 40` | Direct mode (per-LED write) |
| `EC 82` | GetFirmwareVersion |
| `EC B0` | GetConfigTable |
| `EC 32` | Read paths |
| `EC 52 53 00 01` | SetGen1 (brief flash on detection) |

### SetEffectColor packet (`EC 36`)

| Offset | Size | Content |
|---|---|---|
| 0 | 1 | `0xEC` |
| 1 | 1 | `0x36` |
| 2 | 1 | mask_hi |
| 3 | 1 | mask_lo |
| 4 | 1 | channel (0 or 1) |
| 5–56 | 52 | RGB colour data |
| 57–64 | 8 | zero padding |

### SetEffect + Commit flow

1. Build a 16-bit LED mask: for each LED, `mask |= (1 << channel_id) & 0xffff`.
2. Send `EC 36` SetEffectColor with the mask and colours.
3. Send `EC 35` SetEffect open: `EC 35 00 00 10 02 00 00 ...`.
4. Send `EC 3F 55` Commit.

All I/O is serialized under the global mutex `Global\asusaurausb`.

### Zone table (HAL `FUN_0042bd50`)

Maps a case id to a zone name, returning `(name_ptr, length)`: `0x06` RGB strip-1, `0x07` RGB strip-2,
`0x11` RGB HEADER, **`0x13` `RGB_HEADER_1_2`** (the TUF X570 pair), `0x14` `RGB_HEADER_3_4`,
`0x1E` IO+BACK LED ZONE, `0x1F` NB+BACK LED ZONE, `0x20`+ per-board zones.

### HID write primitive

`UsbHidControl::DoWrite` (`FUN_00450560`) is a thin `WriteFile` wrapper — 65-byte buffer straight to
`kernel32!WriteFile`, handle at `this[0x1c]`. `DoRead` (`FUN_00450ba0`) is the `ReadFile` companion.
No per-zone logic lives here.

### TUF X570 channel mapping (hypothesis)

Within the mainboard device: channels 0–2 are the three onboard LEDs (`IO+BACK LED ZONE`), channels
3–4 are the two 4-pin headers (`RGB_HEADER_1_2`); the 12 ARGB LEDs are a separate device/zone.
Masks: onboard-only `0x07`, headers-only `0x18`, all mainboard `0x1F`.

### Ghidra workflow

```
/opt/ghidra/support/analyzeHeadless /tmp/ghidra_proj aura_hal \
  -process Aac3572MbHal_x86.exe -noanalysis \
  -scriptPath .../ghidra_scripts -postScript find_aura_strings
```

Do not re-analyze; run postScripts against the existing project.

## Gotchas

1. **The 4-pin headers did not respond to AURA HID — unresolved, not a hardware limit.**
   **Symptom:** every packet format (Direct `EC 40`, SetEffect `EC 35`, SetEffectColor `EC 36`,
   Commit `EC 3F 55`) writes successfully but the header LEDs stay white; the same packets drive
   onboard and ARGB zones fine. **Cause:** not established here. OpenRGB documents X570 boards
   driving the 12V headers *from this controller*, so the headers are reachable over AURA HID in
   general; our TUF X570 result is an unresolved per-board/address-mapping problem. A different
   bus (the **ENE eIO chip on `/dev/i2c-8`**, same SMBus as DRAM at `0x70–0x73`) remains a
   candidate. **Fix:** check `i2cdetect -l` / `i2cdetect -y 8` and re-check the channel/zone
   mapping; do not conclude the headers are off-limits on all boards.
2. **`UsbHidControlWithPatch` is dead code.** **Symptom:** a promising "patched HID path" class.
   **Cause:** it has RTTI but zero code references — empty vtable, no constructor. **Fix:** ignore it;
   there is no hidden patched path.
3. **Generic ASUS DLLs carry no AURA strings.** **Symptom:** you chase `AsIO.dll`, `ASUS_WMI.dll`,
   `ATKEX.dll`. **Cause:** they are generic platform libraries. **Fix:** the protocol lives in the
   mainboard HAL, not these.
4. **Parameter order is inconsistent in the COM API.** **Symptom:** a call succeeds but returns
   garbage. **Cause:** some methods are `(in,in,out)`, others `(out,in,in)`. **Fix:** read the TLB per
   method.
5. **A locked mutex serializes everything.** **Symptom:** writes appear to hang. **Cause:** all I/O is
   under `Global\asusaurausb`. **Fix:** don't hold it across UI waits; keep transactions short.

## Seen in

- An ASUS AURA reverse-engineering workbench (unpublished), target TUF X570, device `0B05:18F3`
- The OpenRGB AURA driver fork (a local OpenRGB checkout) — implements Direct-mode emulation and the LED-mask fix
  from this protocol knowledge
