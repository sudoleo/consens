// Ship the pinned browser libraries with the app, including KaTeX's relative
// font URLs and upstream licenses. Production does not need npm or a CDN.
import fs from "node:fs/promises";
import path from "node:path";
import { writeAtomicIfChanged } from "./frontend-output.mjs";

// Every file below a package folder, sorted, as paths relative to the package.
async function filesBelow(source, folder) {
  const found = [];
  for (const entry of (await fs.readdir(path.join(source, folder), { withFileTypes: true }))
    .sort((a, b) => a.name.localeCompare(b.name))) {
    const relative = `${folder}/${entry.name}`;
    if (entry.isDirectory()) found.push(...await filesBelow(source, relative));
    else found.push(relative);
  }
  return found;
}

export async function vendorFrontend(root, checkOnly) {
  const packages = {
    marked: ["marked.min.js", "LICENSE.md"],
    dompurify: ["dist/purify.min.js", "LICENSE"],
    katex: ["dist/katex.min.js", "dist/katex.min.css", "dist/contrib/auto-render.min.js", "LICENSE"],
    // The workspace's live view (workspace-view.js): ES modules, imported
    // from core/rfb.js only when the view opens, with their relative imports.
    "@novnc/novnc": ["LICENSE.txt"],
  };
  // Where a package lands under static/vendor (a scope's @ stays out of URLs).
  const folders = { "@novnc/novnc": "novnc" };
  const pins = JSON.parse(await fs.readFile(path.join(root, "package.json"), "utf8")).devDependencies;
  const inputs = [];
  for (const [name, files] of Object.entries(packages)) {
    const source = path.join(root, "node_modules", name);
    const { version } = JSON.parse(await fs.readFile(path.join(source, "package.json"), "utf8"));
    if (version !== pins[name]) throw new Error(`Unexpected ${name} version: ${version}`);
    if (name === "katex") {
      files.push(...(await fs.readdir(path.join(source, "dist/fonts"))).sort().map(file => `dist/fonts/${file}`));
    }
    if (name === "@novnc/novnc") {
      files.push(...await filesBelow(source, "core"), ...await filesBelow(source, "vendor"));
    }
    for (const file of files) {
      const relative = `static/vendor/${folders[name] || name}/${version}/${file}`;
      const target = path.join(root, relative);
      const bytes = await fs.readFile(path.join(source, file));
      if (checkOnly) {
        const current = await fs.readFile(target).catch(() => null);
        if (!current?.equals(bytes)) throw new Error(`${relative} is stale. Run: npm run build`);
      } else {
        await writeAtomicIfChanged(target, bytes);
      }
      inputs.push(relative);
    }
  }
  return inputs;
}
