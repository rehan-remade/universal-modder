# Portal gun for Outer Wilds

Portal 2's portal gun in Outer Wilds, from the first second of every loop, in every save, with or without the
suit. Portals show the other side, keep your momentum, stick to whatever they hit (planets, islands, the
ship) and vanish when the loop resets. The player, the scout and the ship can go through.

The model, textures and sounds come from **your own Portal 2 install**: a converter reads them on your machine.
Nothing from Valve or Mobius ships with this mod.

## Controls

| Input | Action |
|---|---|
| `5` | take out / put away the portal gun (configurable) |
| Left mouse / gamepad RB | blue portal |
| Right mouse / gamepad LB | orange portal |
| Mouse wheel (gun out) | portal size: normal 1.6 x 2.6 m, large 3.2 x 5.2 m, ship 8 x 13 m |

Taking out a game tool (signalscope, scout launcher, translator) puts the gun away. Sitting at a console, talking
to someone or entering the dream world does too. While the gun is out, right mouse doesn't launch the scout and
left mouse doesn't lock on.

## Install

Needs: Outer Wilds (Steam/Epic/Xbox), Portal 2 (Steam), the [Outer Wilds Mod Manager](https://outerwildsmods.com/)
with OWML 2.16+, Python 3.10+ with `pillow` and `numpy`, and the .NET SDK (6+) to build.

1. Convert the gun from Portal 2 (writes `%LOCALAPPDATA%\OWPortalGun`, about 8 MB, under a second):
   ```
   pip install pillow numpy
   python tools/convert.py                          # finds Steam's Portal 2 by itself
   python tools/convert.py --portal2 "D:\Games\Portal 2"   # or point at it
   ```
2. Build the mod straight into OWML's mods folder (`%APPDATA%\OuterWildsModManager\OWML\Mods\charlystereo.PortalGun`):
   ```
   dotnet build src -c Release
   ```
3. Start the game from the Mod Manager. The OWML log says `Portal Gun loaded` and, in game,
   `portal gun added to the loop`.

Settings (Mod Manager → Portal Gun → settings): equip key, volume, and the converted assets folder.

## How it works

- **Viewmodel.** `tools/convert.py` reads `portal2/pak01_dir.vpk` (VPK v2), parses `models/weapons/v_portalgun`
  (Source MDL v49 + VVD + VTX), decodes its compressed animations to per-frame bone poses, converts axes to Unity,
  and writes a small binary (`portalgun.owpg`) plus PNG textures and WAV sounds. In game it becomes a skinned mesh on
  the player camera drawn with the game's own viewmodel shaders (cloned from the signalscope), so it never pokes into
  walls. The Portal 2 skins switch blue/orange with the last portal fired.
- **Portals.** Each portal is a stencil mask (the ellipse plus a short tube behind it) drawn with `UI/Default`; a
  second camera renders the view from behind the other portal with an oblique near plane, restricted to the
  portal's screen rectangle, and a full-screen quad paints that picture where the stencil is set. The game's skybox
  command buffer is copied onto that camera so stars show through.
- **Travel.** Bodies near a portal are tracked each physics step; crossing the plane inside the ellipse warps them
  with `OWRigidbody.WarpToPositionRotation` (which updates sectors and the floating origin) and maps their velocity
  relative to the bodies the portals ride. The player comes out upright for the exit's gravity, looking where the
  mapped view looks. While something is in the hole its collisions with the wall are ignored, the player's ground
  check ignores the hole, and the scout (which anchors with its own raycast) is sent through instead of sticking.
- **Placement.** Shots are hitscan with a visible bolt, go through existing portals, and fit the ellipse to rough
  terrain (an averaged plane, up to about a metre of unevenness, nudged like Portal 2 when it doesn't fit).

## Developer test bridge

Create an empty `dev.enabled` file in the mod folder and the mod reads commands from `dev_commands.txt` and logs to
`dev_log.txt` (screenshots in `shots/`). It can start a lab profile from the title screen without input, wake up,
equip, fire, aim, walk, drop the ship over a portal, launch the scout, trace bodies and reload the loop. See
`src/DevBridge.cs` and `MODLOG.md` for the sequences used to verify this mod. Delete `dev.enabled` to turn it off.

## Credits

- Portal gun model, textures and sounds: Valve (Portal 2), converted from your own copy, never redistributed.
- Outer Wilds: Mobius Digital. OWML and the Mod Manager: the Outer Wilds modding community.
- Built with an AI coding agent (Claude Code) working in the universal-modder toolkit.
