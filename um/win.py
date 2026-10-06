"""Windows games from an agent (native Windows, or WSL where most coding agents live).

    um win setup                                  # copy the PowerShell tools + fetch an ffmpeg with gfxcapture
    um win ps [name]                              # processes with windows: pid, name, title
    um win kill <pid>                             # by exact PID only (never by pattern)
    um win launch --steam 105600 [-- args]        # or: um win launch "C:\\Games\\Foo\\foo.exe" -- -windowed
    um win shot --exe AoE2DE_s.exe out.png [--scale 0.33]    # one frame of the game window (GPU-safe capture)
    um win drive --proc AoE2DE_s "focus" "click 640 360" "key 0x1B"   # input (WinDrive protocol, see um/ps1)
    um win record --exe Game.exe --out C:\\caps\\take1 --seconds 30  # video (gfxcapture) + game-only audio
    um video mux C:\\caps\\take1.mkv C:\\caps\\take1.audio.raw C:\\caps\\take1.json out.mp4
    um win reg get "HKCU\\Software\\Foo" [value] | um win reg set KEY VALUE DATA [--type REG_DWORD]

Why these tools: games render with the GPU, so GDI screen grabs are black - Windows.Graphics.Capture
(ffmpeg's gfxcapture) gets the real frames of one window even when covered. Many games talk to WASAPI
directly, so the only clean way to get just the game's sound is a process-loopback capture. Input goes
through SendInput only while the game is the foreground window, so nothing leaks into other apps.
Lessons: never block the game's main thread when stopping a recording; write .mkv (survives a kill);
NVENC H.264 tops out at 4096 px wide (ultrawide: crop or use HEVC); a crashed game's crash reporter
(BugSplat etc.) can make Steam refuse to relaunch - list and kill it by PID.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from um.common import die, is_windows, is_wsl, ps_exe, to_posix, to_win

HERE = Path(__file__).resolve().parent
TOOLS = HERE / "ps1"          # shipped inside the package so `uv tool install` gets them too
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"


def _check_platform():
    if not (is_windows() or is_wsl()):
        die("`um win` drives Windows games (native Windows or WSL). On Linux use xdotool/ydotool + ffmpeg x11grab/pipewire; "
            "on macOS use screencapture + ffmpeg avfoundation (see skills/game-automation).")


def powershell(script: str, timeout: float = 60) -> str:
    _check_platform()
    r = subprocess.run([ps_exe(), "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=timeout,
                       cwd="/mnt/c" if is_wsl() else None)
    if r.returncode:
        die(f"powershell failed: {r.stderr.strip()[-1500:]}")
    return r.stdout.replace("\r", "")


def local_appdata() -> Path:
    """%LOCALAPPDATA%\\universal-modder (posix path under WSL)."""
    if is_windows():
        base = Path(os.environ["LOCALAPPDATA"])
    else:
        base = Path(to_posix(powershell("[Environment]::GetFolderPath('LocalApplicationData')").strip()))
    d = base / "universal-modder"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tool_path(name: str) -> str:
    """Copy um/ps1/<name> to %LOCALAPPDATA% (PowerShell won't run scripts from \\\\wsl$ reliably); Windows path."""
    src = TOOLS / name
    dst = local_appdata() / "tools" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or hashlib.sha1(dst.read_bytes()).digest() != hashlib.sha1(src.read_bytes()).digest():
        shutil.copyfile(src, dst)
    return to_win(dst)


def ffmpeg_win(required=True) -> str | None:
    """A Windows ffmpeg that has gfxcapture: $UM_FFMPEG_WIN, our download, or one on the Windows PATH."""
    cands = [os.environ.get("UM_FFMPEG_WIN")]
    try:
        cands.append(str(local_appdata() / "ffmpeg" / "bin" / "ffmpeg.exe"))
    except SystemExit:
        pass
    if is_windows():
        cands.append(shutil.which("ffmpeg"))
    for c in cands:
        if c and Path(to_posix(c)).exists():
            return to_posix(c) if is_wsl() else c
    if required:
        die("no Windows ffmpeg with gfxcapture yet: run `um win setup`")
    return None


def setup(args=None):
    _check_platform()
    d = local_appdata()
    for t in ("WinDrive.ps1", "ProcLoopback.ps1"):
        print("tool", tool_path(t))
    if not ffmpeg_win(required=False) or (args and args.force):
        z = d / "ffmpeg.zip"
        print("downloading", FFMPEG_URL)
        urllib.request.urlretrieve(FFMPEG_URL, z)
        with zipfile.ZipFile(z) as zf:
            root = zf.namelist()[0].split("/")[0]
            zf.extractall(d)
        if (d / "ffmpeg").exists():
            shutil.rmtree(d / "ffmpeg")
        (d / root).rename(d / "ffmpeg")
        z.unlink()
    ff = ffmpeg_win()
    out = subprocess.run([ff, "-hide_banner", "-h", "filter=gfxcapture"], capture_output=True, text=True).stdout
    print("ffmpeg", ff, "(gfxcapture ok)" if "gfxcapture" in out else "(WARNING: no gfxcapture in this build)")
    enc = pick_encoder(ff)
    (d / "config.json").write_text(json.dumps(dict(encoder=enc)))
    print("encoder", enc)


def pick_encoder(ff: str) -> str:
    """h264_nvenc / h264_amf / h264_qsv if the GPU takes a test frame, else libx264."""
    for enc in ("h264_nvenc", "h264_amf", "h264_qsv"):
        r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1", "-c:v", enc, "-f", "null", "-"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return enc
    return "libx264"


def encoder() -> str:
    try:
        return json.loads((local_appdata() / "config.json").read_text())["encoder"]
    except (OSError, KeyError, ValueError):
        return "libx264"


# --------------------------------------------------------------------------- processes


def processes(name: str | None = None) -> list[dict]:
    flt = f"-Name '{name}*'" if name else ""
    out = powershell(f"Get-Process {flt} -ErrorAction SilentlyContinue | Where-Object {{ $_.MainWindowHandle -ne 0 }} | "
                     "Select-Object Id,ProcessName,MainWindowTitle,@{n='Hwnd';e={[int64]$_.MainWindowHandle}} | ConvertTo-Json -Compress")
    if not out.strip():
        return []
    d = json.loads(out)
    return d if isinstance(d, list) else [d]


def pid_of(name: str) -> int | None:
    n = name[:-4] if name.lower().endswith(".exe") else name
    out = powershell(f"(Get-Process -Name '{n}' -ErrorAction SilentlyContinue | Select-Object -First 1).Id").strip()
    return int(out) if out.isdigit() else None


def kill(pid: int):
    """By exact PID. (Pattern kills - pkill -f, taskkill /IM with wildcards - can hit the agent's own shell or other apps.)"""
    r = subprocess.run(["taskkill.exe" if is_wsl() else "taskkill", "/PID", str(int(pid)), "/F"], capture_output=True, text=True)
    print((r.stdout or r.stderr).strip())


def launch(target: str, args: list[str], steam: bool = False):
    if steam:
        url = f"steam://rungameid/{target}" if not args else f"steam://run/{target}//{' '.join(args)}/"
        subprocess.run(["cmd.exe" if is_wsl() else "cmd", "/c", "start", "", url], cwd="/mnt/c" if is_wsl() else None, timeout=30)
        return
    exe = to_win(target)
    subprocess.run(["cmd.exe" if is_wsl() else "cmd", "/c", "start", "", exe, *args], cwd="/mnt/c" if is_wsl() else None, timeout=30)


# --------------------------------------------------------------------------- capture


def _source(exe=None, hwnd=None, title=None, cursor=False, crop=None) -> str:
    if hwnd:
        sel = f"hwnd={hwnd}"
    elif exe:
        sel = f"window_exe={exe if exe.lower().endswith('.exe') else exe + '.exe'}"
    elif title:
        sel = f"window_title={title}"
    else:
        die("give --exe, --hwnd or --title")
    c = ""
    if crop:  # left:top:right:bottom pixels to cut
        l, t, r, b = crop
        c = f":crop_left={l}:crop_top={t}:crop_right={r}:crop_bottom={b}"
    return f"gfxcapture={sel}:capture_cursor={1 if cursor else 0}:max_framerate=60{c},hwdownload,format=bgra"


GPU_PREFS = r"Software\Microsoft\DirectX\UserGpuPreferences"


def _gpu_prefs() -> dict:
    """HKCU UserGpuPreferences: exe path (or DirectXUserGlobalSettings) -> "AppStatus=1;AutoHDREnable=2097;"."""
    out = {}
    if is_windows():
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, GPU_PREFS) as k:
                i = 0
                while True:
                    try:
                        name, data, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    out[name] = str(data)
                    i += 1
        except OSError:
            pass
    elif is_wsl():
        try:
            text = subprocess.run(["reg.exe", "query", "HKCU\\" + GPU_PREFS], capture_output=True, text=True, timeout=15, cwd="/mnt/c").stdout
        except (OSError, subprocess.TimeoutExpired):
            return out
        for line in text.splitlines():
            name, sep, data = line.strip().partition("    REG_SZ    ")
            if sep:
                out[name] = data
    return out


def auto_hdr_on(exe=None) -> bool:
    """Windows Auto HDR for this game (its own setting, else the global one). Odd AutoHDREnable = on (2097 on, 2096 off)."""
    def flag(s):
        v = dict(kv.split("=", 1) for kv in s.split(";") if "=" in kv).get("AutoHDREnable", "")
        return int(v) % 2 == 1 if v.isdigit() else None
    prefs = _gpu_prefs()
    if exe:
        name = (exe if exe.lower().endswith(".exe") else exe + ".exe").lower()
        for path, data in prefs.items():
            if path.replace("/", "\\").lower().rsplit("\\", 1)[-1] == name and flag(data) is not None:
                return flag(data)
    return bool(flag(prefs.get("DirectXUserGlobalSettings", "")))


def warn_auto_hdr(exe=None):
    if auto_hdr_on(exe):
        print(f"WARNING: Windows Auto HDR is on{' for ' + exe if exe else ''}. On an HDR display the capture of an SDR game "
              "comes out washed out (brighter, shifted colours). Turn Auto HDR off for the game while capturing: Settings > "
              "System > Display > Graphics > (the game) > Auto HDR.", file=sys.stderr)


def shot(out: str, exe=None, hwnd=None, title=None, scale: float | None = None, timeout=20) -> str:
    """One frame of a game window -> PNG. Returns the (posix) path; with scale also writes <out>_small.png."""
    ff = ffmpeg_win()
    warn_auto_hdr(exe)
    dst = Path(out).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    target = to_win(dst) if is_wsl() else str(dst)
    r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", _source(exe, hwnd, title), "-frames:v", "1", target],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode or not dst.exists():
        die(f"capture failed (is the window open and not minimized?): {r.stderr.strip()[-800:]}")
    if scale:
        from PIL import Image
        im = Image.open(dst)
        small = dst.with_name(dst.stem + "_small.png")
        im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS).save(small)
        print(small)
    return str(dst)


class Recorder:
    """Game window video (gfxcapture -> .mkv) + game-only audio (ProcLoopback -> .audio.raw) + timing .json.

        rec = Recorder(exe="AoE2DE_s.exe", out=r"C:\\caps\\take1"); rec.start(); ...; rec.stop()
        um video mux C:/caps/take1.mkv C:/caps/take1.audio.raw C:/caps/take1.json take1.mp4
    """
    STARTUP = 0.3   # ffmpeg spawn + capture + encoder init before the first frame (measured ~0.24-0.3 s)

    def __init__(self, exe=None, out="take", hwnd=None, title=None, fps=30, audio=True, crop=None, max_width=None, cq=19, pid=None):
        self.pid = pid
        self.exe, self.hwnd, self.title, self.fps, self.audio_on, self.crop, self.max_width, self.cq = exe, hwnd, title, fps, audio, crop, max_width, cq
        self.base = to_win(Path(out).resolve()) if is_wsl() and not (len(out) > 1 and out[1] == ":") else out
        self.video = self.audio = None

    def start(self):
        ff = ffmpeg_win()
        warn_auto_hdr(self.exe)
        enc = encoder()
        vf = [f"fps={self.fps}"]
        mw = self.max_width or (4096 if enc == "h264_nvenc" else None)
        if mw:
            vf.append(f"scale='min(iw,{mw})':-2")
        vf.append("crop=trunc(iw/2)*2:trunc(ih/2)*2")
        # RGB -> YUV with the BT.709 matrix, and say so: an untagged file gets BT.601 here but is read as BT.709 by browsers
        vf.append("scale=out_color_matrix=bt709:out_range=tv,format=yuv420p")
        codec = {"h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(self.cq)],
                 "h264_amf": ["-c:v", "h264_amf", "-quality", "quality", "-qp_i", str(self.cq), "-qp_p", str(self.cq)],
                 "h264_qsv": ["-c:v", "h264_qsv", "-global_quality", str(self.cq)]}.get(enc, ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"])
        t_audio = time.time()
        if self.audio_on:
            pid = self.pid or (pid_of(self.exe) if self.exe else None)
            if not pid:
                print("no pid for audio capture (give --exe or --pid); recording video only", file=sys.stderr)
            else:
                self.audio = subprocess.Popen([ps_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tool_path("ProcLoopback.ps1"),
                                               "-TargetPid", str(pid), "-Out", self.base + ".audio.raw"],
                                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                              cwd="/mnt/c" if is_wsl() else None)
                self.header = json.loads(self.audio.stdout.readline() or "{}")
                t_audio = time.time()
        self.t_video = time.time()
        self.log = Path(to_posix(self.base + ".ffmpeg.log"))
        self.video = subprocess.Popen([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", _source(self.exe, self.hwnd, self.title, crop=self.crop),
                                       "-vf", ",".join(vf), *codec, "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_range", "tv", "-flush_packets", "1", self.base + ".mkv"],
                                      stdin=subprocess.PIPE, stderr=open(self.log, "w"))
        self.t_audio = t_audio
        return self

    def stop(self):
        """'q' to ffmpeg, then wait - never from a thread the game needs (gfxcapture stalls if the window freezes)."""
        if self.video:
            try:
                self.video.stdin.write(b"q")
                self.video.stdin.flush()
            except OSError:
                pass
            try:
                self.video.wait(20)
            except subprocess.TimeoutExpired:
                print("ffmpeg ignored q; killing it", file=sys.stderr)
                self.video.kill()
        meta = dict(video=self.base + ".mkv")
        if self.audio:
            try:
                self.audio.stdin.write("\n")
                self.audio.stdin.flush()
                self.audio.wait(10)
            except (OSError, subprocess.TimeoutExpired):
                self.audio.kill()
            meta.update(self.header, audio=self.base + ".audio.raw", audio_offset_s=round(self.t_video - self.t_audio + self.STARTUP, 3))
        path = Path(to_posix(self.base + ".json"))
        path.write_text(json.dumps(meta, indent=1))
        mkv = Path(to_posix(self.base + ".mkv"))
        if not mkv.exists() or mkv.stat().st_size == 0:
            err = self.log.read_text(errors="replace").strip()[-600:] if self.log.exists() else ""
            print("WARNING: no video frames were captured. gfxcapture only delivers a frame when the window redraws: a game "
                  "that is paused, minimized or showing a static menu produces nothing (and ffmpeg can't react to 'q' until a "
                  "frame arrives). Record while the game is actively rendering." + (f"\nffmpeg: {err}" if err else ""), file=sys.stderr)
        print("recorded", self.base + ".mkv", "(+ audio)" if self.audio else "")
        return meta


class Drive:
    """Python side of WinDrive: d = Drive("AoE2DE_s"); d.focus(); d.click(640, 360); d.key("0x1B")."""

    def __init__(self, proc: str):
        _check_platform()
        self.p = subprocess.Popen([ps_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tool_path("WinDrive.ps1"), "-Proc", proc],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1, cwd="/mnt/c" if is_wsl() else None)
        self.ready = self.p.stdout.readline().strip()

    def cmd(self, line: str, retry: bool = True) -> str:
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        out = self.p.stdout.readline().strip()
        if out.startswith("error") and "foreground" in out and retry:
            self.cmd("focus", retry=False)     # nobody at the PC: the foreground drifts; take it back once
            time.sleep(0.3)
            return self.cmd(line, retry=False)
        if out.startswith("error"):
            raise RuntimeError(f"{line}: {out}")
        return out

    def focus(self):
        return self.cmd("focus") == "ok"

    def rect(self):
        r = self.cmd("rect")
        return None if r == "none" else tuple(int(v) for v in r.split())

    def click(self, x, y, right=False, pause=0.3):
        self.cmd(f"click {int(x)} {int(y)}" + (" right" if right else ""))
        time.sleep(pause)

    def key(self, vk, mode="tap", pause=0.12):
        self.cmd(f"key {vk} {mode}")
        time.sleep(pause)

    def hold(self, vk, ms):
        self.cmd(f"hold {vk} {int(ms)}")

    def type(self, text):
        self.cmd("type " + text)

    def drag(self, x0, y0, x1, y1):
        self.cmd(f"drag {int(x0)} {int(y0)} {int(x1)} {int(y1)}")

    def wheel(self, d):
        self.cmd(f"wheel {int(d)}")

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(5)
        except (OSError, subprocess.TimeoutExpired):
            self.p.kill()


# --------------------------------------------------------------------------- registry


def reg(action: str, key: str, value: str | None = None, data: str | None = None, typ: str = "REG_DWORD"):
    exe = "reg.exe" if is_wsl() else "reg"
    if action == "get":
        cmd = [exe, "query", key] + (["/v", value] if value else [])
    else:
        backup = local_appdata() / "reg-backups"
        backup.mkdir(exist_ok=True)
        bfile = backup / f"{key.replace(chr(92), '_').replace(':', '')}-{time.strftime('%Y%m%d-%H%M%S')}.reg"
        subprocess.run([exe, "export", key, to_win(bfile) if is_wsl() else str(bfile), "/y"], capture_output=True)
        print("backup:", bfile)
        cmd = [exe, "add", key, "/v", value, "/t", typ, "/d", data, "/f"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print((r.stdout or r.stderr).replace("\r", "").strip())


# --------------------------------------------------------------------------- CLI


def main(a):
    c = a.cmd
    if c == "setup":
        setup(a)
    elif c == "ps":
        for p in processes(a.name):
            print(f"{p['Id']:>7}  {p['ProcessName']:28} {p['MainWindowTitle']}")
    elif c == "kill":
        kill(a.pid)
    elif c == "launch":
        launch(a.target, a.args, a.steam)
    elif c == "shot":
        print(shot(a.output, a.exe, a.hwnd, a.title, a.scale))
    elif c == "drive":
        d = Drive(a.proc)
        print(d.ready)
        try:
            for line in a.commands:
                print(line, "->", d.cmd(line, retry=not a.no_retry))
        finally:
            d.close()
    elif c == "record":
        crop = [int(v) for v in a.crop.split(":")] if a.crop else None
        rec = Recorder(exe=a.exe, out=a.out, hwnd=a.hwnd, title=a.title, fps=a.fps, audio=not a.no_audio, crop=crop, pid=a.pid).start()
        try:
            if a.seconds:
                time.sleep(a.seconds)
            else:
                input("recording - press Enter to stop ")
        finally:
            print(json.dumps(rec.stop(), indent=1))
    elif c == "reg":
        reg(a.action, a.key, a.value, a.data, a.type)


def register(sub):
    import argparse
    p = sub.add_parser("win", help="Windows/WSL: screenshots, recording with game-only audio, input, processes",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")
    q = cs.add_parser("setup", help="install the PowerShell tools and a gfxcapture-capable ffmpeg")
    q.add_argument("--force", action="store_true", help="re-download ffmpeg")
    q.set_defaults(func=main)
    q = cs.add_parser("ps", help="processes that have a window")
    q.add_argument("name", nargs="?")
    q.set_defaults(func=main)
    q = cs.add_parser("kill", help="kill by exact PID")
    q.add_argument("pid", type=int)
    q.set_defaults(func=main)
    q = cs.add_parser("launch", help="start a game (exe path or --steam APPID)")
    q.add_argument("target")
    q.add_argument("args", nargs="*")
    q.add_argument("--steam", action="store_true")
    q.set_defaults(func=main)
    for name in ("shot", "record"):
        q = cs.add_parser(name, help="screenshot of a game window" if name == "shot" else "record a game window + its audio")
        if name == "shot":
            q.add_argument("output")
            q.add_argument("--scale", type=float, help="also write a scaled copy (e.g. 0.33) that is cheap to look at")
        else:
            q.add_argument("--out", required=True, help="base path (Windows or WSL path); writes .mkv/.audio.raw/.json")
            q.add_argument("--seconds", type=float)
            q.add_argument("--fps", type=int, default=30)
            q.add_argument("--no-audio", action="store_true")
            q.add_argument("--crop", help="left:top:right:bottom px to cut (e.g. ultrawide -> centre 16:9)")
            q.add_argument("--pid", type=int, help="process to capture audio from, when --exe is ambiguous (e.g. two java.exe)")
        q.add_argument("--exe", help="window's executable name, e.g. AoE2DE_s.exe (regex)")
        q.add_argument("--hwnd", type=int)
        q.add_argument("--title", help="window title regex")
        q.set_defaults(func=main)
    q = cs.add_parser("drive", help="send WinDrive commands to a game window")
    q.add_argument("--proc", required=True, help="process name without .exe")
    q.add_argument("commands", nargs="+")
    q.add_argument("--no-retry", action="store_true")
    q.set_defaults(func=main)
    q = cs.add_parser("reg", help="read / set registry values (set backs the key up first)")
    q.add_argument("action", choices=["get", "set"])
    q.add_argument("key")
    q.add_argument("value", nargs="?")
    q.add_argument("data", nargs="?")
    q.add_argument("--type", default="REG_DWORD")
    q.set_defaults(func=main)
