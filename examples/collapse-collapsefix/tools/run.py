"""One dynamic run of Collapse under the probe (no input is sent to the game).

    uv run --with frida python run.py --tag D1_V1_win_01 [--secs 45] [--shots 20,40] [--leave-mb N] [--cfg setup.ini]

Spawns the exe suspended through Frida (so the probe sees the CRT initializers), resumes it, takes
screenshots of the game window, then kills it by exact PID. Writes runs/<tag>/{events.jsonl,result.json,*.png}.
"""
import argparse, collections, ctypes, hashlib, json, os, re, shutil, subprocess, sys, threading, time
from ctypes import wintypes

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
class MBI(ctypes.Structure):  # MEMORY_BASIC_INFORMATION as seen by a 64-bit caller of VirtualQueryEx
    _fields_ = [('BaseAddress', ctypes.c_uint64), ('AllocationBase', ctypes.c_uint64), ('AllocationProtect', wintypes.DWORD),
                ('PartitionId', wintypes.WORD), ('RegionSize', ctypes.c_uint64), ('State', wintypes.DWORD),
                ('Protect', wintypes.DWORD), ('Type', wintypes.DWORD)]
k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_uint64, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.OpenProcess.restype = wintypes.HANDLE
k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
class PMC(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS_EX
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + \
               [(n, ctypes.c_size_t) for n in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage',
                'PeakPagefileUsage', 'PrivateUsage')]
class MSX(ctypes.Structure):  # MEMORYSTATUSEX
    _fields_ = [('dwLength', wintypes.DWORD), ('dwMemoryLoad', wintypes.DWORD)] + \
               [(n, ctypes.c_uint64) for n in ('ullTotalPhys', 'ullAvailPhys', 'ullTotalPageFile', 'ullAvailPageFile',
                'ullTotalVirtual', 'ullAvailVirtual', 'ullAvailExtendedVirtual')]
k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
k32.GlobalMemoryStatusEx.argtypes = [ctypes.c_void_p]

def va_external(pid):
    """Address-space map of a 32-bit process from outside (no injection, so nothing perturbs init_heap)."""
    h = k32.OpenProcess(0x0400 | 0x0010, False, pid)  # QUERY_INFORMATION | VM_READ
    if not h: return None
    m, a, MB = MBI(), 0x10000, 1 << 20
    acc = collections.Counter(); largest = largest_lo = 0
    while a < 0x100000000 and k32.VirtualQueryEx(h, a, ctypes.byref(m), ctypes.sizeof(m)):
        size = m.RegionSize
        if m.State == 0x10000:
            b, e = m.BaseAddress, m.BaseAddress + size        # split at the 0x70000000 / 0x80000000 borders
            for zone, lo, hi in (('lo', 0, 0x70000000), ('mid', 0x70000000, 0x80000000), ('hi', 0x80000000, 1 << 32)):
                acc['free_' + zone] += max(0, min(e, hi) - max(b, lo))
            largest = max(largest, size)
            largest_lo = max(largest_lo, max(0, min(e, 0x80000000) - b))
        elif m.State == 0x2000: acc['reserved'] += size
        elif m.State == 0x1000: acc['committed'] += size
        a = m.BaseAddress + size
    pmc = PMC(); pmc.cb = ctypes.sizeof(pmc)                   # commit charge: the second road to "out of virtual memory"
    if k32.K32GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb): acc['private'] = pmc.PrivateUsage
    k32.CloseHandle(h)
    ms = MSX(); ms.dwLength = ctypes.sizeof(ms)
    if k32.GlobalMemoryStatusEx(ctypes.byref(ms)):
        acc['sys_commit_limit'], acc['sys_commit_avail'] = ms.ullTotalPageFile, ms.ullAvailPageFile
    r = {k + 'MB': round(v / MB) for k, v in acc.items()}
    r.update(largestMB=round(largest / MB), largestBelow2GMB=round(largest_lo / MB))
    return r

psapi = ctypes.WinDLL('psapi', use_last_error=True)
psapi.GetMappedFileNameW.argtypes = [wintypes.HANDLE, ctypes.c_uint64, wintypes.LPWSTR, wintypes.DWORD]

def mapped_files(pid):
    """Names of the data files the game has mapped (packages), from outside. A level load shows up as a change."""
    h = k32.OpenProcess(0x0400 | 0x0010, False, pid)
    if not h: return None
    m, a, names, buf = MBI(), 0x10000, set(), ctypes.create_unicode_buffer(1024)
    while a < 0x100000000 and k32.VirtualQueryEx(h, a, ctypes.byref(m), ctypes.sizeof(m)):
        if m.State == 0x1000 and m.Type == 0x40000 and m.BaseAddress == m.AllocationBase:   # MEM_MAPPED view start
            if psapi.GetMappedFileNameW(h, m.BaseAddress, buf, 1024):
                n = buf.value
                i = n.lower().find('\\collapse\\')
                if i >= 0: names.add(n[i + 10:])
        elif m.Type == 0x1000000 and m.BaseAddress == m.AllocationBase:                     # MEM_IMAGE: a DLL and where it sits
            if psapi.GetMappedFileNameW(h, m.BaseAddress, buf, 1024):
                names.add('img:%s@%08X' % (buf.value.rsplit('\\', 1)[-1], m.BaseAddress))
        a = m.BaseAddress + m.RegionSize
    k32.CloseHandle(h)
    return names

def close_window(pid):
    """Ask the game's window to close (WM_CLOSE), so it saves setup.ini. Not keyboard/mouse input."""
    ps = "$p=Get-Process -Id %d -ErrorAction SilentlyContinue; if($p){[void]$p.CloseMainWindow()}" % pid
    subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, timeout=30)

def documents():
    """The user's Documents folder as Windows has it (it may be redirected or have a localized name)."""
    guid = (ctypes.c_ubyte * 16).from_buffer_copy(bytes.fromhex('d09ad3fd8f23af46adb46c85480369c7'))  # FOLDERID_Documents
    out = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) == 0:
        path = out.value
        ctypes.windll.ole32.CoTaskMemFree(out)
        return path
    return os.path.join(os.path.expanduser('~'), 'Documents')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
GAME = os.environ.get('COLLAPSE_DIR', r'D:\Steam\steamapps\common\Collapse')  # the game folder
EXE = os.path.join(GAME, 'collapse.exe')
RUNS = os.environ.get('COLLAPSE_RUNS', r'D:\collapse-re\runs')                 # raw data, kept outside the repo
SETUP = os.path.join(documents(), 'Creoteam Collapse', 'setup.ini')
PROCDUMP = os.path.join(os.path.expanduser('~'), 'tools', 'procdump', 'procdump.exe')

def shot(path):
    r = subprocess.run(['bash', os.path.join(ROOT, 'bin', 'um'), 'win', 'shot', '--exe', 'collapse.exe', path],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:   # ffmpeg's gfxcapture often writes the frame and then hangs until the timeout
        open(path + '.err.txt', 'w', encoding='utf-8').write(r.stdout + '\n' + r.stderr)
    return os.path.exists(path) and os.path.getsize(path) > 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True); ap.add_argument('--secs', type=float, default=45)
    ap.add_argument('--shots', default='20,40'); ap.add_argument('--leave-mb', type=int, default=None)
    ap.add_argument('--cfg', default=None); ap.add_argument('--exe', default=EXE)
    ap.add_argument('--no-probe', action='store_true', help='plain launch, no Frida (clean address space)')
    ap.add_argument('--io', action='store_true', help='also hook CreateFileA/CreateDirectoryA/FindFirstFileA (heavy)')
    ap.add_argument('--close', action='store_true', help='end with WM_CLOSE (game saves setup.ini), kill only as fallback')
    ap.add_argument('--dump', action='store_true', help='attach ProcDump: full dump on an unhandled exception')
    ap.add_argument('--maps', action='store_true', help='log mapped package files (level loads) with each VA sample')
    ap.add_argument('--probe', default='probe.js', help='Frida script in tools/ (savetrace.js for D12)')
    a = ap.parse_args()
    out = os.path.join(RUNS, a.tag); os.makedirs(out, exist_ok=True)
    exe_sha = hashlib.sha256(open(a.exe, 'rb').read()).hexdigest()
    if a.cfg:
        os.makedirs(os.path.dirname(SETUP), exist_ok=True); shutil.copyfile(a.cfg, SETUP)

    events, detached = [], {}
    ev_file = open(os.path.join(out, 'events.jsonl'), 'w', encoding='utf-8')
    lock = threading.Lock()
    def emit(e):
        with lock:
            events.append(e); ev_file.write(json.dumps(e, ensure_ascii=False) + '\n'); ev_file.flush()

    if a.no_probe:
        proc = subprocess.Popen([a.exe], cwd=os.path.dirname(a.exe)); pid = proc.pid; t0 = time.time()
        is_dead = lambda: proc.poll() is not None
    else:
        import frida
        src = open(os.path.join(os.path.dirname(__file__), a.probe), encoding='utf-8').read()
        cfg = {'leaveMB': a.leave_mb, 'ioLog': a.io, 'periodMs': 2000}
        src = re.sub(r'/\*CFG\*/.*?/\*CFG\*/', '/*CFG*/' + json.dumps(cfg) + '/*CFG*/', src, flags=re.S)
        dev = frida.get_local_device()
        pid = dev.spawn([a.exe], cwd=os.path.dirname(a.exe))
        sess = dev.attach(pid)
        sess.on('detached', lambda reason, crash: detached.update(reason=reason, crash=str(crash) if crash else None,
                                                                  t=round(time.time() - t0, 2)))
        sc = sess.create_script(src)
        def on_msg(m, d):
            e = m['payload'] if m['type'] == 'send' else {'ev': 'script_error', 'msg': m}
            if e.get('ev') == 'kill_now':   # D12: the writer thread is parked in the hook; end the process by exact PID
                h = k32.OpenProcess(0x0001, False, pid)          # PROCESS_TERMINATE
                e['terminated'] = bool(h and k32.TerminateProcess(h, 0xD12)); k32.CloseHandle(h)
            emit(e)
        sc.on('message', on_msg)
        sc.load()
        t0 = time.time(); dev.resume(pid)
        is_dead = lambda: bool(detached)

    dumper = None
    if a.dump:   # -e: unhandled exceptions only (the allocator's own RaiseException ends up here)
        dumper = subprocess.Popen([PROCDUMP, '-accepteula', '-ma', '-e', str(pid), out],
                                  stdout=open(os.path.join(out, 'procdump.txt'), 'w'), stderr=subprocess.STDOUT)

    def sampler():  # external VA map: dense at start (init_heap, device), then every 2 s
        marks = [0.05, 0.1, 0.2, 0.5, 1, 1.5, 2, 3, 4, 6, 8]
        seen = set()
        while not is_dead():
            el = time.time() - t0
            v = va_external(pid)
            if v: emit(dict(v, ev='va_ext', t=round(el, 2)))
            if a.maps and el > 2:
                cur = mapped_files(pid)
                if cur is not None and cur != seen:
                    emit({'ev': 'maps', 't': round(el, 2), 'added': sorted(cur - seen), 'removed': sorted(seen - cur),
                          'n': len(cur)})
                    seen = cur
            nxt = next((m for m in marks if m > el), None)
            time.sleep(max(0.02, (nxt - el) if nxt else 2.0))
    threading.Thread(target=sampler, daemon=True).start()

    shots = sorted(float(s) for s in a.shots.split(',') if s)
    taken = []
    arm_flag = os.path.join(out, 'ARM')   # D12: create this file (content: N) to arm the kill switch once
    while time.time() - t0 < a.secs and not is_dead():
        if not a.no_probe and os.path.exists(arm_flag):
            try: n = int(open(arm_flag).read().strip() or 2)
            except ValueError: n = 2
            os.remove(arm_flag); sc.post({'type': 'arm', 'n': n})
        if shots and time.time() - t0 >= shots[0]:
            p = os.path.join(out, 'shot_%02ds.png' % shots.pop(0)); taken.append((p, shot(p)))
        time.sleep(0.25)
    alive = not is_dead()
    end = None
    if alive and a.close:
        close_window(pid)
        for _ in range(60):
            if is_dead(): end = 'closed'; break
            time.sleep(0.25)
    if not is_dead():
        try:
            (proc.kill() if a.no_probe else dev.kill(pid)); end = end or 'killed'   # exact PID
        except Exception as ex: detached.setdefault('kill_error', str(ex))
        time.sleep(1.5)
    if a.no_probe and not alive: detached.update(reason='exited', code=proc.returncode)
    time.sleep(0.5)
    if dumper:
        try: dumper.wait(timeout=60)
        except subprocess.TimeoutExpired: dumper.kill()
    glog = os.path.join(os.path.dirname(SETUP), 'collapse.log')
    if os.path.exists(glog): shutil.copyfile(glog, os.path.join(out, 'collapse.log'))
    flog = os.path.join(os.path.dirname(a.exe), 'collapsefix.log')   # the DLL starts it anew on every launch
    if os.path.exists(flog): shutil.copyfile(flog, os.path.join(out, 'collapsefix.log'))
    ev_file.close()

    # summary
    first = lambda ev, tag=None: next((e for e in events if e.get('ev') == ev and (tag is None or e.get('tag') == tag)), None)
    ticks = [e for e in events if e.get('ev') == 'va' and e.get('tag') == 'tick']
    dt, rdt = collections.Counter(), collections.Counter()
    for e in ticks:
        for k, v in (e.get('gameDtHist') or {}).items(): dt[k] += v
        for k, v in (e.get('realDtHist') or {}).items(): rdt[k] += v
    srt = lambda c: dict(sorted(c.items(), key=lambda kv: (len(kv[0]), kv[0])))
    pres = [e['presents'] for e in ticks if 'presents' in e]
    res = {
        'tag': a.tag, 'exe_sha256': exe_sha, 'pid': pid, 'secs': a.secs, 'leave_mb': a.leave_mb,
        'probe': not a.no_probe, 'alive_at_end': alive, 'end': end, 'detached': detached or None,
        'va_ext': [e for e in events if e.get('ev') == 'va_ext'],
        'va_cmdline': [e for e in events if e.get('ev') == 'va' and str(e.get('tag', '')).startswith('GetCommandLineA')],
        'va_after_fence_release': first('va', 'after_fence_release'),
        'va_at_create_device': first('va', 'at_create_device'),
        'min_largest_free_MB': min((e['largestMB'] for e in ticks), default=None),
        'create_device': first('create_device'), 'create_device_hr': (first('create_device_hr') or {}).get('hr'),
        'raises': [e for e in events if e.get('ev') in ('raise', 'map_fail', 'valloc_fail')],
        'setup': [e for e in events if e.get('ev') == 'setup'][-1:] or None,
        'presents_per_2s': pres, 'game_dt_hist_ms': srt(dt), 'real_dt_hist_ms': srt(rdt),
        'dt_zero_frames': sum(e.get('dtZeroFrames', 0) for e in ticks),
        'io': [e for e in events if e.get('ev') == 'io'],
        'threads': [e for e in events if e.get('ev') in ('thread', 'affinity')],
        'script_errors': [e for e in events if e.get('ev') == 'script_error'],
        'shots': [{'path': p, 'ok': ok} for p, ok in taken],
        'maps': [e for e in events if e.get('ev') == 'maps'],
        'min_largest_free_ext_MB': min((e['largestMB'] for e in events if e.get('ev') == 'va_ext' and e['t'] > 10), default=None),
        'dumps': [f for f in os.listdir(out) if f.endswith('.dmp')],
    }
    json.dump(res, open(os.path.join(out, 'result.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ('tag', 'alive_at_end', 'detached', 'create_device_hr', 'min_largest_free_MB',
                                          'min_largest_free_ext_MB', 'dumps')},
                     ensure_ascii=False))

if __name__ == '__main__':
    main()
