"use strict";
const $ = (id) => document.getElementById(id);
const SCALES = [1, 1.25, 1.5, 2];
let fonts = [];
let worker = null, ready = false, nextId = 0, current = 0, result = null, previewUrl = null;

function defaultScale() {
  const d = window.devicePixelRatio || 1;
  return SCALES.reduce((a, b) => Math.abs(b - d) < Math.abs(a - d) ? b : a);
}

function status(text, cls) {
  const s = $("status");
  s.textContent = text;
  s.className = cls || "";
}

function options() {
  const f = fonts.find(x => x.id === $("font").value);
  return { scale: parseFloat($("size").value), mode: document.querySelector("input[name=mode]:checked").value,
           accent: $("accent").value, led: $("led").value, font: f.file, licence: f.licence };
}

function refreshNote() {
  const o = options();
  const n = "Titlebar-" + Math.round(o.scale * 100) + ".vlt";
  $("filename").textContent = n;
  const f = fonts.find(x => x.id === $("font").value);
  $("fontnote").textContent = f.note;
}

function build() {
  if (!ready) return;
  const id = ++nextId;
  current = id;
  $("build").disabled = true;
  $("download").disabled = true;
  status("Building (a few seconds, up to about 10 s at 200 %)...");
  worker.postMessage({ type: "build", id, opts: options() });
}

function onMessage(ev) {
  const m = ev.data;
  if (m.type === "status") status(m.text);
  else if (m.type === "ready") { ready = true; $("build").disabled = false; status("Ready."); build(); }
  else if (m.type === "fatal") status("Could not start: " + m.text + " (needs a current browser and internet access to jsDelivr)", "err");
  else if (m.id !== current) return;           // stale result
  else if (m.type === "error") { $("build").disabled = false; status("Build failed:\n" + m.text, "err"); }
  else if (m.type === "done") {
    result = m;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(new Blob([m.preview], { type: "image/png" }));
    $("preview").src = previewUrl;
    $("preview").hidden = false;
    $("build").disabled = false;
    $("download").disabled = false;
    $("download").textContent = "Download " + m.name;
    status("Done in " + (m.ms / 1000).toFixed(1) + " s: " + m.name + " (" + (m.vlt.length / 1048576).toFixed(1) + " MB).");
  }
}

function download() {
  if (!result) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([result.vlt], { type: "application/gzip" }));
  a.download = result.name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
}

async function main() {
  fonts = await (await fetch("fonts.json")).json();
  $("font").innerHTML = fonts.map(f => `<option value="${f.id}">${f.name}</option>`).join("");
  $("size").value = String(defaultScale());
  for (const id of ["size", "font"]) $(id).addEventListener("change", refreshNote);
  $("build").addEventListener("click", build);
  $("download").addEventListener("click", download);
  refreshNote();
  $("build").disabled = true;
  worker = new Worker("worker.js", { type: "module" });
  worker.onmessage = onMessage;
  worker.onerror = (e) => status("Worker error: " + e.message, "err");
}
main().catch(e => status("Error: " + e.message, "err"));
