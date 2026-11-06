// Save trace for the torn-save test, gotcha 15 in the note (Frida 17). Hooks only kernel32/kernelbase exports, never the game's .text.
// Logs every open/write/flush/truncate/close of files under Creoteam Collapse\ (saves, profile, ini).
// Kill switch: after run.py posts {type:'arm', n:N}, the N-th WriteFile into the next *.jpg save is held in
// its hook and run.py terminates the process by exact PID, leaving a save cut at the bytes written before it.
const CFG = /*CFG*/{}/*CFG*/;

const k32 = Process.getModuleByName('kernel32.dll');
const kb = Process.getModuleByName('kernelbase.dll');
const exp = (name) => { try { return kb.getExportByName(name); } catch (e) { return k32.getExportByName(name); } };
const t0 = Date.now();
const out = (o) => { o.t = Date.now() - t0; send(o); };

const watch = /creoteam/i;
const H = new Map();          // handle string -> {path, bytes, writes}
let killAt = 0;               // 0 = disarmed; N = hold the N-th WriteFile of the next save
function onArm(m) { killAt = m.n || 2; out({ ev: 'armed', n: killAt }); recv('arm', onArm); }
recv('arm', onArm);

Interceptor.attach(exp('CreateFileA'), {
  onEnter(a) {
    this.p = a[0].isNull() ? '' : a[0].readAnsiString();
    this.w = watch.test(this.p);
    if (this.w) { this.acc = a[1].toUInt32(); this.share = a[2].toUInt32(); this.disp = a[4].toUInt32(); this.flags = a[5].toUInt32(); }
  },
  onLeave(r) {
    if (!this.w) return;
    const bad = r.toInt32() === -1;
    out({ ev: 'open', path: this.p, access: '0x' + this.acc.toString(16), share: this.share, disp: this.disp,
          flags: '0x' + this.flags.toString(16), h: r.toString(), ok: !bad, err: bad ? this.lastError : 0 });
    if (!bad && (this.acc & 0x40000000)) H.set(r.toString(), { path: this.p, bytes: 0, writes: 0 });
  }
});

Interceptor.attach(exp('WriteFile'), {
  onEnter(a) {
    const s = H.get(a[0].toString());
    if (!s) return;
    const n = a[2].toUInt32();
    s.writes++;
    if (killAt && /\.jpg$/i.test(s.path) && s.writes >= killAt) {
      killAt = 0;
      out({ ev: 'kill_now', path: s.path, writes_done: s.writes - 1, bytes_done: s.bytes, pending: n });
      for (let i = 0; i < 300; i++) Thread.sleep(0.1);   // hold this write; run.py terminates the process meanwhile
    }
    s.bytes += n;
  }
});

for (const [name, what] of [['FlushFileBuffers', 'flush'], ['SetEndOfFile', 'truncate']]) {
  Interceptor.attach(exp(name), { onEnter(a) { const s = H.get(a[0].toString()); if (s) out({ ev: what, path: s.path, bytes: s.bytes }); } });
}
Interceptor.attach(exp('CloseHandle'), {
  onEnter(a) {
    const k = a[0].toString(), s = H.get(k);
    if (!s) return;
    H.delete(k);
    out({ ev: 'close', path: s.path, bytes: s.bytes, writes: s.writes });
  }
});
Interceptor.attach(exp('DeleteFileA'), {
  onEnter(a) { const p = a[0].isNull() ? '' : a[0].readAnsiString(); if (watch.test(p)) out({ ev: 'delete', path: p }); }
});
out({ ev: 'probe_ready', probe: 'savetrace' });
