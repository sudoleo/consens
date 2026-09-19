import { afterEach, describe, expect, it } from "vitest";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { previousAssets, publishBuild, writeAtomicIfChanged } from "../../scripts/frontend-output.mjs";

const directories = [];
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
