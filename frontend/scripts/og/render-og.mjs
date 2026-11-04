#!/usr/bin/env node
// Render 1200x630 PNGs from HTML files with headless Chrome.
// Usage: node render-og.mjs <in.html> <out.png> [<in2.html> <out2.png> ...]
import { execFileSync } from "node:child_process";
import { mkdtempSync, existsSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const candidates = [
  process.env.CHROME_BIN,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium-browser",
].filter(Boolean);
const chrome = candidates.find((c) => existsSync(c));
if (!chrome) { console.error("No Chrome found. Set CHROME_BIN."); process.exit(1); }

const args = process.argv.slice(2);
if (args.length < 2 || args.length % 2) { console.error("usage: render-og.mjs in.html out.png [...]"); process.exit(1); }
for (let i = 0; i < args.length; i += 2) {
  const input = path.resolve(args[i]);
  const output = path.resolve(args[i + 1]);
  const profile = mkdtempSync(path.join(tmpdir(), "og-chrome-"));
  try {
    execFileSync(chrome, [
      "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
      `--user-data-dir=${profile}`, "--window-size=1200,630", "--force-device-scale-factor=1",
      "--virtual-time-budget=10000", "--run-all-compositor-stages-before-draw",
      `--screenshot=${output}`, `file://${input}`,
    ], { stdio: ["ignore", "ignore", "pipe"], timeout: 60000 });
    console.log(`${path.basename(output)}  ${Math.round(statSync(output).size / 1024)} KB`);
  } finally { rmSync(profile, { recursive: true, force: true }); }
}
