"""Page glue for the configurator: runs build_skin.py UNCHANGED (runpy) inside Pyodide.

Normalisations kept here, not in the generator (see tools/pyodide-spike/README.md):
  - Pyodide's Pillow has no libraqm: force ImageFont.Layout.BASIC so text renders the same everywhere.
  - tar / gzip metadata (mtime, owner, mode) is zeroed and members are sorted: reproducible .vlt.
Also adds the font's licence file to the .vlt (build_skin.py only ships DejaVu's own).

Files in the virtual FS: /work/build_skin.py, /work/fonts/... (as next to this page).
"""
import json
import os
import runpy
import shutil
import sys
import tarfile
import time

WORK = "/work"
OUT = WORK + "/out"


def _zero(ti):
    ti.mtime = 0
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = ""
    ti.mode = 0o755 if ti.isdir() else 0o644
    return ti


def build(opts_json):
    """opts: scale, mode, accent, led, font (path in /work or null), licence (path or null).
    Returns JSON {name, vlt, preview} (paths in the virtual FS)."""
    o = json.loads(opts_json)
    from PIL import ImageFont
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    args = ["--scale", str(o["scale"]), "--mode", o["mode"], "--accent", o["accent"],
            "--led", o["led"], "--preview", "--out", OUT]
    if o.get("pair"):
        args.append("--pair")
    if o.get("font"):
        args += ["--font", WORK + "/" + o["font"]]
    saved = (ImageFont.truetype, time.time)
    _tt = ImageFont.truetype

    def truetype(*a, **k):
        k.setdefault("layout_engine", ImageFont.Layout.BASIC)
        return _tt(*a, **k)

    ImageFont.truetype = truetype
    time.time = lambda: 0.0                     # gzip header mtime
    old_argv = sys.argv
    sys.argv = [WORK + "/build_skin.py"] + args
    try:
        try:
            runpy.run_path(WORK + "/build_skin.py", run_name="__main__")
        except SystemExit as e:
            if e.code not in (None, 0):
                raise RuntimeError("build_skin.py exited with %r" % (e.code,))
        stage = [d for d in os.listdir(OUT) if d.startswith("stage-")][0]
        name = stage[len("stage-"):]
        stage = os.path.join(OUT, stage)
        if o.get("licence"):
            shutil.copy(WORK + "/" + o["licence"], os.path.join(stage, "fonts"))
        vlt = "%s/VLC-Amp-%s.vlt" % (OUT, name)
        with tarfile.open(vlt, "w:gz") as tar:   # same layout as the generator's, sorted + zeroed
            for root, dirs, files in os.walk(stage):
                dirs.sort()
                for fn in sorted(files):
                    full = os.path.join(root, fn)
                    tar.add(full, arcname=os.path.relpath(full, stage), filter=_zero)
    finally:
        sys.argv = old_argv
        ImageFont.truetype, time.time = saved
    return json.dumps({"name": "VLC-Amp-%s.vlt" % name, "vlt": vlt,
                       "preview": "%s/preview-%s.png" % (OUT, name)})
