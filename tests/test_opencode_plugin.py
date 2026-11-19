"""The OpenCode plugin must know every CLI group, and must not invent one.

`plugins/opencode/index.ts` names the groups in its tool description and answers a typo from that
list, so a group added to `um/cli.py` without touching the plugin would leave the description stale.
This test is the sync check (it is also the "test with tool changes" CONTRIBUTING asks for).
"""
from __future__ import annotations

import re
from pathlib import Path

from um.cli import GROUPS

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "opencode" / "index.ts"

# rows of the `GROUPS` array: { name: "scan", blurb: "..." },
_ROW = re.compile(r'\{\s*name:\s*"([a-z0-9]+)"')


def plugin_groups() -> list[str]:
    source = PLUGIN.read_text(encoding="utf-8")
    start = source.index("const GROUPS = [")
    end = source.index("\n]", start)  # the array's closing line, so a "]" inside a blurb can't cut it short
    return _ROW.findall(source[start:end])


def test_plugin_lists_every_cli_group():
    assert plugin_groups() == GROUPS


def test_plugin_file_exists():
    assert PLUGIN.is_file()


def test_plugin_does_not_use_config_substitution():
    # OpenCode expands {env:VAR} only in config files; a server a plugin sets would get the literal text.
    assert "Bearer {env:" not in PLUGIN.read_text(encoding="utf-8")
