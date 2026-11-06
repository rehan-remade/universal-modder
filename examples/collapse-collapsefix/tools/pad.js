// Collapse gamepad probe (Frida 17): times XInputGetState and, on request, answers it with a virtual pad on slot 0.
// No driver and no real input. Commands come from a JSON file, each with a new "id":
//   {"id":1,"on":true}                                  connect the pad, everything neutral
//   {"id":2,"on":false}                                 disconnect
//   {"id":3,"seq":[{"name":"rx","ms":1500,"rx":8192}]}  play steps, neutral between them, one 'pad_step' event per step
// Step fields: b (buttons), lt, rt, lx, ly, rx, ry. The addresses are retail ones and this is a local test tool only.
const CFG = /*CFG*/{}/*CFG*/;
const CMD = 'D:\\collapse-re\\runs\\pad_cmd.json'; // edit: your own runs folder (run.py doesn't fill this in)
const GAP = 500;

const main = Process.mainModule;
const at = (a) => main.base.add(a - 0x400000);
const POLL = at(0x428810), POLL_END = at(0x428bf0), LOOK = at(0x423730);

const k32 = Process.getModuleByName('kernel32.dll');
const qpc = new NativeFunction(k32.getExportByName('QueryPerformanceCounter'), 'int', ['pointer']);
const qpf = new NativeFunction(k32.getExportByName('QueryPerformanceFrequency'), 'int', ['pointer']);
const qbuf = Memory.alloc(8), fbuf = Memory.alloc(4);
qpf(qbuf);
const TICK_US = 1e6 / qbuf.readU64().toNumber();
const now = () => { qpc(qbuf); return qbuf.readU64().toNumber() * TICK_US; };
const asFloat = (p) => { fbuf.writeU32(p.toUInt32()); return fbuf.readFloat(); };
const t0 = Date.now();
const out = (o) => { o.t = Date.now() - t0; send(o); };

const NEUTRAL = { b: 0, lt: 0, rt: 0, lx: 0, ly: 0, rx: 0, ry: 0 };
let on = false, state = NEUTRAL, packet = 0;
let win = { calls: 0, ok: 0, sumUs: 0, maxUs: 0, over1ms: 0, frames: 0, maxGapMs: 0 };
let step = null, lastFrame = 0, lastMask = -1;
const gaps = [];

function hookXInput(m) {
  Interceptor.attach(m.getExportByName('XInputGetState'), {
    onEnter(a) { this.slot = a[0].toInt32(); this.st = a[1]; this.t = now(); },
    onLeave(r) {
      const us = now() - this.t;
      win.calls++; win.sumUs += us;
      if (us > win.maxUs) win.maxUs = us;
      if (us > 1000) win.over1ms++;
      if (this.slot === 0 && on) {
        const p = this.st;
        p.writeU32(++packet);
        p.add(4).writeU16(state.b); p.add(6).writeU8(state.lt); p.add(7).writeU8(state.rt);
        p.add(8).writeS16(state.lx); p.add(10).writeS16(state.ly);
        p.add(12).writeS16(state.rx); p.add(14).writeS16(state.ry);
        r.replace(ptr(0));
      }
      if (r.toInt32() === 0) win.ok++;
    },
  });
  out({ ev: 'xinput_hooked', base: m.base.toString(), path: m.path });
}

Interceptor.attach(POLL, {
  onEnter() { this.self = this.context.ecx; },
  onLeave() {
    const t = Date.now();
    if (lastFrame) {
      const g = t - lastFrame;
      if (g > win.maxGapMs) win.maxGapMs = g;
      if (g > 200) gaps.push(g);
    }
    lastFrame = t; win.frames++;
    const mask = this.self.add(8).readU32();
    if (mask !== lastMask) {
      lastMask = mask;
      out({ ev: 'pad_mask', mask: '0x' + (mask >>> 0).toString(16) });
      if (step) step.masks.push('0x' + (mask >>> 0).toString(16));
    }
    if (step) step.frames++;
  },
});
Interceptor.attach(LOOK, {
  onEnter(a) {
    if (!step || this.returnAddress.compare(POLL) < 0 || this.returnAddress.compare(POLL_END) >= 0) return;
    step.calls++;
    const yaw = asFloat(a[0]), pitch = asFloat(a[1]);
    step.yaw += yaw; step.pitch += pitch;
    if (Math.abs(yaw) > step.maxYaw) step.maxYaw = Math.abs(yaw);
    if (Math.abs(pitch) > step.maxPitch) step.maxPitch = Math.abs(pitch);
  },
});

function play(list, i) {
  if (i >= list.length) { state = NEUTRAL; out({ ev: 'pad_seq_done' }); return; }
  const s = list[i];
  state = Object.assign({}, NEUTRAL, s);
  step = { calls: 0, frames: 0, yaw: 0, pitch: 0, maxYaw: 0, maxPitch: 0, masks: [] };
  setTimeout(() => {
    out(Object.assign({ ev: 'pad_step', name: s.name, input: s }, step));
    step = null; state = NEUTRAL;
    setTimeout(() => play(list, i + 1), GAP);
  }, s.ms || 1500);
}

let lastId = null, hooked = false;
setInterval(() => {
  if (!hooked) {
    const m = Process.findModuleByName('xinput1_3.dll');
    if (m) { hooked = true; hookXInput(m); }
  }
  let c = null;
  try { c = JSON.parse(File.readAllText(CMD)); } catch (e) { return; }
  if (c.id === lastId) return;
  lastId = c.id;
  if (c.on !== undefined) { on = !!c.on; state = NEUTRAL; out({ ev: 'pad_on', on: on }); }
  if (c.seq) { on = true; out({ ev: 'pad_seq', n: c.seq.length }); play(c.seq, 0); }
}, 100);

setInterval(() => {
  const w = win;
  win = { calls: 0, ok: 0, sumUs: 0, maxUs: 0, over1ms: 0, frames: 0, maxGapMs: 0 };
  out({ ev: 'pad_tick', calls: w.calls, ok: w.ok, avgUs: w.calls ? Math.round(w.sumUs / w.calls) : 0, maxUs: Math.round(w.maxUs),
        over1ms: w.over1ms, frames: w.frames, maxGapMs: w.maxGapMs, gaps: gaps.splice(0) });
}, 2000);
out({ ev: 'pad_probe_loaded', base: main.base.toString() });
