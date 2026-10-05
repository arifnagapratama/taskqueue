// Run with node tests/markdown-field.test.mjs; requires installed Chromium.
// Set CHROMIUM_PATH if Chromium is outside the locations below.
import { build } from "esbuild";
import { compile } from "svelte/compiler";
import { readFile, writeFile, mkdtemp, rm, access, readdir } from "node:fs/promises";
import { tmpdir, homedir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { execFile } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cache = join(homedir(), ".cache/ms-playwright");
const cachedBrowsers = (await readdir(cache).catch(() => []))
  .filter(name => name.startsWith("chromium-"))
  .flatMap(name => [join(cache, name, "chrome-linux64/chrome"), join(cache, name, "chrome-linux/chrome")]);
const candidates = [process.env.CHROMIUM_PATH, ...cachedBrowsers,
  "/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chromium-browser"].filter(Boolean);
let chromium;
for (const candidate of candidates) {
  try { await access(candidate); chromium = candidate; break; } catch {}
}
if (!chromium) throw new Error("Chromium required; set CHROMIUM_PATH");
const directory = await mkdtemp(join(tmpdir(), "markdown-field-test-"));
try {
  await build({
    entryPoints: [join(root, "tests/markdown-field.browser.js")],
    outfile: join(directory, "test.js"), bundle: true, format: "iife", platform: "browser",
    conditions: ["browser"], plugins: [{ name: "svelte", setup(builder) {
      builder.onLoad({ filter: /\.svelte$/ }, async ({ path }) => ({
        contents: compile(await readFile(path, "utf8"), { filename: path, generate: "client" }).js.code,
        resolveDir: dirname(path),
      }));
    }}],
  });
  await writeFile(join(directory, "index.html"), '<!doctype html><html><body><script src="test.js"></script></body></html>');
  const { stdout } = await promisify(execFile)(chromium, ["--headless", "--no-sandbox", "--disable-gpu",
    "--dump-dom", "--virtual-time-budget=10000", `file://${join(directory, "index.html")}`], { maxBuffer: 1024 * 1024, timeout: 30000 });
  const result = stdout.match(/(?:PASS|FAIL):[^<]+/)?.[0];
  console.log(result || stdout);
  if (!result?.startsWith("PASS:")) process.exitCode = 1;
} finally {
  await rm(directory, { recursive: true, force: true });
}
