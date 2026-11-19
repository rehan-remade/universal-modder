# First slice — run checklist

The guest side is proven (see MODLOG session 5). This is the host half: Outer Wilds reads the guest's
frame out of shared memory and paints it on a surface in the world, depth-tested so OW terrain in front
of it occludes it.

## Before launching

1. **Clear any stale Steam launch.** A hung `wineboot.exe --init` chain under AppId 753640 holds the
   prefix and blocks a new launch. Stop Outer Wilds in Steam until nothing is left:
   `ps -eo pid,etimes,args | grep -E '753640|iscriptevaluator' | grep -v grep`
2. **Start the guest** (it must be up *before* the host connects, or the host just retries):
   ```
   cd examples/minecraft-outerwilds-passthrough
   python3 tools/install-guest.py --list          # jar must say "current"
   nohup python3 tools/launch-mc.py --width 1280 --height 720 --log /tmp/opencode/mc-run.log &
   ```
   Wait for the profile (~2.5 min at 149 mods), then confirm:
   ```
   tools/probe-guest.py hello
   ```
   Expect `{"t":"hello","v":1,"shm":"blockcraft-frame","pid":<n>}`.
3. **Launch Outer Wilds yourself** (Steam). Then load into a save.

> **The passthrough starts on the SolarSystem scene, not the title screen.** `BlockCraftMod.Start`
> only calls `StartPassthrough()` from the `OWScene.SolarSystem` branch of `OnCompleteSceneLoad`. Reaching
> the title screen proves the mod loaded; loading a save proves the bridge works.

## Host log lines, in order (OWML log)

```
[BlockCraft - Minecraft inside Outer Wilds]: Success: BlockCraft loaded
[BlockCraft - Minecraft inside Outer Wilds]: Message: block tool added to the loop
[BlockCraft - Minecraft inside Outer Wilds]: Success: passthrough up: link on 127.0.0.1:25599, compositor, bridge, dev on
[BlockCraft - Minecraft inside Outer Wilds]: Message: guest hello: shm blockcraft-frame, pid <n>     <- guest connected
[BlockCraft - Minecraft inside Outer Wilds]: Message: frames <n>, misses <n>, guest frame <n>, ...   <- frames arriving
```

Only the first line appears on the title screen. Lines 3–5 need a loaded SolarSystem scene.

Where it is:
`ls -t ~/.local/share/OuterWildsModManager/OWML/Logs/*.txt | head -1`

## Drive it

```
tools/slice1.sh waitfor solarsystem   # blocks until the SolarSystem scene is up
tools/slice1.sh dump                  # host pose, guest status, link + reader counters
tools/slice1.sh place 6               # put the screen 6 m in front of the camera
tools/slice1.sh shot slice1           # Spectacle screenshot into the mod's shots/
```

`dump` is the single most useful command. What it prints, and what each part tells us:

| line | tells us |
|---|---|
| `host: ...` | the bridge has a camera pose to send |
| `guest: ...` | the compositor is alive |
| `screen pos ... size ...` | where the quad is and how big |
| `link: connected <bool> ... recv <n> shm ... pid ...` | the WebSocket reached the guest |
| `reader: reads <n> torn <n> missed <n> publish <n> slot <n>` | **the host is reading the guest's frames** |

Interpretation:
- `connected False` → the guest is not running, or not yet past its title screen.
- `connected True` but `reads 0` → link is up, host can't map the buffer (check `shm` name).
- `reads` climbing but `publish 0` → mismatch on the buffer (the guest is writing, the host is looking
  at a different object).
- `torn` climbing → a real seqlock bug; the guest side measured 0 torn over 330 frames, so this would
  point at the C# reader.
- `reads` climbing, `frames <n>` climbing in the log, and the picture visible → **first slice done**.

## If something is wrong

- **No `passthrough up` line after loading a save** → the mod's `Start` didn't run, or the scene event
  never fired. Check the mod is still installed: `python3 tools/install-mod.py` (running
  `OWML.Launcher.exe` empties `Mods/`).
- **`connected False` with the guest up** → port 25599. `ss -ltn | grep 25599` on the Linux side.
- **Host never sees `guest hello`** → the host connected *before* the guest and gave up, or the port is
  woven at a different value. Restart the host (`tools/slice1.sh` cannot do this; reload the save).
- **Raw WebSocket probes throwing in the guest log** → harmless; `HostLink.onOpen`/`onError` are now
  guarded, so a probe logs one line and the link survives.

## What "done" looks like for slice 1

A screenshot from Outer Wilds showing the Minecraft picture on a surface, with OW terrain correctly
occluding it — i.e. the depth test works and it is not just pasted over the screen.
