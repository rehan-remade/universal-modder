#!/usr/bin/env python3
"""Verify the installed wheel, not the source checkout, and its runtime resources."""
from __future__ import annotations

import importlib.resources
import json
from pathlib import Path

import um

repo = Path.cwd().resolve()
loaded = Path(um.__file__).resolve()
if loaded.is_relative_to(repo):
    raise SystemExit(f"loaded source checkout instead of installed wheel: {loaded}")
root = importlib.resources.files("um")
required = [
    "fonts/SpaceGrotesk-Bold.ttf",
    "fonts/JetBrainsMono-Bold.ttf",
    "ps1/WinDrive.ps1",
    "ps1/ProcLoopback.ps1",
    "blender/render_sprites.py",
]
missing = [name for name in required if not root.joinpath(name).is_file()]
if missing:
    raise SystemExit("installed package is missing: " + ", ".join(missing))
print(json.dumps({"version": um.__version__, "module": str(loaded), "resources": required}, indent=2))
