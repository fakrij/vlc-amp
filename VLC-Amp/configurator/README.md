# VLC Amp skin configurator (static page)

Builds one `VLC-Amp-NNN.vlt` in the browser: size (100 / 125 / 150 / 200 %, preselected from
`devicePixelRatio`), font (curated, or your own TTF / OTF file, embedded as `fonts/lcd.*`), dark / light,
an optional light + dark pair (`--pair`: the theme button switches; about twice the memory), primary and
secondary colour, preview, download.
No server and no build step: `source/build_skin.py` runs **unchanged** in Pyodide + Pillow (a Web Worker),
so the generator stays the single source of truth. The preview is the generator's own `--preview` image.
It builds the thin hi-fi skin (24 px strip, 620 x 676 px window, minimum width 490, video window with control panel
and extra row); the page offers no strip height or width option (use `--bar-height` / `--width` locally).

## Files
- `index.html`, `app.js` (UI), `worker.js` (Pyodide worker), `glue.py` (page glue, see below)
- `build_skin.py` + `fonts/DejaVu*` - copies of `../source/` (run `sync.sh` or `tools/sync-configurator.py` after EVERY generator change; the latter also verifies)
- `sync.sh` - dependency-free copy of the generator and the DejaVu files into this folder
- `fonts.json`, `fonts/` - the curated fonts and their licence texts
- `test/node-build.mjs` - headless check: same staging as the worker, under node
- `test/browser-test.mjs` - the page itself in Edge (puppeteer-core): single build, pair, own font

`glue.py` holds the normalisations from `tools/pyodide-spike/README.md`: BASIC text layout (Pyodide's
Pillow has no libraqm), zeroed and sorted tar / gzip metadata (reproducible `.vlt`), and it adds the
font's licence file to the `.vlt` (`fonts/LICENSE-<name>`). Same options give the same bytes.

## Fonts
DejaVu Sans Mono (default, generator ships its licence), JetBrains Mono, Roboto Mono (variable file, default
instance = Regular), Source Code Pro (OTF, unmodified: Reserved Font Name "Source"). Selection follows
`docs/font-notes.md`; all are monospace, so tabular digits are guaranteed. Adding a font: put the file and
its licence into `fonts/` and an entry into `fonts.json`.

## Versions
`worker.js` pins `PYODIDE_VERSION = "314.0.7"` (Python 3.14, Pillow 12.2.0) and loads Pyodide and its Pillow
package from `cdn.jsdelivr.net/pyodide/v314.0.7/full/`. Runtime and package must come from the same release;
change the constant to upgrade (and rerun the node check). First visit downloads about 7 MB (cached).

## Hosting
Live at **<https://fakrij.github.io/vlc-amp/>**. The workflow `.github/workflows/pages.yml` (at
the repository root) publishes only this folder to GitHub Pages on every push to `main` that touches it
(repository Settings > Pages > Source: GitHub Actions). It first checks that `build_skin.py` here is the
same as `../source/build_skin.py`, so run `sh configurator/sync.sh` (plain copy, no dependencies) or
`tools/sync-configurator.py` (same copy, then builds with the CLI and with the copy and compares) and commit both
after a generator change.

Needs HTTPS (Pages provides it) because module workers and `fetch` do not work from `file:`.
Local try-out: `python3 -m http.server -d configurator` and open `http://localhost:8000/`.

## Headless check
```
npm i pyodide@314.0.7
curl -O https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pillow-12.2.0-cp314-cp314-pyemscripten_2026_0_wasm32.whl
node test/node-build.mjs node_modules/pyodide pillow-*.whl <outdir> \
  '{"scale":1,"mode":"light","accent":"#ff8800","led":"#00ccff","font":"fonts/SourceCodePro-Regular.otf","licence":"fonts/LICENSE-SourceCodePro.md"}'
tools/vlc-test.sh start <outdir>/VLC-Amp-100.vlt
```
`tools/sync-configurator.py --pyodide node_modules/pyodide pillow-*.whl` does the build and compares it with a CLI build of the same options;
the two are byte-identical only when the CLI's Pillow is the same version as Pyodide's (12.2.0): another Pillow
can differ by +-1 in a few gradient pixels. Browser check (Windows Edge through puppeteer-core): start
`python3 -m http.server 8765` in `configurator/`, then `node test/browser-test.mjs` on Windows with `TBFONT` set (header of the file).
