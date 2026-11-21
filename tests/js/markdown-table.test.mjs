import { beforeEach, describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const TABLE_HTML = `
  <table>
    <thead><tr><th>Stage</th><th>Subject</th><th>Units</th></tr></thead>
    <tbody>
      <tr><td>1</td><td>Rendering fundamentals</td><td>8</td></tr>
      <tr><td>2</td><td>Information design</td><td>11</td></tr>
      <tr><td>Total</td><td></td><td>19</td></tr>
    </tbody>
  </table>`;

function boot(html = TABLE_HTML) {
  return loadScripts(["static/js/markdown-stream.js"], {
    before(window) {
      window.marked = { parse: vi.fn(() => html) };
      window.DOMPurify = { sanitize: vi.fn(value => value) };
    },
  });
}

describe("Markdown tables", () => {
  let window;
  let document;

  beforeEach(() => {
    ({ window, document } = boot());
  });

  it("keeps the semantic table inside an accessible scroll region", () => {
    const output = document.createElement("div");
    window.injectMarkdown(output, "| Stage | Subject | Units |");

    const wrapper = output.querySelector(".markdown-table-wrap");
    const table = wrapper?.querySelector("table.markdown-table");

    expect(wrapper).not.toBeNull();
    expect(wrapper.getAttribute("role")).toBe("region");
    expect(wrapper.getAttribute("aria-label")).toBe("Table: Stage, Subject, Units");
    expect(wrapper.tabIndex).toBe(0);
    expect(table?.querySelectorAll("thead th")).toHaveLength(3);
  });

  it("aligns predominantly numeric columns without changing text columns", () => {
    const output = document.createElement("div");
    window.injectMarkdown(output, "table");

    const headings = output.querySelectorAll("th");
    const firstRow = output.querySelector("tbody tr");
    const totalRow = output.querySelector("tbody tr:last-child");

    expect(headings[0].classList.contains("is-numeric")).toBe(true);
    expect(headings[1].classList.contains("is-numeric")).toBe(false);
    expect(headings[2].classList.contains("is-numeric")).toBe(true);
    expect(firstRow.cells[0].classList.contains("is-numeric")).toBe(true);
    expect(firstRow.cells[2].classList.contains("is-numeric")).toBe(true);
    expect(totalRow.cells[0].classList.contains("is-numeric")).toBe(false);
    expect(totalRow.cells[2].classList.contains("is-numeric")).toBe(true);
  });

  // Left-aligned, the dash of a row without a value sat at the far side of
  // its column, beside the number of the column before.
  it("stands a dash for a missing value where the numbers of its column stand", () => {
    const row = cells => `<tr>${cells.map(cell => `<td>${cell}</td>`).join("")}</tr>`;
    const { window: win, document: doc } = boot(`<table><thead><tr><th>Benchmark</th><th>Ours</th><th>Theirs</th><th>Note</th></tr></thead><tbody>${
      row(["Terminal", "48,5", "67,2", "–"])}${row(["Program", "31,5", "65,0", "fine"])}${
      row(["Exam", "51,7", "–", "words"])}${row(["Work", "52,69", "—", "-"])}</tbody></table>`);
    const output = doc.createElement("div");
    win.injectMarkdown(output, "table");
    const cells = Array.from(output.querySelectorAll("tbody tr")).map(line => Array.from(line.cells));

    const marks = cell => ["is-numeric", "is-blank"].filter(name => cell.classList.contains(name)).join(" ");
    // A column of numbers with gaps is a column of numbers.
    expect(output.querySelectorAll("th")[2].classList.contains("is-numeric")).toBe(true);
    expect(marks(cells[2][2])).toBe("is-numeric is-blank");
    expect(marks(cells[3][2])).toBe("is-numeric is-blank");
    expect(marks(cells[0][2])).toBe("is-numeric");
    // Dashes among words are words.
    expect(output.querySelectorAll("th")[3].classList.contains("is-numeric")).toBe(false);
    expect(marks(cells[0][3])).toBe("");
    expect(marks(cells[3][3])).toBe("");
  });

  // With a floor of a sentence's width under every cell, "Rang" and "93"
  // took a sixth of the answer each and the last column was cut off.
  it("marks the cells short enough to need no room of their own", () => {
    const row = cells => `<tr>${cells.map(cell => `<td>${cell}</td>`).join("")}</tr>`;
    const { window: win, document: doc } = boot(`<table><thead><tr><th>Rang</th><th>Versicherer</th><th>Überschuss / Ergebnis 2025</th></tr></thead><tbody>${
      row(["1", "<strong>HUK-Coburg</strong>", "621 Mio. €, +78 %"])}${
      row(["2", "Generali  DE", ""])}${
      row(["3", "308 % Gruppe", "756 Mio. € adj. Nettogewinn"])}</tbody></table>`);
    const output = doc.createElement("div");
    win.injectMarkdown(output, "table");
    const short = Array.from(output.querySelectorAll("tr"))
      .map(line => Array.from(line.cells).map(cell => cell.classList.contains("is-short")));

    expect(short).toEqual([
      [true, true, false],
      // A number, a name in bold, and a phrase of seventeen characters.
      [true, true, false],
      // Spaces count once, and an empty cell needs nothing.
      [true, true, true],
      // Twelve characters are still short.
      [true, true, false],
    ]);
  });

  // A table wider than the answer pans in its place; the side it goes on to
  // fades out, and no side fades where nothing is hidden.
  it("says on which side a panning table goes on", () => {
    const output = document.createElement("div");
    window.injectMarkdown(output, "table");
    const wrapper = output.querySelector(".markdown-table-wrap");
    const sides = () => ["is-cut-start", "is-cut-end"].filter(name => wrapper.classList.contains(name));
    const pan = (left, width = 900) => {
      Object.defineProperty(wrapper, "clientWidth", { configurable: true, value: 700 });
      Object.defineProperty(wrapper, "scrollWidth", { configurable: true, value: width });
      wrapper.scrollLeft = left;
      wrapper.dispatchEvent(new window.Event("scroll"));
    };

    pan(0);
    expect(sides()).toEqual(["is-cut-end"]);
    pan(120);
    expect(sides()).toEqual(["is-cut-start", "is-cut-end"]);
    pan(200);
    expect(sides()).toEqual(["is-cut-start"]);
    pan(0, 700);
    expect(sides()).toEqual([]);
  });
});
