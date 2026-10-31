// node features.mjs <pyodide-dir> <pillow-wheel>: print Pillow's compiled-in library versions inside Pyodide
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const [pyDir, wheel] = process.argv.slice(2);
const { loadPyodide } = await import(pathToFileURL(join(pyDir, "pyodide.mjs")));
const py = await loadPyodide({ indexURL: pyDir });
py.unpackArchive(new Uint8Array(readFileSync(wheel)), "wheel");
if (process.argv[5]) {                   // optional: also run a probe script (arg3 = repo root, arg4 = file)
  py.FS.mkdirTree("/work/source/fonts");
  py.FS.writeFile("/work/source/fonts/DejaVuSansMono.ttf",
    new Uint8Array(readFileSync(join(process.argv[4], "source/fonts/DejaVuSansMono.ttf"))));
  py.globals.set("PROBE", readFileSync(process.argv[5], "utf8"));
  py.runPython("exec(compile(PROBE,'probe','exec'))");
}
console.log(py.runPython(`
import PIL
from PIL import features
"Python %s | Pillow %s | freetype %s | zlib %s | libpng %s | raqm %s | simd %s" % (
    __import__("sys").version.split()[0], PIL.__version__, features.version("freetype2"),
    features.version("zlib"), features.version("libpng"), features.check("raqm"), features.version("libimagequant"))
`));
