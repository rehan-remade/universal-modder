# Pacmania 1.1 Super Mario Mod

This directory contains the scripts used to mod the DOS game **Pacmania 1.1** (by Gregg Seelhoff) to replace the main Pacman character with a custom Super Mario sprite!

## How it works

The game stores its graphics in a raw, uncompressed 2bpp CGA mode 4 memory dump embedded inside `PMAN.EXE` (starting at offset 36082). 

1. **`extract_cga.py`**: Extracts the CGA sprite sheet from `PMAN.EXE` and saves it as a BMP image. This allowed us to visualize the exact coordinates of the Pacman sprites.
2. **`patch_mario_cga.py`**: The main modding script. It searches specific rows of the embedded CGA sprite sheet (Y=176 and Y=192) for the 16x16 Pacman sprites, and injects a 4-color Super Mario sprite directly into the executable using exact CGA bitwise math.
3. **`launch_dosbox.bat`**: A helper script to launch the modded game inside DOSBox-X.

## Execution

To apply the mod to your own copy of Pacmania 1.1:
1. Place a pristine copy of `PMAN.EXE` in this folder.
2. Run `python patch_mario_cga.py`.
3. The script will directly patch `PMAN.EXE`.
4. Run the game in DOSBox to play as Mario!

*(Note: The game executable is not included here for copyright reasons.)*
