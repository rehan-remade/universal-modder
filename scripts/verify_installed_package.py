#!/usr/bin/env python3
"""Verify an installed distribution, its CLI surface, and packaged resource bytes."""
from __future__ import annotations

import hashlib
import importlib.resources
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import um

repo = Path.cwd().resolve()
loaded = Path(um.__file__).resolve()
if loaded.is_relative_to(repo):
    raise SystemExit(f"loaded source checkout instead of installed distribution: {loaded}")
root = importlib.resources.files("um")
required = [
    "fonts/SpaceGrotesk-Bold.ttf",
    "fonts/SpaceGrotesk-Medium.ttf",
    "fonts/JetBrainsMono-Bold.ttf",
    "fonts/OFL-SpaceGrotesk.txt",
    "fonts/OFL-JetBrainsMono.txt",
    "ps1/WinDrive.ps1",
    "ps1/ProcLoopback.ps1",
    "blender/render_sprites.py",
]
missing = [name for name in required if not root.joinpath(name).is_file()]
if missing:
    raise SystemExit("installed package is missing: " + ", ".join(missing))
resource_hashes = {}
for name in required:
    installed = root.joinpath(name).read_bytes()
    source = (repo / "um" / name).read_bytes()
    if installed != source:
        raise SystemExit(f"installed resource differs from source: {name}")
    resource_hashes[name] = hashlib.sha256(installed).hexdigest()
with tempfile.TemporaryDirectory(prefix="um-installed-cli-") as td:
    commands = [[sys.executable, "-m", "um", "--version"], [sys.executable, "-m", "um", "--help"]]
    commands += [[sys.executable, "-m", "um", group, "--help"] for group in
                 ("scan", "fal", "comfy", "sprite", "render3d", "video", "win", "backup", "publish", "kb")]
    for command in commands:
        subprocess.run(command, cwd=td, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=30)
print(json.dumps({"version": um.__version__, "module": str(loaded), "resources": resource_hashes}, indent=2, sort_keys=True))
