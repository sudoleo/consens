import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// The shapes an answer draws from what a model already writes
// (markdown-stream.js): figures, bars, steps.
function render(html) {
  const { window, document } = loadScripts(["static/js/markdown-stream.js"], {
    before(win) {
      win.marked = { parse: vi.fn(() => html) };
      win.DOMPurify = { sanitize: vi.fn(value => value) };
    },
  });
  const output = document.createElement("div");
  window.injectMarkdown(output, "answer");
  return output;
}

const table = (head, rows) => `<table><thead><tr>${head.map(cell => `<th>${cell}</th>`).join("")}</tr></thead><tbody>${
  rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
const widths = output => Array.from(output.querySelectorAll(".md-bar > i")).map(fill => fill.style.width);

describe("Figures", () => {
  it("shows a table of one row as its values over their headings", () => {
    const output = render(table(["After subsidy", "Per year", "Pays off after"], [["17.600 €", "1.380 €", "11 Jahre"]]));

    expect(output.querySelector("table")).toBeNull();
    const groups = output.querySelectorAll("dl.md-figures > div");
    expect(groups).toHaveLength(3);
    expect(groups[2].querySelector("dt").textContent).toBe("Pays off after");
    expect(groups[2].querySelector("dd").textContent).toBe("11 Jahre");
  });

  it("leaves a row of sentences, a single cell and a row without numbers as a table", () => {
    expect(render(table(["A", "B"], [["A long sentence that explains 1 thing", "2"]])).querySelector(".md-figures")).toBeNull();
    expect(render(table(["A"], [["12"]])).querySelector(".md-figures")).toBeNull();
    expect(render(table(["A", "B"], [["yes", "no"]])).querySelector(".md-figures")).toBeNull();
    expect(render(table(["A", "B"], [["1", "2"], ["3", "4"]])).querySelector(".md-figures")).toBeNull();
  });
});

describe("Bars", () => {
  it("measures each amount against the largest of its column, in either number convention", () => {
    const german = render(table(["Heating", "Per year"], [["Gas", "2.150 €"], ["Air", "1.075 €"], ["Ground", "537,50 €"]]));
    expect(widths(german)).toEqual(["100%", "50%", "25%"]);
    expect(german.querySelector("th:last-child").classList.contains("is-numeric")).toBe(true);

    const english = render(table(["Plan", "Price"], [["A", "$2,000.00"], ["B", "$1,000"], ["C", "$500.5"]]));
    expect(widths(english)).toEqual(["100%", "50%", "25%"]);
  });

  it("gives label and one amount the row form and several amounts a bar each", () => {
    const one = render(table(["Heating", "Per year"], [["Gas", "2.150 €"], ["Air", "1.380 €"], ["Ground", "1.090 €"]]));
    expect(one.querySelector("table").classList.contains("md-bar-rows")).toBe(true);
    expect(one.querySelector("table").style.getPropertyValue("--md-bar-amount")).toBe("8ch");

    const two = render(table(["Heating", "Buy", "CO₂"], [["Gas", "12.000 €", "4,6 t"], ["Air", "32.000 €", "1,5 t"], ["Ground", "45.000 €", "1,1 t"]]));
    expect(two.querySelector("table").classList.contains("md-bar-rows")).toBe(false);
    expect(two.querySelectorAll(".md-bar")).toHaveLength(6);
  });

  it("draws nothing for years, running numbers, mixed units, text or fewer than three rows", () => {
    expect(widths(render(table(["Event", "Year"], [["A", "1999"], ["B", "2008"], ["C", "2020"]])))).toEqual([]);
    expect(widths(render(table(["Name", "Rank"], [["A", "1"], ["B", "2"], ["C", "3"]])))).toEqual([]);
    expect(widths(render(table(["Name", "Size"], [["A", "3 kg"], ["B", "2 m"], ["C", "5 kg"]])))).toEqual([]);
    expect(widths(render(table(["Name", "Note"], [["A", "about 3"], ["B", "2"], ["C", "5"]])))).toEqual([]);
    expect(widths(render(table(["Name", "Size"], [["A", "3 kg"], ["B", "2 kg"]])))).toEqual([]);
    expect(widths(render(table(["Name", "Change"], [["A", "-3 %"], ["B", "2 %"], ["C", "5 %"]])))).toEqual([]);
  });

  it("leaves a last row that sums the others without a bar", () => {
    const output = render(table(["Item", "Cost"], [["A", "100 €"], ["B", "300 €"], ["C", "200 €"], ["Total", "600 €"]]));

    expect(widths(output)).toEqual(["33.3%", "100%", "66.7%"]);
    expect(output.querySelector("tbody tr:last-child .md-bar")).toBeNull();
  });
});

describe("Steps", () => {
  it("puts a numbered list of titled items on a rail and keeps its start", () => {
    const output = render('<ol start="3"><li><strong>Ask.</strong> Three offers.</li><li><p><b>Apply.</b> Before you sign.</p></li></ol>');
    const list = output.querySelector("ol");

    expect(list.classList.contains("md-steps")).toBe(true);
    expect(list.style.counterReset).toBe("md-step 2");
  });

  it("leaves plain, partly titled and all-bold lists and bullet lists alone", () => {
    expect(render("<ol><li>One</li><li>Two</li></ol>").querySelector(".md-steps")).toBeNull();
    expect(render("<ol><li><strong>One.</strong> Text</li><li>Two</li></ol>").querySelector(".md-steps")).toBeNull();
    expect(render("<ol><li><strong>Only bold</strong></li></ol>").querySelector(".md-steps")).toBeNull();
    expect(render("<ol><li>Then <strong>bold</strong> later</li></ol>").querySelector(".md-steps")).toBeNull();
    expect(render("<ul><li><strong>One.</strong> Text</li></ul>").querySelector(".md-steps")).toBeNull();
  });
});
