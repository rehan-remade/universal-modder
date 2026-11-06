"""Regression part A for collapsefix: start the game to the menu with one ini variant per run, no input, 40 s each,
through run.py (killed by exact PID, screenshot at 25 s). Reports each run's hook lines and any SKIP/FAILED.
Backs up the game's collapsefix.ini and the profile's setup.ini first and always restores them. The variants are
written from the repo's patch/collapsefix.ini, so they test the defaults that ship.
    python regress.py [case ...]   (no args = all cases, about 27 min)"""
import ctypes, json, os, re, shutil, subprocess, sys


def documents():
    """The user's Documents folder as Windows has it (it may be redirected or have a localized name)."""
    guid = (ctypes.c_ubyte * 16).from_buffer_copy(bytes.fromhex('d09ad3fd8f23af46adb46c85480369c7'))  # FOLDERID_Documents
    out = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) == 0:
        path = out.value
        ctypes.windll.ole32.CoTaskMemFree(out)
        return path
    return os.path.join(os.path.expanduser('~'), 'Documents')


GAME = os.environ.get('COLLAPSE_DIR', r'D:\Steam\steamapps\common\Collapse')  # the game folder (run.py reads it too)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(REPO, 'tools', 'run.py')
SETUP = os.path.join(documents(), 'Creoteam Collapse', 'setup.ini')
RUNS = os.environ.get('COLLAPSE_RUNS', r'D:\collapse-re\runs')
BK = os.path.join(os.path.dirname(RUNS), 'backup', 'regress')
SECS = 40

# name: ({(section, key): value}, setup.ini edit or None)
CASES = {
    'defaults': ({}, None),
    'borderless0': ({('fix', 'borderless'): '0'}, None),
    'dpi0': ({('fix', 'dpi_aware'): '0'}, None),
    'alttab0': ({('fix', 'alt_tab'): '0'}, None),
    'excl_alttab0': ({('fix', 'borderless'): '0', ('fix', 'alt_tab'): '0'}, None),
    'displaymode0': ({('fix', 'display_mode'): '0'}, None),
    'refresh_game': ({('fix', 'refresh'): '-1'}, None),
    'vsync1': ({('fix', 'vsync'): '1'}, None),
    'timer0': ({('fix', 'timer'): '0'}, None),
    'savelog0': ({('fix', 'save_log'): '0'}, None),
    'fov0': ({('fix', 'fov'): '0'}, None),
    'fov100': ({('fix', 'fov'): '100'}, None),
    'uiscale100': ({('fix', 'ui_scale'): '100'}, None),
    'uiscale200': ({('fix', 'ui_scale'): '200'}, None),
    'englishkeys0': ({('fix', 'english_keys'): '0'}, None),
    'input0': ({('fix', 'input'): '0'}, None),
    'input0_keys0': ({('fix', 'input'): '0', ('fix', 'english_keys'): '0'}, None),
    'navguard0': ({('fix', 'nav_guard'): '0'}, None),
    'batches0': ({('fix', 'release_batches'): '0'}, None),
    'keeper0': ({('fix', 'mouse_keeper'): '0'}, None),
    'all_input_off': ({('fix', 'input'): '0', ('fix', 'english_keys'): '0', ('fix', 'mouse_keeper'): '0'}, None),
    'pad30': ({('fix', 'pad_camera_deadzone'): '30'}, None),
    'counts1': ({('log', 'd3d_counts'): '1'}, None),
    'log0': ({('log', 'enabled'): '0'}, None),
    'badres_excl': ({('fix', 'borderless'): '0'}, ('Resolution', '2560 1440')),
    'badres_border': ({}, ('Resolution', '2560 1440')),
}


def ini_with(text, over):
    for (sec, key), val in over.items():
        m = re.search(r'(?ms)^\[%s\]\s*$(.*?)(?=^\[|\Z)' % re.escape(sec), text)
        body = m.group(1)
        if re.search(r'(?m)^%s\s*=' % re.escape(key), body):
            body2 = re.sub(r'(?m)^%s\s*=.*$' % re.escape(key), '%s=%s' % (key, val), body)
        else:
            body2 = body.rstrip('\r\n') + '\r\n%s=%s\r\n' % (key, val)
        text = text[:m.start(1)] + body2 + text[m.end(1):]
    return text


def setup_with(text, key, val):
    return re.sub(r'(?m)^(\s*%s:\s*).*$' % re.escape(key), lambda m: m.group(1) + val, text)


def main():
    os.makedirs(BK, exist_ok=True)
    for src, name in ((os.path.join(GAME, 'collapsefix.ini'), 'collapsefix.ini'), (SETUP, 'setup.ini')):
        if not os.path.exists(os.path.join(BK, name)):
            shutil.copyfile(src, os.path.join(BK, name))
    base = open(os.path.join(REPO, 'patch', 'collapsefix.ini'), encoding='utf-8', newline='').read()
    setup0 = open(os.path.join(BK, 'setup.ini'), encoding='latin-1', newline='').read()
    names = sys.argv[1:] or list(CASES)
    try:
        for name in names:
            over, sedit = CASES[name]
            with open(os.path.join(GAME, 'collapsefix.ini'), 'w', encoding='utf-8', newline='') as f:
                f.write(ini_with(base, over))
            with open(SETUP, 'w', encoding='latin-1', newline='') as f:
                f.write(setup_with(setup0, *sedit) if sedit else setup0)
            tag = 'RG_' + name
            subprocess.run(['uv', 'run', '--no-project', '--with', 'frida', 'python', '-I', RUN, '--tag', tag,
                            '--secs', str(SECS), '--no-probe', '--shots', '25'], cwd=os.path.dirname(RUN),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out = os.path.join(RUNS, tag)
            res = json.load(open(os.path.join(out, 'result.json'), encoding='utf-8'))
            glog = open(os.path.join(out, 'collapse.log'), encoding='latin-1').read() if os.path.exists(os.path.join(out, 'collapse.log')) else ''
            flog_p = os.path.join(out, 'collapsefix.log')
            flog = open(flog_p, encoding='utf-8', errors='replace').read() if os.path.exists(flog_p) else ''
            bad = [l for l in flog.splitlines() if re.search(r'SKIP|FAIL|not the expected', l)]
            print('=== %s: alive_at_end=%s end=%s dumps=%s display_done=%s hr=%s' % (
                name, res.get('alive_at_end'), res.get('end') or res.get('detached'), res.get('dumps'),
                'init display' in glog and 'done' in glog, res.get('create_device_hr')), flush=True)
            for l in flog.splitlines():
                if re.search(r'^(collapsefix |C-\d+ \w+.*: |ini: |\[\d+\] (C-05 alt_tab|C-55 d3d_counts|C-56|C-14 input|CreateDevice fullscreen|C-05 borderless window))', l):
                    print('   ' + l[:170])
            for l in bad:
                print('   !! ' + l[:170])
    finally:
        shutil.copyfile(os.path.join(BK, 'collapsefix.ini'), os.path.join(GAME, 'collapsefix.ini'))
        shutil.copyfile(os.path.join(BK, 'setup.ini'), SETUP)
        print('restored collapsefix.ini and setup.ini', flush=True)


main()
