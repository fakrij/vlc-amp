// Headless browser check of the page (Windows node + Edge, puppeteer-core): single build, light + dark pair,
// own font upload. From WSL start `python3 -m http.server 8765` in configurator/, then on Windows:
//   npm i puppeteer-core ; $env:TBFONT='C:\\path\\font.ttf' ; node browser-test.mjs
import puppeteer from "puppeteer-core";
const b = await puppeteer.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: "new", args: ["--no-sandbox"] });
const p = await b.newPage();
p.on("console", m => console.log("console:", m.text()));
p.on("pageerror", e => console.log("pageerror:", e.message));
await p.goto("http://localhost:8765/index.html");
await p.waitForFunction(() => /Done in|failed|Could not/.test(document.getElementById("status").textContent), { timeout: 90000 });
console.log("status:", await p.$eval("#status", e => e.textContent));
await p.click("#pair");
await p.click("#build");
await p.waitForFunction(() => /Done in|failed/.test(document.getElementById("status").textContent) && !document.getElementById("build").disabled, { timeout: 90000 });
console.log("pair status:", await p.$eval("#status", e => e.textContent));
const fontPath = process.env.TBFONT;
const inp = await p.$("#fontfile");
await inp.uploadFile(fontPath);
await new Promise(r => setTimeout(r, 500));
console.log("fontnote:", await p.$eval("#fontnote", e => e.textContent));
await p.click("#build");
await p.waitForFunction(() => /Done in|failed/.test(document.getElementById("status").textContent) && !document.getElementById("build").disabled, { timeout: 90000 });
console.log("own font status:", await p.$eval("#status", e => e.textContent));
await b.close();
