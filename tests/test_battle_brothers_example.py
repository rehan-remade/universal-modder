"""Build check for examples/battle-brothers-training, plus its pure-logic test when a Squirrel
interpreter is available (set SQ=<path to sq>, or have `sq` on PATH)."""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

EX = Path(__file__).resolve().parents[1] / "examples" / "battle-brothers-training"


def test_build_layout(tmp_path):
    out = subprocess.run([sys.executable, str(EX / "build.py")], capture_output=True, text=True, check=True)
    zpath = Path(out.stdout.strip().splitlines()[0])
    names = zipfile.ZipFile(zpath).namelist()
    assert "scripts/!mods_preload/mod_training_grounds.nut" in names
    assert "training_grounds/logic.nut" in names
    assert not any(n.endswith((".cnut", ".dat")) for n in names)


def test_logic_under_squirrel():
    sq = os.environ.get("SQ") or shutil.which("sq")
    if not sq:
        pytest.skip("no Squirrel interpreter")
    r = subprocess.run([sq, "tests/test_logic.nut"], capture_output=True, text=True, cwd=EX)
    assert "OK" in r.stdout, r.stdout + r.stderr
