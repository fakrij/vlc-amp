// node node-build.mjs <pyodide-dir> <pillow-wheel> <outdir> '<opts json>'
// Same staging as worker.js, but from local files: runs the page's glue.py + build_skin.py in Pyodide.
// opts: {"scale":1,"mode":"dark","accent":"#5fd3e8","led":"#ffb347","font":"fonts/..."|null,"licence":...|null}
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { pathToFileURL, fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const [pyDir, wheel, outDir, optsJson] = process.argv.slice(2);
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const { loadPyodide } = await import(pathToFileURL(join(pyDir, "pyodide.mjs")));
const py = await loadPyodide({ indexURL: pyDir });
py.unpackArchive(new Uint8Array(readFileSync(wheel)), "wheel");   // node: no CDN loadPackage

const opts = JSON.parse(optsJson);
const files = ["build_skin.py", "glue.py", "fonts/DejaVuSansMono.ttf", "fonts/DejaVuSans-Bold.ttf",
  "fonts/LICENSE-DejaVu.txt", opts.font, opts.licence].filter(Boolean);
py.FS.mkdirTree("/work/fonts");
for (const f of files) py.FS.writeFile("/work/" + f, new Uint8Array(readFileSync(join(root, f))));
py.runPython("import sys; sys.path.insert(0, '/work')\nimport glue");
py.globals.set("OPTS", optsJson);
const t = performance.now();
const res = JSON.parse(py.runPython("glue.build(OPTS)"));
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, res.name), py.FS.readFile(res.vlt));
writeFileSync(join(outDir, "preview.png"), py.FS.readFile(res.preview));
console.log(JSON.stringify({ name: res.name, ms: Math.round(performance.now() - t) }));
