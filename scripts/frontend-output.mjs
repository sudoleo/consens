// Publish complete files before switching the manifest. A running server must
// never observe truncated assets or a manifest pointing at deleted bundles.
import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";

const BUNDLE = /^([a-z][a-z0-9-]*)\.[a-f0-9]{12}\.(js|css)$/;

export async function writeAtomicIfChanged(target, content) {
  const bytes = Buffer.isBuffer(content) ? content : Buffer.from(content);
  const current = await fs.readFile(target).catch(error => {
    if (error.code !== "ENOENT") throw error;
    return null;
  });
  if (current?.equals(bytes)) return;
  await fs.mkdir(path.dirname(target), { recursive: true });
  const temporary = `${target}.${randomUUID()}.tmp`;
  try {
    await fs.writeFile(temporary, bytes, { flag: "wx" });
    await fs.rename(temporary, target);
  } finally {
    await fs.rm(temporary, { force: true });
  }
}

export async function previousAssets(dist, outputs) {
  const old = await fs.readFile(path.join(dist, "manifest.json"), "utf8").then(JSON.parse).catch(error => {
    if (error.code !== "ENOENT") throw error;
    return {};
  });
  const candidates = [
    ...(old.scripts || []).map(item => item.src),
    ...Object.values(old.styles || {}),
    ...(old.previous_assets || []).map(name => `/static/dist/${name}`),
  ];
  const groups = new Set([...outputs.keys()].map(name => {
    const match = name.match(BUNDLE);
    return match && `${match[1]}.${match[2]}`;
  }));
  const retained = new Map();
  for (const url of candidates) {
    if (typeof url !== "string" || !url.startsWith("/static/dist/")) continue;
    const name = url.slice("/static/dist/".length);
    const match = name.match(BUNDLE);
    if (!match || outputs.has(name)) continue;
    const key = `${match[1]}.${match[2]}`;
    const versions = retained.get(key) || [];
    if (!groups.has(key) || versions.length >= 2 || versions.includes(name)) continue;
    if ((await fs.stat(path.join(dist, name)).catch(() => null))?.isFile()) {
      retained.set(key, [...versions, name]);
    }
  }
  // Keep newest-first order within each group for the next rollover.
  return [...retained.entries()].sort(([a], [b]) => a.localeCompare(b)).flatMap(([, names]) => names);
}

export async function publishBuild(dist, outputs, manifest) {
  for (const [name, content] of outputs) {
    if (!BUNDLE.test(name)) throw new Error(`Invalid bundle filename: ${name}`);
    await writeAtomicIfChanged(path.join(dist, name), content);
  }
  await writeAtomicIfChanged(path.join(dist, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  // Retain two prior versions per JS/CSS group, including identical rebuilds.
  // Only prune known bundle basenames inside dist, after the manifest switch.
  const keep = new Set([...outputs.keys(), ...(manifest.previous_assets || [])]);
  for (const name of await fs.readdir(dist)) {
    if (BUNDLE.test(name) && !keep.has(name)) await fs.rm(path.join(dist, name));
  }
}
