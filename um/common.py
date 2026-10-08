"""Small helpers shared by the subcommands: platform checks, WSL path mapping, subprocess, output."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import NoReturn


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
    if os.name != "nt":
        d.chmod(0o700)
    return d


def safe_filename_segment(value: str, label: str = "name") -> str:
    """Return one portable filename segment, or fail before any filesystem/network side effect."""
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if (not isinstance(value, str) or not value or len(value.encode("utf-8")) > 240 or value in {".", ".."} or Path(value).name != value
            or "/" in value or "\\" in value or ":" in value or value[-1:] in {" ", "."}
            or value.split(".", 1)[0].upper() in reserved or any(ord(c) < 32 for c in value)):
        die(f"unsafe {label}: {value!r}")
    return value


def bounded_read(stream, limit: int, label: str = "response") -> bytes:
    """Read at most limit bytes plus one sentinel byte so oversized responses fail closed."""
    out = bytearray()
    while len(out) <= limit:
        try:
            chunk = stream.read(min(1 << 20, limit + 1 - len(out)))
        except TypeError:
            # Small in-memory/file-like fakes may implement read() without a size.
            chunk = stream.read()
            if len(chunk) > limit:
                die(f"{label} exceeds the {limit:,}-byte limit")
            return bytes(chunk)
        if not chunk:
            return bytes(out)
        out.extend(chunk)
    die(f"{label} exceeds the {limit:,}-byte limit")


def atomic_write_stream(path: Path, stream, limit: int, label: str = "download") -> int:
    """Bound a streamed write and replace the final path only after a complete fsynced payload exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_filename_segment(path.name, "output filename")
    tmp = path.with_name(f".{path.name}.um-part-{os.getpid()}-{time.time_ns()}")
    total = 0
    try:
        with open(tmp, "xb") as out:
            while True:
                try:
                    chunk = stream.read(1 << 20)
                except TypeError:
                    chunk = stream.read()
                    if total + len(chunk) > limit:
                        die(f"{label} exceeds the {limit:,}-byte limit")
                    out.write(chunk)
                    total += len(chunk)
                    break
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    die(f"{label} exceeds the {limit:,}-byte limit")
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
        return total
    finally:
        tmp.unlink(missing_ok=True)


_SENSITIVE_KEY = re.compile(r"(?:^|[_-])(?:api_?key|key|token|secret|password|authorization|auth)(?:$|[_-])", re.I)


def redact_for_receipt(value):
    """Remove likely credentials and signed URL queries from durable JSON receipts."""
    if isinstance(value, dict):
        return {k: ("<redacted>" if _SENSITIVE_KEY.search(str(k)) else redact_for_receipt(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_for_receipt(v) for v in value]
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        p = urllib.parse.urlsplit(value)
        if p.username or p.password or p.query:
            host = p.hostname or ""
            if p.port:
                host += f":{p.port}"
            return urllib.parse.urlunsplit((p.scheme, host, p.path, "<redacted>", ""))
    return value


def append_private_jsonl(path: Path, record: dict) -> None:
    """Append one bounded receipt record without following a pre-existing symlink."""
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_filename_segment(path.name, "receipt filename")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    data = (json.dumps(redact_for_receipt(record), separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > 8 << 20:
        die("receipt record exceeds the 8 MiB limit")
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        die(f"cannot open receipt {path}: {exc}")
    try:
        os.fchmod(fd, 0o600)
        pending = memoryview(data)
        while pending:
            written = os.write(fd, pending)
            if written <= 0:
                die(f"short write while appending receipt {path}")
            pending = pending[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def run(cmd: list[str], check: bool = True, capture: bool = True, timeout: float | None = None, **kw) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=check, capture_output=capture, text=True, timeout=timeout, **kw)
    except FileNotFoundError:
        die(f"not found: {cmd[0]}")
    except subprocess.CalledProcessError as e:
        die(f"{' '.join(map(str, cmd[:3]))}... failed ({e.returncode}):\n{(e.stderr or e.stdout or '').strip()[-2000:]}")


def die(msg: str, code: int = 1) -> NoReturn:
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
