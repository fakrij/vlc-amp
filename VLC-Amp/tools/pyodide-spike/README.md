# Pyodide spike (BACKLOG T17 step 2 / item 24)

Question: can `source/build_skin.py` run **unchanged** in Pyodide + Pillow and produce the
same `.vlt` as a native build? Answer: yes, byte-identical, once two environment differences are
neutralised in a wrapper (`harness.py`), not in the generator. Spike only: node, no browser, no page.

## Files
- `run.mjs` - node: load Pyodide + Pillow wheel, copy `build_skin.py` + `fonts/` into the virtual FS,
  run it through `harness.py` (`--themes midnight`, one theme), read the `.vlt` bytes back out of the FS.
- `harness.py` - runs `build_skin.py` via `runpy`; same file for native and Pyodide (see Obstacles).
- `compare.py`, `pixdiff.py`, `features.mjs`, `textprobe.py` - diagnosis helpers.

Run (versions used: Pyodide 314.0.7 = Python 3.14.2, Pillow 12.2.0; native Python 3.12 + `pillow==12.2.0`):
```
npm i pyodide@314.0.7 ; curl -O https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pillow-12.2.0-cp314-cp314-pyemscripten_2026_0_wasm32.whl
node run.mjs node_modules/pyodide pillow-*.whl <repo> <outdir> <scale>
python harness.py source/build_skin.py 1 --scale <scale> --themes midnight --out <dir>   # native
```

## Results (WSL2 Linux, node 24, Pyodide read from local disk; timings noisy, machine was loaded)
Byte-identical native vs Pyodide at scales 1, 1.5, 2 (sha256 equal; `VLC-Amp-100/150/200.vlt` =
252010 / 276234 / 296056 bytes).

Download (brotli transfer from jsDelivr; raw in brackets): `pyodide.asm.wasm` 3.44 MB (9.6),
`python_stdlib.zip` 2.51 (2.5), `pyodide.asm.mjs` 0.26 (1.25), Pillow wheel 1.03 (1.04),
`pyodide.mjs` + lock 0.03 => **about 7.3 MB** (14.4 MB raw). Less than the 10-15 MB assumed in item 24.
`build_skin.py` + fonts add ~1.1 MB (fonts only if shipped uncompressed; DejaVu is also needed in the `.vlt`).

Load (local files, so no network): Pyodide start 1.4-2.1 s, Pillow unpack + import 0.17-0.25 s.
Add download time on top (7.3 MB: ~1 s at 60 Mbit/s; the browser caches it).

Build time per scale (single theme, Pyodide / native CPython 3.12 + Pillow, same machine):
| scale | Pyodide first run | Pyodide second run | native |
|---|---|---|---|
| 1   | 1.7-2.3 s | 1.2-1.6 s | 1.8-2.2 s |
| 1.5 | 3.0-3.9 s | 2.6-3.2 s | 3.8-4.5 s |
| 2   | 4.9-6.2 s | 4.4-5.3 s | 7.3-9.3 s |
So wasm is about as fast as native here (this build is dominated by pure-Python drawing). Build must go in a Web Worker so the page stays responsive.

## Obstacles (generator NOT modified; what a browser version needs)
1. **Text rendering differs without a wrapper.** Native Pillow wheels ship libraqm, Pyodide's does not
   (FreeType 2.14.3 + raqm vs 2.13.3 basic layout). Result: `atlas_t0.png` and `t0_eq_bands.png` differ in
   ~2.7k opaque pixels (glyphs only, RGB delta up to 196; shapes, resizing and alpha identical).
   With `ImageFont.Layout.BASIC` native output equals Pyodide's exactly. `harness.py` forces BASIC via a
   wrapper on `ImageFont.truetype`. Consequence: for the configurator, Pyodide *is* the renderer; a native
   build only matches if forced to BASIC. Suggested generator patch (not applied): pass
   `layout_engine=ImageFont.Layout.BASIC` in the `ImageFont.truetype` calls, so every environment agrees.
2. **tar/gzip metadata is not reproducible.** `tarfile.add` stores file mtime, uid/gid/uname and mode
   (Emscripten FS: 777/666, owner root) and gzip stores `time.time()`. Even two native runs differ. The harness
   zeroes these (`TarFile.addfile` wrapper + `time.time = 0`). Suggested patch: a `filter=` on `tar.add`
   and `gzip.GzipFile(mtime=0)` (open with `fileobj`) in the generator. Irrelevant for VLC; only for byte comparisons / caching.
3. Member order comes from `os.walk` (directory order, not sorted); it matched here, but sort `dirs` to make it guaranteed.
4. `build_skin.py` calls `argparse` / `sys.exit`: run via `runpy.run_path(..., run_name="__main__")` and
   catch `SystemExit`. `HERE` is `__file__`-relative, so fonts must sit at `<dir>/fonts` in the virtual FS.
5. Node-only quirk: `py.unpackArchive` rejects a Buffer; wrap it in `new Uint8Array(...)`. In a browser use
   `pyodide.loadPackage("pillow")` instead.
6. Pyodide's CDN has Pillow only for its own Python ABI; pin the Pyodide version (wheel and runtime must match).
7. Not tested: browsers, `--font/--mode/--accent/--led` (do not exist yet), memory use.

## Update (T24): generator patched
`source/build_skin.py` now forces `Layout.BASIC`, zeroes tar / gzip metadata and sorts members itself.
`node run.mjs ... <scale> 0` (no wrapper) gives a `.vlt` byte-identical to a native build with the same
Pillow version (checked at scale 1, Pillow 12.2.0: sha256 equal). `harness.py` is no longer needed for that.
