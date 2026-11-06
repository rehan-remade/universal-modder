// Collapse C-54 test (Frida 17): puts the navmesh walk once into the seven-triangle ring seen in the mark_castle hang.
// With nav_guard the walk stops at its step limit and the game goes on; without it the game freezes.
// The addresses and mesh values are retail ones and this is a local test tool only.
const main = Process.mainModule;
const at = (a) => main.base.add(a - 0x400000);
const WALK = at(0x54b648);
const TRI = 1917, EDGE = 5753, ADJ = [5750, 5743, 5823];
const POINT = [-62.435333251953125, 1.867940902709961, 7.526333808898926];
const p2 = Memory.alloc(12);
POINT.forEach((v, i) => p2.add(i * 4).writeFloat(v));
const t0 = Date.now();
const out = (o) => { o.t = Date.now() - t0; send(o); };
let walks = 0, other = 0;

function ringMesh(mesh) {
  const adj = mesh.add(0x50).readPointer().add(TRI * 12);
  return ADJ.every((v, i) => adj.add(i * 4).readS32() === v);
}
const hook = Interceptor.attach(WALK, {
  onEnter() {
    const c = this.context;
    if (++walks % 100 === 1) out({ ev: 'nav_walks', walks, other });
    let ok = false;
    try { ok = ringMesh(c.esp.add(0xf4).readPointer()); } catch (e) { ok = false; }
    if (!ok) { other++; return; }
    c.esp.add(0x80).writeS32(EDGE);
    c.esi = p2;
    c.ecx = ptr(TRI);
    out({ ev: 'nav_injected', walks, other });
    hook.detach();
  },
});
out({ ev: 'nav_ready', at: WALK.toString() });
