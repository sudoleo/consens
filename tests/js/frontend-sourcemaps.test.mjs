import { afterEach, describe, expect, it } from "vitest";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import * as esbuild from "esbuild";

import {
  concatenationLayout,
  decodeMappings,
  decodeVlq,
  encodeVlq,
  normalizeBundleMap,
  remapConcatenated,
} from "../../scripts/frontend-sourcemaps.mjs";
import { publishBuild } from "../../scripts/frontend-output.mjs";

const directories = [];
afterEach(async () => {
  for (const dir of directories.splice(0)) await fs.rm(dir, { recursive: true, force: true });
});

// Resolve one generated position the way app/core/sourcemaps.py does.
function lookup(map, line, column) {
  const segments = decodeMappings(map.mappings)[line - 1] || [];
  let found = null;
  for (const segment of segments) {
    if (segment[0] <= column - 1) found = segment;
  }
  return found && { source: map.sources[found[1]], line: found[2] + 1, column: found[3] + 1 };
}

describe("frontend source maps", () => {
  it("round-trips VLQ values including negatives and large columns", () => {
    const values = [0, 1, -1, 15, -16, 31, 32, 1_000_000, -123_456];
    expect(decodeVlq(encodeVlq(values))).toEqual(values);
    expect(decodeVlq("AAgBC")).toEqual([0, 0, 16, 1]);
    expect(() => decodeVlq("g")).toThrow();
  });

  it("maps a minified concatenation back onto the original files", async () => {
    // CRLF and a template literal with a real newline: both shift lines.
    const files = [
      { file: "static/js/first.js", content: "function alpha(value) {\r\n  return value + 1;\r\n}\r\n" },
      { file: "static/js/second.js", content: "const text = `a\nb`;\nfunction betaFailure(input) {\n  return input.missing.property;\n}\n" },
    ];
    const source = files.map(({ file, content }) => `/* ${file} */\n${content}\n;`).join("\n");
    const result = await esbuild.transform(source, {
      minify: true, keepNames: true, target: "es2020", legalComments: "none",
      sourcemap: "external", sourcefile: "app.concat.js", sourcesContent: false,
    });
    const map = remapConcatenated(JSON.parse(result.map), concatenationLayout(files), "app.x.js");
    expect(map.sources).toEqual(["static/js/first.js", "static/js/second.js"]);

    const lines = result.code.split("\n");
    const line = lines.findIndex((text) => text.includes("function betaFailure"));
    const column = lines[line].indexOf("function betaFailure") + 1;
    // Line 3: the template literal spans lines 1-2 of second.js.
    expect(lookup(map, line + 1, column)).toEqual({ source: "static/js/second.js", line: 3, column: 1 });

    const alphaLine = lines.findIndex((text) => text.includes("function alpha"));
    const alpha = lookup(map, alphaLine + 1, lines[alphaLine].indexOf("function alpha") + 1);
    expect(alpha).toEqual({ source: "static/js/first.js", line: 1, column: 1 });
  });

  it("normalizes bundle map sources to repository paths", () => {
    const map = normalizeBundleMap({ version: 3, sources: ["../firebase.js", "..\\js\\x.js"],
      names: ["n"], mappings: "AAAA,EAAEA" }, "static/dist", "firebase.abc.js");
    expect(map.sources).toEqual(["static/firebase.js", "static/js/x.js"]);
    expect(map.names).toEqual([]);
    expect(decodeMappings(map.mappings)).toEqual([[[0, 0, 0, 0], [2, 0, 0, 2]]]);
  });

  it("publishes maps next to their bundles and prunes them with the bundle", async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "consensio-map-test-"));
    directories.push(dir);
    const publish = async (digit, previous) => {
      const name = `app.${digit.repeat(12)}.js`;
      await publishBuild(dir, new Map([[name, "code"], [`${name}.map`, "{}"]]),
        { scripts: [{ name: "app", src: `/static/dist/${name}` }], styles: {}, previous_assets: previous });
      return name;
    };
    const first = await publish("1", []);
    const second = await publish("2", [first]);
    expect((await fs.readdir(dir)).sort()).toEqual(
      [first, `${first}.map`, second, `${second}.map`, "manifest.json"].sort());
    await publish("3", [second]);
    const names = await fs.readdir(dir);
    expect(names).not.toContain(first);
    expect(names).not.toContain(`${first}.map`);
    expect(names).toContain(`${second}.map`);
    await expect(publishBuild(dir, new Map([["app.444444444444.js.map", "{}"]]), {})).rejects.toThrow();
  });
});
