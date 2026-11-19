"""`um win launch <exe>` must start the game in the exe's own folder (games open their data files relative to
the working directory; Tomb Raider: Legend dies with "Failed to open BIGFILE.000" otherwise)."""
from um import win


def test_launch_exe_starts_in_its_own_folder(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(win.subprocess, "run", fake_run)
    monkeypatch.setattr(win, "is_wsl", lambda: False)
    monkeypatch.setattr(win, "to_win", lambda p: p)
    win.launch(r"A:\Games\Foo\foo.exe", ["-windowed"])
    assert len(calls) == 1
    cmd = calls[0]
    i = cmd.index("/D")
    assert cmd[i + 1] == r"A:\Games\Foo"
    assert cmd[i + 2:] == [r"A:\Games\Foo\foo.exe", "-windowed"]
    assert cmd[:4] == ["cmd", "/c", "start", ""]


def test_launch_steam_url_has_no_directory(monkeypatch):
    calls = []
    monkeypatch.setattr(win.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(win, "is_wsl", lambda: False)
    win.launch("105600", [], steam=True)
    assert calls and "/D" not in calls[0]
    assert calls[0][-1].startswith("steam://")
