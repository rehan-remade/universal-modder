"""Tools print UTF-8; the locale codec must never decide whether um works.

On a Chinese Windows `locale.getpreferredencoding()` is cp936, on a Western one cp1252, while ffmpeg prints
a path in UTF-8, and so does PowerShell 5.1 when its console is at code page 65001 or the script starts with
`um.common.PS_UTF8`. A bare `text=True` therefore dies with `UnicodeDecodeError` in subprocess's reader
thread on the first CJK window title, save folder or game path - `um win ps` did, on a machine with 中文
window titles. `um.common.text_utf8()` is the way to read a tool's output (`text_console()` for taskkill and
reg, which print in the console code page); `test_no_subprocess_call_decodes_with_the_locale_codec` keeps
it that way.
"""
from __future__ import annotations

import ast
import locale
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from um import video
from um.common import run, text_console, text_utf8

UM = Path(__file__).resolve().parent.parent / "um"
SUBPROCESS_CALLS = {"run", "Popen", "check_output", "call", "check_call"}
CJK = "中文 测试"
# 0xaf/0xad are the bytes cp936 chokes on in a real Chinese window title ('中' is e4 b8 ad in UTF-8).
GARBAGE = b"\xaf\xad\xff"


def _child(writes: str) -> list[str]:
    """A child python that puts `writes` on stdout as raw bytes, whatever its own stdio codec is."""
    return [sys.executable, "-c", f"import sys; sys.stdout.buffer.write({writes})"]


def test_text_utf8_pins_the_codec():
    kw = text_utf8()
    assert kw == dict(text=True, encoding="utf-8", errors="replace")
    assert text_utf8(timeout=5)["timeout"] == 5
    # taskkill and reg print in the console code page: keep the locale codec there, but never raise
    assert text_console() == dict(text=True, encoding=locale.getpreferredencoding(False), errors="replace")


def test_tool_output_is_read_as_utf8():
    r = run(_child(f"{CJK!r}.encode('utf-8')"), env=dict(os.environ, PYTHONIOENCODING="cp1252"))
    assert r.stdout == CJK


def test_undecodable_bytes_never_raise():
    """A wrong guess has to cost one replacement character, not a traceback in a reader thread."""
    r = run(_child(f"{GARBAGE!r}"))
    assert "\ufffd" in r.stdout


def test_no_subprocess_call_decodes_with_the_locale_codec():
    bad = []
    for path in sorted(UM.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            f = node.func
            if not (f.attr in SUBPROCESS_CALLS and isinstance(f.value, ast.Name) and f.value.id == "subprocess"):
                continue
            kw = {k.arg for k in node.keywords if k.arg}
            if "text" in kw and "encoding" not in kw:
                bad.append(f"{path.relative_to(UM.parent)}:{node.lineno}")
    assert not bad, "read tool output through um.common.text_utf8() instead: " + ", ".join(bad)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_ffmpeg_reads_a_cjk_path(tmp_path):
    """ffmpeg echoes the path it was given; before text_utf8() this raised on Windows, not on Linux CI."""
    clip = tmp_path / f"{CJK}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=128x96:d=1:r=10", str(clip)],
                   check=True, capture_output=True)
    assert video.probe(clip)["duration"] > 0
