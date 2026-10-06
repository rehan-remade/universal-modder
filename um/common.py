"""Small helpers shared by the subcommands: platform checks, WSL path mapping, subprocess, output."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def is_windows() -> bool:
    return os.name == "nt"


def is_mac() -> bool:
    return sys.platform == "darwin"


def is_wsl() -> bool:
    if sys.platform != "linux":
        return False
    return "microsoft" in platform.release().lower() or os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop")


def ps_exe() -> str:
    """Windows PowerShell. Falls back to its full path: an agent's PATH often lacks System32\\WindowsPowerShell\\v1.0."""
    name = "powershell.exe" if is_wsl() else "powershell"
    found = shutil.which(name)
    if found:
        return found
    if is_wsl():
        full = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    else:
        full = os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return full if os.path.exists(full) else name


def to_win(path: str | Path) -> str:
    """/mnt/c/Games/x -> C:\\Games\\x (WSL); paths that are already Windows paths pass through."""
    p = str(path)
    if len(p) > 1 and p[1] == ":":
        return p
    if p.startswith("/mnt/") and len(p) > 6 and p[6] in "/" and p[5].isalpha():
        return p[5].upper() + ":\\" + p[7:].replace("/", "\\")
    if p.startswith("/mnt/") and len(p) == 6:
        return p[5].upper() + ":\\"
    if is_wsl() and shutil.which("wslpath"):
        return subprocess.run(["wslpath", "-w", p], capture_output=True, text=True).stdout.strip()
    return p


def to_posix(path: str | Path) -> str:
    """C:\\Games\\x -> /mnt/c/Games/x under WSL; unchanged elsewhere."""
    p = str(path)
    if is_wsl() and len(p) > 1 and p[1] == ":":
        return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")
    return p


def data_dir() -> Path:
    """Per-user state: backups, downloaded tools. Override with UM_HOME."""
    d = Path(os.environ.get("UM_HOME", Path.home() / ".universal-modder"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def run(cmd: list[str], check: bool = True, capture: bool = True, timeout: float | None = None, **kw) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=check, capture_output=capture, text=True, timeout=timeout, **kw)
    except FileNotFoundError:
        die(f"not found: {cmd[0]}")
    except subprocess.CalledProcessError as e:
        die(f"{' '.join(map(str, cmd[:3]))}... failed ({e.returncode}):\n{(e.stderr or e.stdout or '').strip()[-2000:]}")


def die(msg: str, code: int = 1):
    print(f"um: {msg}", file=sys.stderr)
    sys.exit(code)


def emit(obj, as_json: bool = False):
    if as_json or not isinstance(obj, str):
        print(json.dumps(obj, indent=2, default=str))
    else:
        print(obj)


def parse_size(s: str) -> tuple[int, int]:
    """'64x26' -> (64, 26); '128' -> (128, 128)."""
    if "x" in s.lower():
        w, h = s.lower().split("x", 1)
        return int(w), int(h)
    return int(s), int(s)


def need(module: str, pip_name: str | None = None):
    try:
        return __import__(module)
    except ImportError:
        die(f"this command needs {pip_name or module}: `pip install {pip_name or module}` (or run through bin/um, which uses uv)")
