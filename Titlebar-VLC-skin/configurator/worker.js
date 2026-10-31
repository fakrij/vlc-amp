// Web Worker: Pyodide + Pillow, runs build_skin.py (unchanged) through glue.py.
// Pinned versions: the Pyodide runtime and its Pillow package must match (see README.md).
const PYODIDE_VERSION = "314.0.7";
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";

let py = null;
const staged = new Set();

function post(msg) { self.postMessage(msg); }

async function stage(path) {            // fetch a file next to the page into /work/<path>
  if (staged.has(path)) return;
  const r = await fetch(path);
  if (!r.ok) throw new Error("cannot fetch " + path + " (" + r.status + ")");
  const data = new Uint8Array(await r.arrayBuffer());
  const dir = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
  if (dir) py.FS.mkdirTree("/work/" + dir);
  py.FS.writeFile("/work/" + path, data);
  staged.add(path);
}

async function init() {
  post({ type: "status", text: "Loading Python (about 7 MB, cached by the browser)..." });
  const { loadPyodide } = await import(PYODIDE_URL + "pyodide.mjs");
  py = await loadPyodide({ indexURL: PYODIDE_URL });
  post({ type: "status", text: "Loading Pillow..." });
  await py.loadPackage("pillow");
  py.FS.mkdirTree("/work/fonts");
  for (const f of ["build_skin.py", "glue.py", "fonts/DejaVuSansMono.ttf", "fonts/DejaVuSans-Bold.ttf",
                   "fonts/LICENSE-DejaVu.txt"]) await stage(f);
  py.runPython("import sys; sys.path.insert(0, '/work')\nimport glue");
  post({ type: "ready" });
}

async function build(id, opts, fontData) {
  try {
    if (fontData) {                       // the user's own font: /work/fonts/own.ttf (or .otf), no licence file
      const ext = /\.otf$/i.test(opts.ownFont || "") ? "otf" : "ttf";
      opts.font = "fonts/own." + ext;
      py.FS.writeFile("/work/" + opts.font, fontData);
    }
    if (opts.font && !fontData) await stage(opts.font);
    if (opts.licence) await stage(opts.licence);
    py.globals.set("OPTS", JSON.stringify(opts));
    const t = performance.now();
    const res = JSON.parse(py.runPython("glue.build(OPTS)"));
    const vlt = py.FS.readFile(res.vlt);
    const preview = py.FS.readFile(res.preview);
    post({ type: "done", id, name: res.name, vlt, preview, ms: Math.round(performance.now() - t) },
         [vlt.buffer, preview.buffer]);
  } catch (e) {
    post({ type: "error", id, text: String(e.message || e).split("\n").slice(-6).join("\n") });
  }
}

const ready = init().catch(e => post({ type: "fatal", text: String(e.message || e) }));
self.onmessage = async (ev) => {
  await ready;
  if (py && ev.data.type === "build") await build(ev.data.id, ev.data.opts, ev.data.fontData);
};
