// Collapse dynamic probe (Frida 17). Observes only; hooks system DLLs, never the game's .text
// (Metro 2033 gotcha 19: an Interceptor on game code crashed a worker thread).
// CFG is substituted by run.py: {leaveMB: null|number, ioLog: bool, periodMs: number}
const CFG = /*CFG*/{"leaveMB": null, "ioLog": true, "periodMs": 2000}/*CFG*/;

const k32 = Process.getModuleByName('kernel32.dll');
const kb = Process.getModuleByName('kernelbase.dll');
const exp = (name) => { try { return kb.getExportByName(name); } catch (e) { return k32.getExportByName(name); } };
const VirtualQuery = new NativeFunction(exp('VirtualQuery'), 'uint32', ['pointer', 'pointer', 'uint32']);
const VirtualAlloc = new NativeFunction(exp('VirtualAlloc'), 'pointer', ['pointer', 'uint32', 'uint32', 'uint32']);
const MB = 1024 * 1024;
const t0 = Date.now();
const out = (o) => { o.t = Date.now() - t0; send(o); };

function regions() {
  const mbi = Memory.alloc(28), list = [];
  let a = ptr(0x10000);
  for (;;) {
    if (VirtualQuery(a, mbi, 28) === 0) break;
    const base = mbi.readPointer(), size = mbi.add(12).readU32(), state = mbi.add(16).readU32();
    list.push({ base: base, size: size, state: state });
    const next = base.add(size);
    if (next.compare(a) <= 0 || size === 0) break;
    a = next;
  }
  return list;
}
// Zones: lo < 0x70000000 (init_heap's fence) <= mid < 0x80000000 (2 GB) <= hi (LAA only). Regions are split at the borders.
function vaMap(tag) {
  let free = 0, largest = 0, z = { lo: 0, mid: 0, hi: 0 }, reserved = 0, committed = 0, largestBelow2G = 0;
  for (const r of regions()) {
    const b = r.base.toUInt32(), e = b + r.size;
    if (r.state === 0x10000) {
      free += r.size; if (r.size > largest) largest = r.size;
      z.lo += Math.max(0, Math.min(e, 0x70000000) - b);
      z.mid += Math.max(0, Math.min(e, 0x80000000) - Math.max(b, 0x70000000));
      z.hi += Math.max(0, e - Math.max(b, 0x80000000));
      largestBelow2G = Math.max(largestBelow2G, Math.max(0, Math.min(e, 0x80000000) - b));
    } else if (r.state === 0x2000) reserved += r.size; else if (r.state === 0x1000) committed += r.size;
  }
  const f = (x) => Math.round(x / MB);
  return { ev: 'va', tag: tag, freeMB: f(free), largestMB: f(largest), free_loMB: f(z.lo), free_midMB: f(z.mid),
           free_hiMB: f(z.hi), largestBelow2GMB: f(largestBelow2G), reservedMB: f(reserved), committedMB: f(committed) };
}

// Reserve free address space until only CFG.leaveMB stays free (D1b provocation).
function eatTo(leaveMB) {
  const leave = leaveMB * MB;
  const G = 0x10000;  // reservations must start on the 64 KB allocation granularity
  let free = regions().filter(r => r.state === 0x10000).sort((x, y) => y.size - x.size);
  let total = free.reduce((s, r) => s + r.size, 0), taken = 0, fails = 0;
  for (const r of free) {
    if (total - taken <= leave) break;
    const b = r.base.toUInt32(), ab = Math.ceil(b / G) * G, avail = Math.floor((b + r.size - ab) / G) * G;
    let want = Math.floor(Math.min(avail, total - taken - leave) / G) * G;
    while (want >= G) {
      if (!VirtualAlloc(ptr(ab), want, 0x2000, 1).isNull()) { taken += want; break; }
      fails++; want = Math.floor(want / 2 / G) * G;
    }
  }
  out({ ev: 'eat', leaveMB: leaveMB, takenMB: Math.round(taken / MB), fails: fails });
  return Math.round(taken / MB);
}

// 1) VA right after the CRT initializers (init_heap) ran: WinMain calls GetCommandLineA early.
// (VC6 CRT calls it once before the initializers; WinMain calls it again after them.)
let cmdN = 0;
Interceptor.attach(exp('GetCommandLineA'), { onEnter() { if (++cmdN <= 3) out(vaMap('GetCommandLineA#' + cmdN)); } });
// init_heap's fence (reserve everything below 0x70000000) is released by the function at 0x5E5990 (VirtualFree MEM_RELEASE).
// Hot hooks starve the agent and froze the game on the intro logo (2026-10-28), so this one detaches itself.
let fenceReleased = 0;
const vfHook = Interceptor.attach(exp('VirtualFree'), {
  onEnter() { const ra = this.returnAddress.toUInt32(); this.fence = ra >= 0x5E5990 && ra < 0x5E59C0; },
  onLeave() {
    if (this.fence && fenceReleased++ === 0)
      setTimeout(() => { out(vaMap('after_fence_release')); vfHook.detach(); }, 0);
  }
});

// 2) Engine "out of virtual memory": the allocator raises 0xC0000005 itself.
Interceptor.attach(exp('RaiseException'), {
  onEnter(a) { out({ ev: 'raise', code: '0x' + (a[0].toUInt32() >>> 0).toString(16), from: this.returnAddress.toString() }); out(vaMap('at_raise')); }
});
Interceptor.attach(exp('MapViewOfFile'), {
  onLeave(r) { if (r.isNull()) { out({ ev: 'map_fail', err: this.lastError }); out(vaMap('at_map_fail')); } }
});
// (No VirtualAlloc hook: it is hot, and the engine reports its own failures through RaiseException.)

// 3) D3D9: GetProcAddress("Direct3DCreate9") -> IDirect3D9 vtable.
const ppNames = ['BackBufferWidth', 'BackBufferHeight', 'BackBufferFormat', 'BackBufferCount', 'MultiSampleType',
  'MultiSampleQuality', 'SwapEffect', 'hDeviceWindow', 'Windowed', 'EnableAutoDepthStencil',
  'AutoDepthStencilFormat', 'Flags', 'FullScreen_RefreshRateInHz', 'PresentationInterval'];
let presents = 0, d3dHooked = false, devHooked = false;
function hookDevice(dev) {
  if (devHooked) return; devHooked = true;
  const vt = dev.readPointer();
  Interceptor.attach(vt.add(0x44).readPointer(), { onEnter() { presents++; onPresent(); } }); // Present
  Interceptor.attach(vt.add(0x40).readPointer(), {                                          // Reset
    onEnter(a) { this.pp = a[1]; }, onLeave(r) { out({ ev: 'reset', hr: '0x' + (r.toUInt32() >>> 0).toString(16) }); }
  });
}
function hookD3D(d3d) {
  if (d3dHooked) return; d3dHooked = true;
  const vt = d3d.readPointer();
  out({ ev: 'd3d', adapters: new NativeFunction(vt.add(0x10).readPointer(), 'uint32', ['pointer'], 'stdcall')(d3d) });
  Interceptor.attach(vt.add(0x40).readPointer(), {                                          // CreateDevice
    onEnter(a) {
      this.ppd = a[6];
      const pp = {}; for (let i = 0; i < 14; i++) pp[ppNames[i]] = '0x' + (a[5].add(i * 4).readU32() >>> 0).toString(16);
      let eaten = null;
      if (CFG.leaveMB !== null) eaten = eatTo(CFG.leaveMB);
      out({ ev: 'create_device', adapter: a[1].toUInt32(), devType: a[2].toUInt32(),
            behavior: '0x' + (a[4].toUInt32() >>> 0).toString(16), pp: pp, eatenMB: eaten });
      out(vaMap('at_create_device'));
    },
    onLeave(r) {
      const hr = r.toUInt32() >>> 0;
      out({ ev: 'create_device_hr', hr: '0x' + hr.toString(16) });
      if (hr === 0) hookDevice(this.ppd.readPointer());
    }
  });
}
// kernel32!GetProcAddress has its own body on Windows 11 (it doesn't pass through kernelbase!GetProcAddress).
Interceptor.attach(k32.getExportByName('GetProcAddress'), {
  onEnter(a) { const n = a[1]; this.name = (n.toUInt32() > 0xffff) ? n.readCString() : null; },
  onLeave(r) {
    if (this.name === 'Direct3DCreate9' && !r.isNull())
      Interceptor.attach(r, { onLeave(ret) { if (!ret.isNull()) hookD3D(ret); } });
  }
});

// 4) Game time without hooking GetTickCount (the limiter calls it ~100k/s; a JS hook perturbs timing and
//    CModule crashes 32-bit targets here). The main loop stores its tick in 0x6379A4 (insn 0x5E2BB0), so at
//    every Present we read it: game dt = tick delta; real dt = QueryPerformanceCounter delta.
const QPC = new NativeFunction(exp('QueryPerformanceCounter'), 'int', ['pointer']);
const QPF = new NativeFunction(exp('QueryPerformanceFrequency'), 'int', ['pointer']);
const qbuf = Memory.alloc(8); QPF(qbuf); const qfreq = qbuf.readU64().toNumber();
const qms = () => { QPC(qbuf); return qbuf.readU64().toNumber() * 1000 / qfreq; };
const TICK = ptr(0x6379A4);
let lastGameTick = null, lastReal = null, gameDt = {}, realDt = {}, tickSame = 0, frames = 0;
function onPresent() {
  const t = TICK.readU32(), r = qms();
  if (lastGameTick !== null) {
    const d = (t - lastGameTick) >>> 0, k = d > 129 ? '>129' : String(d);
    gameDt[k] = (gameDt[k] || 0) + 1; if (d === 0) tickSame++;
    const rd = Math.round(r - lastReal), rk = rd > 129 ? '>129' : String(rd);
    realDt[rk] = (realDt[rk] || 0) + 1; frames++;
  }
  lastGameTick = t; lastReal = r;
}
function timeDrain() {
  const o = { gameDtHist: gameDt, realDtHist: realDt, frames: frames, dtZeroFrames: tickSame };
  gameDt = {}; realDt = {}; frames = 0; tickSame = 0; return o;
}
let limSleeps = 0, limSleepMs = 0;
Interceptor.attach(exp('Sleep'), {
  onEnter(a) { const ra = this.returnAddress; if (ra.compare(ptr(0x5E2880)) >= 0 && ra.compare(ptr(0x5E2B30)) < 0) { limSleeps++; limSleepMs += a[0].toUInt32(); } }
});

// 5) Files: the single-instance lock, the profile root, saves, ini files.
const interesting = /creoteam|96bae105|savegame|\.ini|onedrive|documents|appdata/i;
let fileOpens = 0;
function hookPath(name, idx) {
  Interceptor.attach(exp(name), {
    onEnter(a) { this.p = a[idx].isNull() ? '' : a[idx].readAnsiString(); },
    onLeave(r) {
      fileOpens++;
      const bad = (name === 'CreateFileA' || name === 'FindFirstFileA') ? (r.toInt32() === -1) : r.isNull() || r.toUInt32() === 0;
      if (CFG.ioLog && (interesting.test(this.p) || bad && !/\\data\\/i.test(this.p)))
        out({ ev: 'io', fn: name, path: this.p, ok: !bad, err: bad ? this.lastError : 0 });
    }
  });
}
if (CFG.ioLog) { hookPath('CreateFileA', 0); hookPath('CreateDirectoryA', 0); hookPath('FindFirstFileA', 0); }  // D0/D4 only

// 6) Threads.
Interceptor.attach(exp('CreateThread'), { onEnter(a) { out({ ev: 'thread', start: a[2].toString(), from: this.returnAddress.toString() }); } });
Interceptor.attach(exp('SetThreadAffinityMask'), { onEnter(a) { out({ ev: 'affinity', mask: '0x' + a[1].toUInt32().toString(16) }); } });

// 7) Settings object, polled (no hooks in game code): S = [0x64EE1C].
let lastSetup = '';
function setupSnap() {
  const S = ptr(0x64EE1C).readPointer();
  if (S.isNull()) return null;
  const sc = []; for (let i = 0; i < 6; i++) sc.push(S.add(0x6a0 + i * 4).readU32());
  return { fullscreen: S.add(0x75).readU8(), res: [S.add(0x78).readU32(), S.add(0x7c).readU32()],
           win: [S.add(0x80).readU32(), S.add(0x84).readU32()], aa: S.add(0x88).readU32(), freqMax: S.add(0x8c).readU32(),
           bits: S.add(0x90).readU32(), fovRad: S.add(0x9c).readFloat(), fovDeg: S.add(0x9c).readFloat() * 180 / Math.PI,
           screen6: sc, screen6f: sc.map(v => { const b = Memory.alloc(4); b.writeU32(v); return b.readFloat(); }) };
}
setInterval(() => {
  let s = null; try { s = setupSnap(); } catch (e) {}
  if (s) { const j = JSON.stringify(s); if (j !== lastSetup) { lastSetup = j; out(Object.assign({ ev: 'setup' }, s)); } }
  out(Object.assign(vaMap('tick'), timeDrain(), { presents: presents, limSleeps: limSleeps, limSleepMs: limSleepMs,
    fileOpens: fileOpens, fenceReleases: fenceReleased }));
  presents = 0; limSleeps = 0; limSleepMs = 0;
}, CFG.periodMs);
out({ ev: 'probe_ready', cfg: CFG });
