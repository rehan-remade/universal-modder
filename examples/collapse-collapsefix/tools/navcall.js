// Collapse C-54 test (Frida 17): calls the navmesh function once from the game's own thread, with the arguments of the
// mark_castle hang. With nav_guard it returns; without it the game freezes. Retail addresses, a local test tool only.
const main = Process.mainModule;
const at = (a) => main.base.add(a - 0x400000);
const FN = at(0x54b140);
const TRI = 1917, ADJ = [5750, 5743, 5823];
const POINT = [-62.435333251953125, 1.867940902709961, 7.526333808898926];
const RADIUS = /*RADIUS*/0/*RADIUS*/;
const p2 = Memory.alloc(12);
const call = new NativeFunction(FN, 'uint32', ['pointer', 'pointer', 'float'], 'thiscall');
let calls = 0, other = 0, done = false;

function ringMesh(mesh) {
  const adj = mesh.add(0x50).readPointer().add(TRI * 12);
  return ADJ.every((v, i) => adj.add(i * 4).readS32() === v);
}
send({ ev: 'navcall_ready' });
const hook = Interceptor.attach(FN, {
  onEnter() {
    calls++;
    if (done) return;
    const mesh = this.context.ecx;
    let ok = false;
    try { ok = ringMesh(mesh); } catch (e) { ok = false; }
    if (!ok) {
      if (++other % 500 === 1) send({ ev: 'navcall_other', calls, other });
      return;
    }
    done = true;
    hook.detach();
    POINT.forEach((v, i) => p2.add(i * 4).writeFloat(v));
    send({ ev: 'navcall_start', calls, other, mesh: mesh.toString() });
    const t = Date.now();
    const r = call(mesh, p2, RADIUS);
    send({ ev: 'navcall_returned', result: r & 0xff, ms: Date.now() - t });
  },
});
