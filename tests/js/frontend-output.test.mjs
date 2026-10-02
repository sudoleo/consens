import { afterEach, describe, expect, it } from "vitest";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { promisify } from "node:util";
import { previousAssets, publishBuild, writeAtomicIfChanged } from "../../scripts/frontend-output.mjs";

const directories = [];
const execute = promisify(execFile);
async function workspace() {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "consensio-build-test-"));
  directories.push(dir);
  return dir;
}
afterEach(async () => {
  for (const dir of directories.splice(0)) await fs.rm(dir, { recursive: true, force: true });
});

async function build(dir, digit) {
  const name = `app.${digit.repeat(12)}.js`;
  const outputs = new Map([[name, `/* version ${digit} */`]]);
  const manifest = { scripts: [{ name: "app", src: `/static/dist/${name}` }], styles: {},
    previous_assets: await previousAssets(dir, outputs) };
  await publishBuild(dir, outputs, manifest);
  return { name, outputs, manifest };
}

describe("frontend publishing", () => {
  it("preserves manifest and content-hashed asset bytes in an autocrlf checkout", async () => {
    const dir = await workspace();
    const dist = path.join(dir, "static", "dist");
    const hash = (bytes) => createHash("sha256").update(bytes).digest("hex").slice(0, 12);
    const script = "window.checkoutProof = true;\n";
    const style = "body{color:#123456}\n";
    const scriptName = `app.${hash(script)}.js`;
    const styleName = `app.${hash(style)}.css`;
    const outputs = new Map([[scriptName, script], [styleName, style]]);
    const manifest = { scripts: [{ name: "app", src: `/static/dist/${scriptName}` }],
      styles: { app: `/static/dist/${styleName}` }, previous_assets: [] };
    await publishBuild(dist, outputs, manifest);
    const manifestBytes = await fs.readFile(path.join(dist, "manifest.json"));
    await fs.copyFile(new URL("../../.gitattributes", import.meta.url), path.join(dir, ".gitattributes"));
    await fs.writeFile(path.join(dir, "source-control.txt"), "ordinary source\nsecond line\n");
    const emptyAttributes = path.join(dir, "empty-attributes");
    await fs.writeFile(emptyAttributes, "");
    const git = (...args) => execute("git", ["-c", `safe.directory=${dir}`,
      "-c", "core.autocrlf=true", "-c", "core.safecrlf=false",
      "-c", `core.attributesFile=${emptyAttributes}`, ...args], {
      cwd: dir, env: { ...process.env, GIT_ATTR_NOSYSTEM: "1" },
    });
    await git("init", "--quiet");
    await git("add", "--", ".gitattributes", "static/dist", "source-control.txt");
    // Force a real checkout from the index; untouched working files would hide
    // Git's LF -> CRLF conversion. No global Git setting or real build changes.
    for (const name of [...outputs.keys(), "manifest.json"]) await fs.unlink(path.join(dist, name));
    await fs.unlink(path.join(dir, "source-control.txt"));
    await git("checkout-index", "--all", "--force");
    expect(await fs.readFile(path.join(dir, "source-control.txt"), "utf8"))
      .toBe("ordinary source\r\nsecond line\r\n");
    expect.soft(await fs.readFile(path.join(dist, "manifest.json"))).toEqual(manifestBytes);
    for (const [name, content] of outputs) {
      const checkedOut = await fs.readFile(path.join(dist, name));
      expect.soft(checkedOut).toEqual(Buffer.from(content));
      expect.soft(name).toContain(`.${hash(checkedOut)}.`);
    }
  }, 15000);

  it("preserves two previous versions and does not age them out on identical rebuilds", async () => {
    const dir = await workspace();
    const first = await build(dir, "1");
    const second = await build(dir, "2");
    const third = await build(dir, "3");
    expect(third.manifest.previous_assets).toEqual([second.name, first.name]);
    const same = await build(dir, "3");
    expect(same.manifest).toEqual(third.manifest);
    const fourth = await build(dir, "4");
    expect(fourth.manifest.previous_assets).toEqual([third.name, second.name]);
    await expect(fs.access(path.join(dir, first.name))).rejects.toThrow();
    for (const name of [second.name, third.name, fourth.name]) {
      expect((await fs.readFile(path.join(dir, name), "utf8")).length).toBeGreaterThan(0);
    }
  });

  it("does not truncate or rewrite unchanged vendor and bundle files", async () => {
    const dir = await workspace();
    const target = path.join(dir, "vendor.js");
    await writeAtomicIfChanged(target, "unchanged");
    const oldTime = new Date("2020-01-01T00:00:00Z");
    await fs.utimes(target, oldTime, oldTime);
    await writeAtomicIfChanged(target, "unchanged");
    expect((await fs.stat(target)).mtimeMs).toBe(oldTime.getTime());
    await writeAtomicIfChanged(target, "replacement");
    expect(await fs.readFile(target, "utf8")).toBe("replacement");
    expect(await fs.readdir(dir)).toEqual(["vendor.js"]);
  });

  it("leaves the old manifest and assets readable when publication fails", async () => {
    const dir = await workspace();
    const first = await build(dir, "1");
    await expect(publishBuild(dir, new Map([["invalid.js", "bad"]]), {})).rejects.toThrow();
    expect(JSON.parse(await fs.readFile(path.join(dir, "manifest.json"), "utf8"))).toEqual(first.manifest);
    expect(await fs.readFile(path.join(dir, first.name), "utf8")).toBe("/* version 1 */");
  });

  it("never prunes unrelated files and ignores untrusted retention paths", async () => {
    const dir = await workspace();
    const first = await build(dir, "1");
    await fs.writeFile(path.join(dir, "notes.txt"), "keep");
    first.manifest.previous_assets = ["../outside.js", "/absolute.js"];
    await writeAtomicIfChanged(path.join(dir, "manifest.json"), JSON.stringify(first.manifest));
    const next = await build(dir, "2");
    expect(next.manifest.previous_assets).toEqual([first.name]);
    expect(await fs.readFile(path.join(dir, "notes.txt"), "utf8")).toBe("keep");
  });
});
