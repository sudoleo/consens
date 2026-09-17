// Ship the pinned browser libraries with the app, including KaTeX's relative
// font URLs and upstream licenses. Production does not need npm or a CDN.
import fs from "node:fs/promises";
import path from "node:path";

export async function vendorFrontend(root, checkOnly) {
  const packages = {
    marked: ["marked.min.js", "LICENSE.md"],
    dompurify: ["dist/purify.min.js", "LICENSE"],
    katex: ["dist/katex.min.js", "dist/katex.min.css", "dist/contrib/auto-render.min.js", "LICENSE"],
  };
  const pins = JSON.parse(await fs.readFile(path.join(root, "package.json"), "utf8")).devDependencies;
  const inputs = [];
  for (const [name, files] of Object.entries(packages)) {
    const source = path.join(root, "node_modules", name);
    const { version } = JSON.parse(await fs.readFile(path.join(source, "package.json"), "utf8"));
    if (version !== pins[name]) throw new Error(`Unexpected ${name} version: ${version}`);
    if (name === "katex") {
      files.push(...(await fs.readdir(path.join(source, "dist/fonts"))).sort().map(file => `dist/fonts/${file}`));
    }
    for (const file of files) {
      const relative = `static/vendor/${name}/${version}/${file}`;
      const target = path.join(root, relative);
      const bytes = await fs.readFile(path.join(source, file));
      if (checkOnly) {
        const current = await fs.readFile(target).catch(() => null);
        if (!current?.equals(bytes)) throw new Error(`${relative} is stale. Run: npm run build`);
      } else {
        await fs.mkdir(path.dirname(target), { recursive: true });
        await fs.writeFile(target, bytes);
      }
      inputs.push(relative);
    }
  }
  return inputs;
}
