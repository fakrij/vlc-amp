"""Runs source/build_skin.py UNCHANGED via runpy, with optional deterministic tar/gzip metadata.

usage: harness.py <build_skin.py> <normalize 0|1> <build_skin args...>
The same file is used natively and inside Pyodide so both builds see identical wrapping.
"""
import runpy
import sys
import tarfile
import time

script, norm, args = sys.argv[1], sys.argv[2] == "1", sys.argv[3:]
if norm:
    time.time = lambda: 0.0                      # gzip header mtime
    _add = tarfile.TarFile.addfile

    def addfile(self, ti, fileobj=None):         # tar header: mtime / owner
        ti.mtime = 0
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = ""
        ti.mode = 0o755 if ti.isdir() else 0o644   # Emscripten FS uses 777 / 666
        return _add(self, ti, fileobj)

    tarfile.TarFile.addfile = addfile
    # Pyodide's Pillow has no libraqm; native wheels do and then lay text out differently.
    # Force the basic layout engine so both sides rasterise glyphs identically.
    from PIL import ImageFont
    _tt = ImageFont.truetype

    def truetype(*a, **k):
        k.setdefault("layout_engine", ImageFont.Layout.BASIC)
        return _tt(*a, **k)

    ImageFont.truetype = truetype
sys.argv = [script] + args
try:
    runpy.run_path(script, run_name="__main__")
except SystemExit as e:
    if e.code not in (None, 0):
        raise
