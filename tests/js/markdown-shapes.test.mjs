import { readFileSync } from "node:fs";

import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// The shapes an answer draws from what a model already writes
// (answer-shapes.js through markdown-stream.js): figures, two sides, a
// timeline, bars with the row the answer points to, steps.
function load(html) {
  return loadScripts(["static/js/answer-shapes.js", "static/js/markdown-stream.js"], {
    before(win) {
      win.marked = { parse: vi.fn(() => html) };
      win.DOMPurify = { sanitize: vi.fn(value => value) };
    },
  });
}

function render(html) {
  const { window, document } = load(html);
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
    expect(output.querySelector(".md-figures").classList.contains("is-long")).toBe(false);
  });

  it("gives long values the smaller size", () => {
    const output = render(table(["Market", "Users"], [["1.234.567.890 €", "4,2 Mio."]]));
    expect(output.querySelector(".md-figures").classList.contains("is-long")).toBe(true);
  });

  it("leaves a row of sentences, a single cell and a row without numbers as a table", () => {
    expect(render(table(["A", "B"], [["A long sentence that explains 1 thing", "2"]])).querySelector(".md-figures")).toBeNull();
    expect(render(table(["A"], [["12"]])).querySelector(".md-figures")).toBeNull();
    expect(render(table(["A", "B"], [["yes", "no"]])).querySelector(".md-figures")).toBeNull();
    expect(render(table(["A", "B"], [["1", "2"], ["3", "4"]])).querySelector(".md-figures")).toBeNull();
  });
});

describe("Two sides", () => {
  const pros = ["Running costs about a third below gas", "The subsidy covers almost half the purchase", "No risk from a rising CO₂ price"];
  const cons = ["Even after the subsidy dearer than a gas boiler", "The outdoor unit needs room and can be heard", ""];

  it("draws two text columns of unrelated points as two named lists, empty cells left out", () => {
    const output = render(table(["For", "Against"], pros.map((pro, index) => [pro, cons[index]])));

    expect(output.querySelector("table")).toBeNull();
    const sides = output.querySelectorAll(".md-facing > .md-facing-side");
    expect(sides).toHaveLength(2);
    expect(sides[0].querySelector(".md-facing-head").textContent).toBe("For");
    expect(sides[0].querySelectorAll("li")).toHaveLength(3);
    expect(sides[1].querySelectorAll("li")).toHaveLength(2);
    // Each list is named by its side's heading, as the column header named the cells.
    const list = sides[1].querySelector("ul");
    expect(output.querySelector(`#${list.getAttribute("aria-labelledby")}`).textContent).toBe("Against");
  });

  it("keeps the words and marks of a cell", () => {
    const output = render(table(["Buy", "Rent"], [
      ["You build <strong>wealth</strong> over the years", "You can move whenever the job asks for it"],
      ["Nobody can give you notice to leave", "No repairs and no <a href=\"https://example.com\">roof</a> to pay for"],
    ]));
    expect(output.querySelector(".md-facing li strong").textContent).toBe("wealth");
    expect(output.querySelector(".md-facing li a").getAttribute("href")).toBe("https://example.com");
  });

  it("keeps a table of labels and their meaning, rows that are pairs", () => {
    // Short labels against long explanations.
    expect(render(table(["Aspect", "What it means"], [
      ["Noise", "About 45 dB at five metres, like a quiet conversation"],
      ["Room", "One square metre outside and a small cabinet inside"],
      ["Maintenance", "One check a year, done in under an hour by a technician"],
    ])).querySelector(".md-facing")).toBeNull();
    // Labels in bold throughout, however long.
    expect(render(table(["Aspect", "What it means"], [
      ["<strong>Running costs per year</strong>", "Around a third below a gas boiler of the same size"],
      ["<strong>Space it takes outside</strong>", "About one square metre beside the wall of the house"],
    ])).querySelector(".md-facing")).toBeNull();
    // A column of questions is answered across the row.
    expect(render(table(["Question", "Answer"], [
      ["Do I need underfloor heating for it?", "No, radiators often reach 55 °C with ease"],
      ["Does it work in an old house at all?", "Yes, when the heat load has been measured first"],
    ])).querySelector(".md-facing")).toBeNull();
  });

  it("keeps short words, amounts, three columns and a single row", () => {
    expect(render(table(["For", "Against"], [["Cheap", "Loud"], ["Quick", "Big"]])).querySelector(".md-facing")).toBeNull();
    expect(render(table(["Option", "Price"], [["The first of the offers we got", "12.000 €"], ["The second of the offers we got", "14.000 €"]]))
      .querySelector(".md-facing")).toBeNull();
    expect(render(table(["A", "B", "C"], [[pros[0], cons[0], pros[1]], [pros[1], cons[1], pros[2]]])).querySelector(".md-facing")).toBeNull();
    expect(render(table(["For", "Against"], [[pros[0], cons[0]]])).querySelector(".md-facing")).toBeNull();
  });

  it("draws the border case on each side of the length rule", () => {
    // The shorter column's typical cell just reaches half of the other's.
    const half = "x".repeat(20), full = "y".repeat(40), less = "z".repeat(19);
    expect(render(table(["A", "B"], [[half, full], [half, full]])).querySelector(".md-facing")).not.toBeNull();
    expect(render(table(["A", "B"], [[less, full], [less, full]])).querySelector(".md-facing")).toBeNull();
    // 16 characters are a statement; 15 are not, unless a side has fewer points.
    const sixteen = "s".repeat(16), fifteen = "f".repeat(15);
    expect(render(table(["A", "B"], [[sixteen, sixteen], [sixteen, sixteen]])).querySelector(".md-facing")).not.toBeNull();
    expect(render(table(["A", "B"], [[fifteen, fifteen], [fifteen, fifteen]])).querySelector(".md-facing")).toBeNull();
    expect(render(table(["A", "B"], [[fifteen, fifteen], [fifteen, ""]])).querySelector(".md-facing")).not.toBeNull();
  });
});

describe("Timeline", () => {
  it("puts a table of dates and events on the rail and keeps it a table", () => {
    const output = render(table(["Year", "What changed"], [
      ["2020", "The bonus for replacing oil boilers starts."],
      ["2023", "The heating law is passed."],
      ["2024", "The new subsidy of up to 70 % applies."],
    ]));
    const timeline = output.querySelector("table.md-timeline");
    expect(timeline).not.toBeNull();
    expect(timeline.querySelector("thead").textContent).toContain("Year");
    expect(output.querySelector(".md-bar")).toBeNull();
  });

  it("reads dates in any order and language from their digits", () => {
    const rows = dates => dates.map(date => [date, "Something happened then."]);
    for (const dates of [
      ["März 2020", "Mai 2023", "Jan. 2024"],
      ["12.03.2020", "1.5.2023", "30.11.2024"],
      ["2020-03-12", "2023-05", "2024-11-30"],
      ["3/12/2020", "5/1/2023", "11/30/2024"],
      ["12. März", "1. Mai", "30. Nov."],
      ["09:00", "12:30", "17:45"],
      ["Q1 2024", "Q3 2024", "Q2 2025"],
      ["2019–2021", "seit 2022", "1990s"],
      ["March 12, 2020", "May 1, 2023", "Nov 30, 2024"],
    ]) {
      expect(render(table(["When", "What"], rows(dates))).querySelector(".md-timeline"), dates.join(" | ")).not.toBeNull();
    }
  });

  it("keeps quantities, running numbers, labels, amounts and short tables", () => {
    const rows = (dates, text = "Something happened then.") => dates.map(date => [date, text]);
    expect(render(table(["Height", "What grows"], rows(["1500 m", "2000 m", "2500 m"]))).querySelector(".md-timeline")).toBeNull();
    expect(render(table(["Dose", "Effect"], rows(["1000", "1500", "2000"]))).querySelector(".md-timeline")).toBeNull();
    expect(render(table(["Step", "What"], rows(["1", "2", "3"]))).querySelector(".md-timeline")).toBeNull();
    expect(render(table(["Section", "What"], rows(["3.1", "3.2", "3.3"]))).querySelector(".md-timeline")).toBeNull();
    expect(render(table(["Day", "What"], rows(["Day 1", "Day 2", "Day 3"]))).querySelector(".md-timeline")).toBeNull();
    expect(render(table(["Year", "Revenue"], rows(["2021", "2022", "2023"], "1.200 €"))).querySelector(".md-timeline")).toBeNull();
    expect(render(table(["Year", "What"], rows(["2021", "2022"]))).querySelector(".md-timeline")).toBeNull();
    expect(render(table(["Year", "What", "Where"], [["2021", "a", "b"], ["2022", "a", "b"], ["2023", "a", "b"]]))
      .querySelector(".md-timeline")).toBeNull();
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

  it("aligns a column with a typographic minus as numbers, without bars", () => {
    const output = render(table(["Since", "Deposit rate"], [["2020", "−0,50 %"], ["2022", "0,75 %"], ["2023", "4,00 %"]]));
    expect(output.querySelector("tbody td:last-child").classList.contains("is-numeric")).toBe(true);
    expect(widths(output)).toEqual([]);
  });

  it("leaves a last row that sums the others without a bar", () => {
    const output = render(table(["Item", "Cost"], [["A", "100 €"], ["B", "300 €"], ["C", "200 €"], ["Total", "600 €"]]));

    expect(widths(output)).toEqual(["33.3%", "100%", "66.7%"]);
    expect(output.querySelector("tbody tr:last-child .md-bar")).toBeNull();
  });

  it("points to the one row whose label is bold throughout", () => {
    const output = render(table(["Heating", "Per year"], [
      ["Ground", "1.090 €"], ["<strong>Air</strong>", "1.380 €"], ["Pellets", "1.620 €"], ["Gas", "2.150 €"],
    ]));
    const picked = output.querySelectorAll("tr.md-pick");
    expect(picked).toHaveLength(1);
    expect(picked[0].cells[0].textContent).toBe("Air");
  });

  it("points to nothing with several bold rows, a partly bold label, a bold total or no bars", () => {
    const pick = html => render(html).querySelector("tr.md-pick");
    expect(pick(table(["H", "Y"], [["<strong>A</strong>", "1 €"], ["<strong>B</strong>", "2 €"], ["C", "3 €"]]))).toBeNull();
    expect(pick(table(["H", "Y"], [["<strong>Air</strong> pump", "1 €"], ["B", "2 €"], ["C", "3 €"]]))).toBeNull();
    expect(pick(table(["H", "Y"], [["A", "100 €"], ["B", "300 €"], ["C", "200 €"], ["<strong>Total</strong>", "600 €"]]))).toBeNull();
    expect(pick(table(["H", "Y"], [["<strong>A</strong>", "x"], ["B", "y"], ["C", "z"]]))).toBeNull();
  });
});

describe("Steps", () => {
  it("puts a numbered list of titled items on a rail and keeps its start", () => {
    const output = render('<ol start="3"><li><strong>Ask.</strong> Three offers.</li><li><p><b>Apply.</b> Before you sign.</p></li></ol>');
    const list = output.querySelector("ol");

    expect(list.classList.contains("md-steps")).toBe(true);
    expect(list.style.counterReset).toBe("md-step 2");
  });

  it("drops the point or colon that closed a title in running text, not an ellipsis", () => {
    const output = render("<ol><li><strong>Ask.</strong> Three offers.</li><li><strong>Apply</strong>: before you sign.</li>"
      + "<li><strong>Wait...</strong> a week.</li><li><strong>Sign:</strong> then.</li></ol>");
    const titles = Array.from(output.querySelectorAll("ol.md-steps strong")).map(title => title.textContent);
    expect(titles).toEqual(["Ask", "Apply", "Wait...", "Sign"]);
    expect(output.querySelectorAll("ol.md-steps li")[1].textContent).toBe("Apply before you sign.");
  });

  it("drops a line break the model wrote after the title, which stands on its own line already", () => {
    const output = render("<ol><li><p><strong>2020–2022: Zero rates</strong><br>\nThe bank held its rate.</p></li>"
      + "<li><p><strong>Since 2024: Easing</strong><br>Rates fell.</p></li></ol>");
    expect(output.querySelectorAll("ol.md-steps br")).toHaveLength(0);
    expect(output.querySelector("ol.md-steps li").textContent).toContain("Zero rates");
  });

  it("leaves plain, partly titled and all-bold lists and bullet lists alone", () => {
    expect(render("<ol><li>One</li><li>Two</li></ol>").querySelector(".md-steps")).toBeNull();
    expect(render("<ol><li><strong>One.</strong> Text</li><li>Two</li></ol>").querySelector(".md-steps")).toBeNull();
    expect(render("<ol><li><strong>Only bold</strong></li></ol>").querySelector(".md-steps")).toBeNull();
    expect(render("<ol><li>Then <strong>bold</strong> later</li></ol>").querySelector(".md-steps")).toBeNull();
    expect(render("<ul><li><strong>One.</strong> Text</li></ul>").querySelector(".md-steps")).toBeNull();
  });

  it("stands on the rail while its last item is still only a title", () => {
    const { window } = load("<ol><li><strong>Ask.</strong> Three offers.</li><li><strong>Appl</strong></li></ol>");
    const growing = window.document.createElement("div");
    growing.append(window.renderMarkdownFragment("answer", { growing: true }));
    expect(growing.querySelector("ol.md-steps")).not.toBeNull();
    const fixed = window.document.createElement("div");
    fixed.append(window.renderMarkdownFragment("answer"));
    expect(fixed.querySelector("ol.md-steps")).toBeNull();
  });
});

describe("Public pages", () => {
  it("draws a server-rendered answer with the same rules and names the shapes", () => {
    const html = `<div class="share-md">${table(["A", "B"], [["17 €", "3 Jahre"]])}`
      + `${table(["Heating", "Per year"], [["Gas", "2.150 €"], ["<strong>Air</strong>", "1.380 €"], ["Ground", "1.090 €"]])}`
      + "<ol><li><strong>Ask.</strong> Three offers.</li></ol></div>";
    const { window, document } = loadScripts([], { body: html, base: false });
    const script = document.createElement("script");
    script.dataset.drawAnswers = ".share-md";
    script.textContent = readFileSync(new URL("../../static/js/answer-shapes.js", import.meta.url), "utf8");
    document.body.append(script);

    const root = document.querySelector(".share-md");
    expect(root.querySelector(".md-figures")).not.toBeNull();
    expect(root.querySelector("table.md-bar-rows tr.md-pick")).not.toBeNull();
    expect(root.querySelector("ol.md-steps")).not.toBeNull();
    expect(window.AnswerShapes.present(root)).toEqual(["figures", "bars", "pick", "steps"]);
    // Drawing again changes nothing.
    window.AnswerShapes.draw(root);
    expect(root.querySelectorAll(".md-bar")).toHaveLength(3);
  });
});
