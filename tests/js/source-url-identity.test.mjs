/**
 * Source merge identity (R31).
 *
 * Merging sources across runs must not collapse two different documents into
 * one because their path or query differ only in case, and citation numbers
 * must keep pointing at the document they were written for. Only the parts
 * that carry no meaning (scheme, host, fragment) are normalized, which is the
 * same contract as canonical_source_url in app/services/source_catalog.py.
 */

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

function boot() {
  return loadScripts(["static/js/sources.js"], {
    before(target) {
      target.App = { state: { set() {} } };
    },
  });
}

describe("evidence URL identity", () => {
  it("keeps sources apart that differ only in path or query case", () => {
    const { window } = boot();
    const first = window.App.prepareResponseSourcesForEvidence(
      "Upper [S1]",
      [{ id: "S1", url: "https://example.test/Report?key=AbC", title: "Upper" }],
      [],
    );
    const second = window.App.prepareResponseSourcesForEvidence(
      "Lower [S1]",
      [{ id: "S1", url: "https://example.test/report?key=abc", title: "Lower" }],
      first.evidenceSources,
    );

    expect(second.evidenceSources.map(source => source.url)).toEqual([
      "https://example.test/Report?key=AbC",
      "https://example.test/report?key=abc",
    ]);
    expect(first.markdown).toBe("Upper [1]");
    expect(second.markdown).toBe("Lower [2]");
    expect(second.sources).toEqual([
      { id: "S2", title: "Lower", url: "https://example.test/report?key=abc", provider: "" },
    ]);
  });

  it("keeps a trailing slash as part of the resource, like the backend", () => {
    const { window } = boot();
    const merged = window.App.prepareResponseSourcesForEvidence(
      "[S1] [S2]",
      [
        { id: "S1", url: "https://example.test/docs/", title: "Slash" },
        { id: "S2", url: "https://example.test/docs", title: "No slash" },
      ],
      [],
    );
    expect(merged.evidenceSources.length).toBe(2);
    expect(merged.markdown).toBe("[1] [2]");
  });

  it("still merges URLs that differ only in scheme/host case or fragment", () => {
    const { window } = boot();
    const first = window.App.prepareResponseSourcesForEvidence(
      "A [S1]",
      [{ id: "S1", url: "https://Example.TEST/Report?key=AbC#intro", title: "A" }],
      [],
    );
    const second = window.App.prepareResponseSourcesForEvidence(
      "B [S1]",
      [{ id: "S1", url: "HTTPS://example.test/Report?key=AbC", title: "B" }],
      first.evidenceSources,
    );

    expect(second.evidenceSources.length).toBe(1);
    expect(second.markdown).toBe("B [1]");
  });
});
