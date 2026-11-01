#!/usr/bin/env python3
"""Regenerate the configurator's copy of the generator from source/build_skin.py and verify it.

  >>> RE-RUN THIS AFTER EVERY CHANGE TO source/build_skin.py (and commit configurator/). <<<

Why a copy exists: the page is a static folder (GitHub Pages) served from configurator/, so it cannot
fetch ../source/. The worker stages configurator/build_skin.py + configurator/fonts/DejaVu* into
Pyodide's virtual FS as /work/build_skin.py and /work/fonts/ (generator's HERE = its own folder).

Sync step (PATCHES below is the only place where the copy may differ from the source; it is empty
today: the generator already forces Layout.BASIC, writes a reproducible .vlt and runs unchanged under
Pyodide; the page's glue.py handles the rest, so no hand edits and no patches are needed):
  - configurator/build_skin.py        <- source/build_skin.py (+ PATCHES)
  - configurator/fonts/DejaVu*, LICENSE-DejaVu.txt <- source/fonts/

Verify step (non-zero exit on any difference):
  - runs source/build_skin.py and configurator/build_skin.py with identical options and compares every
    staged file (stage-*/ tree) and the .vlt byte for byte: bar 24 / 36 / 40 px x scale 1.0 / 1.5 with
    --themes midnight, plus --mode/--accent/--led (light, custom accent) and --pair at 24 px.
  - with --pyodide <pyodide-dir> <pillow-wheel> (see configurator/README.md "Headless check"): also builds
    the page's options through glue.py in Pyodide under node and compares the .vlt with the CLI build.
Dependency-free alternative for the copy step only: configurator/sync.sh (plain cp of the same files; with
the empty PATCHES list both give byte-identical results; the Pages workflow also checks the copy with cmp).
The Pyodide comparison is byte exact only against the same Pillow as Pyodide's (12.2.0).
Needs Pillow in the Python that runs this script (e.g. ~/.cache/titlebar-test/venv/bin/python).
"""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source")
CFG = os.path.join(ROOT, "configurator")
FONTS = ["DejaVuSansMono.ttf", "DejaVuSans-Bold.ttf", "LICENSE-DejaVu.txt"]
PATCHES = []   # list of (old, new) text replacements applied to the copy; each must match exactly once

CASES = [["--bar-height", str(h), "--scale", str(s), "--themes", "midnight"]
         for h in (24, 36, 40) for s in (1.0, 1.5)]
CASES += [["--mode", "light", "--accent", "#ff8800", "--led", "#00ccff"],
          ["--mode", "dark", "--accent", "#c8f060", "--pair", "--scale", "1.5"]]
PAGE_OPTS = {"scale": 1, "mode": "light", "accent": "#ff8800", "led": "#00ccff", "font": None, "licence": None}


def sync():
    text = open(os.path.join(SRC, "build_skin.py"), encoding="utf-8").read()
    for old, new in PATCHES:
        assert text.count(old) == 1, "patch does not match exactly once: %r" % old[:60]
        text = text.replace(old, new)
    with open(os.path.join(CFG, "build_skin.py"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    for f in FONTS:
        shutil.copy(os.path.join(SRC, "fonts", f), os.path.join(CFG, "fonts", f))
    print("synced configurator/build_skin.py (%d patches) and %d font files" % (len(PATCHES), len(FONTS)))


def run(script, args, out):
    r = subprocess.run([sys.executable, script] + args + ["--out", out], capture_output=True, text=True)
    if r.returncode:
        sys.exit("FAIL: %s %s\n%s" % (script, args, r.stderr[-800:]))


def tree(d):
    return sorted(os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(d) for f in fs)


def compare(a, b, label):
    fa, fb = tree(a), tree(b)
    bad = [f for f in fa if f not in fb] + [f for f in fb if f not in fa]
    bad += [f for f in fa if f in fb and not filecmp.cmp(os.path.join(a, f), os.path.join(b, f), shallow=False)]
    if bad:
        print("DIFF %s: %s" % (label, bad[:8]))
        return 1
    print("ok   %-60s %d files identical" % (label, len(fa)))
    return 0


def verify(pyodide):
    fails = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, args in enumerate(CASES):
            a, b = os.path.join(tmp, "src%d" % i), os.path.join(tmp, "cfg%d" % i)
            run(os.path.join(SRC, "build_skin.py"), args, a)
            run(os.path.join(CFG, "build_skin.py"), args, b)
            fails += compare(a, b, " ".join(args))
        if pyodide:
            fails += verify_pyodide(tmp, *pyodide)
    return fails


def verify_pyodide(tmp, pydir, wheel):
    cli = os.path.join(tmp, "pycli")
    o = PAGE_OPTS
    run(os.path.join(SRC, "build_skin.py"), ["--scale", "1", "--mode", o["mode"], "--accent", o["accent"],
                                             "--led", o["led"]], cli)
    out = os.path.join(tmp, "pyo")
    t = time.time()
    r = subprocess.run(["node", os.path.join(CFG, "test", "node-build.mjs"), pydir, wheel, out, json.dumps(o)],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("FAIL pyodide build:\n" + r.stderr[-800:])
    print("pyodide build:", r.stdout.strip(), "(%.1f s incl. start-up)" % (time.time() - t))
    same = filecmp.cmp(os.path.join(cli, "VLC-Amp-100.vlt"), os.path.join(out, "VLC-Amp-100.vlt"), shallow=False)
    print(("ok   " if same else "DIFF ") + "pyodide .vlt vs CLI .vlt (page options)")
    if not same:
        print("     note: Pyodide ships Pillow 12.2.0; a different Pillow in this Python can change single pixels"
              " (+-1) in gradient bitmaps, which is not a generator difference. Compare with the same Pillow.")
    return 0 if same else 1


if __name__ == "__main__":
    pyodide = None
    if "--pyodide" in sys.argv:
        i = sys.argv.index("--pyodide")
        pyodide = (os.path.abspath(sys.argv[i + 1]), os.path.abspath(sys.argv[i + 2]))
    sync()
    n = verify(pyodide)
    print("FAILED: %d difference(s)" % n if n else "all identical")
    sys.exit(1 if n else 0)
