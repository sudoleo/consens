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

    // A column of numbers with gaps is a column of numbers.
    expect(output.querySelectorAll("th")[2].classList.contains("is-numeric")).toBe(true);
    expect(cells[2][2].className).toBe("is-numeric is-blank");
    expect(cells[3][2].className).toBe("is-numeric is-blank");
    expect(cells[0][2].className).toBe("is-numeric");
    // Dashes among words are words.
    expect(output.querySelectorAll("th")[3].classList.contains("is-numeric")).toBe(false);
    expect(cells[0][3].className).toBe("");
    expect(cells[3][3].className).toBe("");
  });
});
