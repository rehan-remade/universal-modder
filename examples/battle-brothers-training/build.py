#!/usr/bin/env python3
"""Build mod_training_grounds-<version>.zip from mod/ (dist/ next to this file).

    python build.py            # build
    python build.py --install "C:/path/to/Battle Brothers/data"   # also copy the zip there
Optionally set SQ=<path to a Squirrel 3.x sq executable> to syntax-check every .nut first.
"""
import os, re, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "mod")


def version():
    text = open(os.path.join(SRC, "scripts", "!mods_preload", "mod_training_grounds.nut"), encoding="utf-8").read()
    return re.search(r'Version = "([^"]+)"', text).group(1)


def main():
    files = []
    for root, _, names in os.walk(SRC):
        for n in sorted(names):
            files.append(os.path.join(root, n))
    sq = os.environ.get("SQ")
    if sq:
        for f in [x for x in files if x.endswith('.nut')]:
            r = subprocess.run([sq, "-c", f], capture_output=True, text=True, cwd=HERE)
            if r.returncode != 0 or "rror" in r.stdout + r.stderr:
                sys.exit("syntax error in %s\n%s%s" % (f, r.stdout, r.stderr))
    out_dir = os.path.join(HERE, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "mod_training_grounds-%s.zip" % version())
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files):
            z.write(f, os.path.relpath(f, SRC).replace(os.sep, "/"))
    print(out)
    if "--install" in sys.argv:
        dest = sys.argv[sys.argv.index("--install") + 1]
        shutil.copy2(out, dest)
        print("copied to", dest)


if __name__ == "__main__":
    main()
