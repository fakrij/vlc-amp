// node run.mjs <pyodide-dir> <pillow-wheel> <repo-root> <outdir> <scale> [normalize=1]
// Loads Pyodide + Pillow, runs source/build_skin.py unchanged, writes the .vlt to <outdir>.
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { join } from "node:path";

const [pyDir, wheel, repo, outDir, scale = "1", norm = "1"] = process.argv.slice(2);
const t0 = performance.now();
const { loadPyodide } = await import(pathToFileURL(join(pyDir, "pyodide.mjs")));
const py = await loadPyodide({ indexURL: pyDir });
const t1 = performance.now();
// a wheel is a zip: unpack it into site-packages (what loadPackage does after downloading it)
py.unpackArchive(new Uint8Array(readFileSync(wheel)), "wheel");   // Buffer is rejected
py.runPython("from PIL import Image, ImageDraw, ImageFont, ImageChops");
const t2 = performance.now();

// stage generator + fonts + harness in the virtual FS
py.FS.mkdirTree("/work/source/fonts");
py.FS.writeFile("/work/source/build_skin.py", readFileSync(join(repo, "source/build_skin.py")));
for (const f of readdirSync(join(repo, "source/fonts")))
  py.FS.writeFile("/work/source/fonts/" + f, readFileSync(join(repo, "source/fonts", f)));
py.FS.writeFile("/work/harness.py", readFileSync(new URL("./harness.py", import.meta.url)));

const times = [];
for (let i = 0; i < 2; i++) {            // 1st = cold (imports), 2nd = warm
  const t = performance.now();
  py.globals.set("ARGS", ["/work/source/build_skin.py", norm, "--scale", scale,
    "--themes", "midnight", "--out", "/work/out"]);
  try {
    py.runPython("import sys,runpy\nsys.argv=['harness.py']+list(ARGS.to_py())\n" +
      "runpy.run_path('/work/harness.py',run_name='__main__')");
  } catch (e) { console.error("BUILD FAILED:", String(e.message).slice(-1500)); process.exit(1); }
  times.push(performance.now() - t);
}
const name = py.FS.readdir("/work/out").find(n => n.endsWith(".vlt"));
const bytes = py.FS.readFile("/work/out/" + name);
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, name), bytes);
console.log(JSON.stringify({ name, bytes: bytes.length, load_pyodide_ms: Math.round(t1 - t0),
  load_pillow_ms: Math.round(t2 - t1), build_cold_ms: Math.round(times[0]),
  build_warm_ms: Math.round(times[1]) }));
