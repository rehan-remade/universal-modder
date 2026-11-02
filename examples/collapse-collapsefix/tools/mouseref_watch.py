"""mouseref_watch.py <pid> <seconds> : C-56. Poll the system dinput8 (build dbcea407) shared mouse refcount (+0x26100)
and its table (+0x260F0) every 20 ms in a running game; print each change with time. 0 = the table was freed.
Local test tool: the offsets belong to one Windows build, and other builds are refused.
    uv run --with frida python mouseref_watch.py <pid> 600"""
import sys, time, frida

JS = r"""
var m = Process.enumerateModules().filter(function (x) { return /\\(syswow64|system32)\\dinput8\.dll$/i.test(x.path); })[0];
if (!m) { send({err: 'no system dinput8'}); }
else {
  var pe = m.base.add(m.base.add(0x3c).readU32());
  var ts = pe.add(8).readU32();
  if (ts !== 0xdbcea407) send({err: 'timestamp ' + ts.toString(16)});
  else {
    var rc = m.base.add(0x26100), tb = m.base.add(0x260F0);
    var last = null;
    setInterval(function () {
      var v = rc.readS32() + ' ' + tb.readPointer();
      if (v !== last) { last = v; send({v: v}); }
    }, 20);
    send({ok: m.base.toString()});
  }
}
"""
pid, secs = int(sys.argv[1]), float(sys.argv[2])
s = frida.attach(pid)
sc = s.create_script(JS)
t0 = time.time()
def on(msg, data):
    p = msg.get('payload', msg)
    print('%8.2f %s' % (time.time() - t0, p), flush=True)
gone = []
s.on('detached', lambda reason, *rest: gone.append(reason))  # the game closed: stop instead of waiting out secs
sc.on('message', on)
sc.load()
try:
    while time.time() - t0 < secs and not gone: time.sleep(0.5)
    if gone: print('%8.2f detached: %s' % (time.time() - t0, gone[0]), flush=True)
finally:
    try: s.detach()
    except Exception: pass
