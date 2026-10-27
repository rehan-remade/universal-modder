"""`um win shot/record` put --title/--exe into an ffmpeg filtergraph for gfxcapture. A ':' in a window title or an
exe path split the option there ("Halo: The Master Chief Collection" became window_title=Halo), and a '\\' was
read as an escape (issue #370)."""
import shutil
import subprocess

import pytest

from um import win

VALUES = ["Halo: The Master Chief Collection", "Age of Empires II: DE", "Star Wars Jedi: Survivor",
          r"(?i)^tom clancy's: \w+, [beta]; v1\.2$", r"C:\Games\foo\bar.exe"]


def test_source_escapes_title_and_exe_for_the_filtergraph():
    assert win._source(title="Halo: The Master Chief Collection").startswith(
        r"gfxcapture=window_title=Halo\\: The Master Chief Collection:capture_cursor=0:")
    # gfxcapture matches window_exe against the exe's file name, so a full path is cut to it
    assert win._source(exe=r"C:\Games\Halo MCC\mcclauncher.exe").startswith("gfxcapture=window_exe=mcclauncher.exe:")
    assert win._source(exe="/mnt/c/Games/foo").startswith("gfxcapture=window_exe=foo.exe:")
    # a regex keeps its backslash, escaped once per level
    assert win._source(exe=r"Game\.exe").startswith(r"gfxcapture=window_exe=Game\\\\.exe:")
    assert win._source(hwnd=123456).startswith("gfxcapture=hwnd=123456:")
    # the example in ffmpeg-filters, "Notes on filtergraph escaping"
    assert win._ff_value("this is a 'string': may contain one, or more, special characters") == \
        r"this is a \\\'string\\\'\\: may contain one\, or more\, special characters"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
@pytest.mark.parametrize("value", VALUES)
def test_escaped_value_reaches_the_filter_intact(value):
    # the two parsers gfxcapture's options go through, the graph's and then the filter's option list, on a
    # filter every ffmpeg build has: metadata stores the value and prints it back
    graph = f"color=s=16x16:d=0.04,metadata=mode=add:key=um:value={win._ff_value(value)},metadata=mode=print"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", graph, "-frames:v", "1", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    assert [ln.split("] um=", 1)[1] for ln in r.stderr.splitlines() if "] um=" in ln] == [value]
