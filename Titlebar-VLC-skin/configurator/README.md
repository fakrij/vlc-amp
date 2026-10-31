# Titlebar configurator (static page)

Builds one `Titlebar-NNN.vlt` in the browser: size (100 / 125 / 150 / 200 %, preselected from
`devicePixelRatio`), font, dark / light, primary and secondary colour, preview, download.
No server and no build step: `source/build_skin.py` runs **unchanged** in Pyodide + Pillow (a Web Worker),
so the generator stays the single source of truth. The preview is the generator's own `--preview` image.

## Files
- `index.html`, `app.js` (UI), `worker.js` (Pyodide worker), `glue.py` (page glue, see below)
- `build_skin.py` + `fonts/DejaVu*` - copies of `../source/` (run `./sync.sh` after the generator changes)
- `fonts.json`, `fonts/` - the curated fonts and their licence texts
- `test/node-build.mjs` - headless check: same staging as the worker, under node

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

## Host on GitHub Pages
Pages serves a static folder, so either:
- Settings > Pages > Deploy from a branch > `main`, folder `/` and the page is at
  `https://<user>.github.io/<repo>/Titlebar-VLC-skin/configurator/`; or
- publish only this folder (for example copy it to a `gh-pages` branch root, or use a GitHub Actions
  "upload-pages-artifact" step with `path: Titlebar-VLC-skin/configurator`).

Needs HTTPS (Pages provides it) because module workers and `fetch` do not work from `file:`.
Local try-out: `python3 -m http.server -d configurator` and open `http://localhost:8000/`.

## Headless check
```
npm i pyodide@314.0.7
curl -O https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pillow-12.2.0-cp314-cp314-pyemscripten_2026_0_wasm32.whl
node test/node-build.mjs node_modules/pyodide pillow-*.whl <outdir> \
  '{"scale":1,"mode":"light","accent":"#ff8800","led":"#00ccff","font":"fonts/SourceCodePro-Regular.otf","licence":"fonts/LICENSE-SourceCodePro.md"}'
tools/vlc-test.sh start <outdir>/Titlebar-100.vlt
```
