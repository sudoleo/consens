import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

// Under each table of an answer stands a line that copies it as CSV or as
// Markdown (markdown-stream.js addTableTools). It copies the cells the model
// wrote, also where a shape was drawn from them (answer-shapes.js), and it
// adds no text to the answer.
const VENDOR = ["static/vendor/marked/12.0.2/marked.min.js", "static/vendor/dompurify/3.4.17/dist/purify.min.js"];

function boot({ rich = false, clipboard } = {}) {
  const writeText = vi.fn(async () => {});
  const env = loadScripts([...VENDOR, "static/js/answer-shapes.js", "static/js/markdown-stream.js",
    ...(rich ? ["static/js/answer-copy.js"] : [])], {
    before(window) {
      Object.defineProperty(window.navigator, "clipboard", { configurable: true, value: clipboard || { writeText } });
    },
  });
  return { ...env, writeText };
}

function render(markdown, options) {
  const env = boot(options);
  const output = env.document.createElement("div");
  env.document.body.append(output);
  env.window.injectMarkdown(output, markdown, []);
  return { ...env, output };
}

async function copied({ output, writeText }, format, at = 0) {
  writeText.mockClear();
  output.querySelectorAll(`.table-copy[data-format="${format}"]`)[at].click();
  await vi.waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
  return writeText.mock.calls[0][0];
}

const PRICES = `Prices:

| Product | Price | Note |
|:---|---:|:---:|
| **Pump** | 1.234,56 € | the "small" one |
| [Boiler](https://example.com/b) | 900 € | a \\| b |
| Tank | – | first<br>second |

After the table.`;

describe("Copying a table", () => {
  it("puts one quiet line without words of its own under the table", () => {
    const { output } = render(PRICES);
    const line = output.querySelector(".markdown-table-wrap + .md-block-tools.md-table-tools");
    expect(line).not.toBeNull();
    const buttons = [...line.querySelectorAll("button.table-copy")];
    expect(buttons.map(button => [button.dataset.format, button.dataset.word, button.getAttribute("aria-label")]))
      .toEqual([["csv", "CSV", "Copy table as CSV"], ["markdown", "Markdown", "Copy table as Markdown"]]);
    // Its words are drawn from attributes: the answer's text is the answer.
    expect(line.textContent).toBe("");
    expect(output.textContent.replace(/\s+/g, " ").trim()).toBe(
      'Prices: Product Price Note Pump 1.234,56 € the "small" one Boiler 900 € a | b Tank – firstsecond After the table.');
    expect(output.querySelectorAll(".md-table-tools")).toHaveLength(1);
  });

  it("copies the cells as CSV, a value with a comma, a quote or a line break in quotes", async () => {
    const view = render(PRICES);
    expect(await copied(view, "csv")).toBe([
      "Product,Price,Note",
      'Pump,"1.234,56 €","the ""small"" one"',
      "Boiler,900 €,a | b",
      'Tank,–,"first\nsecond"',
    ].join("\n"));
    const button = view.output.querySelector('.table-copy[data-format="csv"]');
    await vi.waitFor(() => expect(button.classList.contains("is-copied")).toBe(true));
    expect(button.getAttribute("aria-label")).toBe("Copied");
    expect(button.closest(".md-table-tools").classList.contains("is-copied")).toBe(true);
  });

  it("copies the table as the Markdown it was written in", async () => {
    expect(await copied(render(PRICES), "markdown")).toBe([
      "| Product | Price | Note |",
      "| :--- | ---: | :---: |",
      '| **Pump** | 1.234,56 € | the "small" one |',
      "| [Boiler](https://example.com/b) | 900 € | a \\| b |",
      "| Tank | – | first<br>second |",
    ].join("\n"));
  });

  it("copies the cells of a table that became figures, not the figures", async () => {
    const view = render("| After subsidy | Per year | Pays off after |\n|---|---|---|\n| 17.600 € | 1,38 Tsd. € | 11 Jahre |\n");
    expect(view.output.querySelector("table")).toBeNull();
    expect(view.output.querySelector("dl.md-figures + .md-table-tools")).not.toBeNull();
    expect(await copied(view, "csv")).toBe('After subsidy,Per year,Pays off after\n17.600 €,"1,38 Tsd. €",11 Jahre');
    expect(await copied(view, "markdown")).toBe(
      "| After subsidy | Per year | Pays off after |\n| --- | --- | --- |\n| 17.600 € | 1,38 Tsd. € | 11 Jahre |");
  });

  it("copies the rows of a table that became two sides, its empty cells where they were", async () => {
    const view = render(["| For | Against |", "|---|---|",
      "| Running costs about a third below gas | Even after the subsidy dearer than a gas boiler |",
      "| The subsidy covers almost half the purchase | |",
      "| No risk from a rising CO₂ price | The outdoor unit needs room and can be heard |"].join("\n"));
    expect(view.output.querySelector("table")).toBeNull();
    expect(view.output.querySelector(".md-facing + .md-table-tools")).not.toBeNull();
    expect(await copied(view, "csv")).toBe(["For,Against",
      "Running costs about a third below gas,Even after the subsidy dearer than a gas boiler",
      "The subsidy covers almost half the purchase,",
      "No risk from a rising CO₂ price,The outdoor unit needs room and can be heard"].join("\n"));
  });

  it("keeps every value in its column where a cell spans rows or columns", async () => {
    const view = render(["<table><thead><tr><th>Region</th><th>Product</th><th>Sales</th></tr></thead><tbody>",
      '<tr><td rowspan="2">North</td><td>Pump</td><td>12</td></tr>',
      "<tr><td>Boiler</td><td>7</td></tr>",
      '<tr><td colspan="2">Total</td><td>19</td></tr>',
      "</tbody></table>"].join(""));
    expect(view.output.querySelector("td[rowspan]")).not.toBeNull();
    expect(await copied(view, "csv")).toBe("Region,Product,Sales\nNorth,Pump,12\n,Boiler,7\nTotal,,19");
    expect(await copied(view, "markdown")).toBe(
      "| Region | Product | Sales |\n| --- | --- | --- |\n| North | Pump | 12 |\n|  | Boiler | 7 |\n| Total |  | 19 |");
  });

  it("copies a table with bars or a timeline without what was drawn into it", async () => {
    const bars = render("| Heating | Cost |\n|---|---|\n| **Heat pump** | 1.380 € |\n| Gas | 2.050 € |\n| Oil | 2.300 € |\n");
    expect(bars.output.querySelectorAll(".md-bar")).toHaveLength(3);
    expect(await copied(bars, "csv")).toBe("Heating,Cost\nHeat pump,1.380 €\nGas,2.050 €\nOil,2.300 €");
    expect(await copied(bars, "markdown")).toContain("| **Heat pump** | 1.380 € |");
    const timeline = render("| Year | Event |\n|---|---|\n| 2020 | The premium starts. |\n| 2023 | The law is passed. |\n| 2024 | The new subsidy applies. |\n");
    expect(timeline.output.querySelector("table.md-timeline")).not.toBeNull();
    expect(await copied(timeline, "csv")).toBe("Year,Event\n2020,The premium starts.\n2023,The law is passed.\n2024,The new subsidy applies.");
  });

  it("leaves two sections drawn side by side, which never were a table, without a line", () => {
    const { output } = render("### For\n\n- Cheaper to run\n- Subsidised\n\n### Against\n\n- Dearer to buy\n- Needs room\n");
    expect(output.querySelector(".md-facing")).not.toBeNull();
    expect(output.querySelector(".md-table-tools")).toBeNull();
  });

  it("gives a spreadsheet the same cells as a table beside the CSV", async () => {
    const write = vi.fn(async () => {});
    const view = render(PRICES, { rich: true, clipboard: { write, writeText: vi.fn(async () => {}) } });
    const text = blob => new Promise(resolve => {
      const reader = new view.window.FileReader();
      reader.onload = () => resolve(reader.result);
      reader.readAsText(blob);
    });
    view.window.ClipboardItem = function ClipboardItem(kinds) { this.kinds = kinds; };
    view.output.querySelector('.table-copy[data-format="csv"]').click();
    await vi.waitFor(() => expect(write).toHaveBeenCalledTimes(1));
    const { kinds } = write.mock.calls[0][0][0];
    expect(await text(kinds["text/plain"])).toContain('Pump,"1.234,56 €","the ""small"" one"');
    expect(await text(kinds["text/html"])).toBe("<table><thead><tr><th>Product</th><th>Price</th><th>Note</th></tr></thead><tbody>"
      + "<tr><td>Pump</td><td>1.234,56 €</td><td>the &#34;small&#34; one</td></tr>"
      + "<tr><td>Boiler</td><td>900 €</td><td>a | b</td></tr>"
      + "<tr><td>Tank</td><td>–</td><td>first<br>second</td></tr></tbody></table>");
    // Markdown is text for a text field: nothing rich goes with it.
    view.output.querySelector('.table-copy[data-format="markdown"]').click();
    await vi.waitFor(() => expect(view.window.navigator.clipboard.writeText).toHaveBeenCalledTimes(1));
    expect(write).toHaveBeenCalledTimes(1);
  });

  it("says so when the clipboard refuses", async () => {
    const view = render(PRICES, { clipboard: { writeText: vi.fn(async () => { throw new Error("denied"); }) } });
    view.window.App.showPopup = vi.fn();
    const button = view.output.querySelector(".table-copy");
    button.click();
    await vi.waitFor(() => expect(view.window.App.showPopup).toHaveBeenCalledWith("Copy to clipboard failed."));
    expect(button.classList.contains("is-copied")).toBe(false);
  });

  // The line is part of every render, so the table and what follows it stand
  // where they stood once the stream ends, and the line the reader sees is
  // the one that copies.
  it("stands under a streamed table from the moment the table does, and still copies after the full render", async () => {
    const view = boot();
    const output = view.document.createElement("div");
    view.document.body.append(output);
    const text = `${PRICES}\n`;
    view.window.renderMarkdownStream(output, text.slice(0, text.indexOf("| Tank")));
    expect(output.querySelector(".stream-table-pending")).not.toBeNull();
    expect(output.querySelector(".md-table-tools")).toBeNull();
    view.window.renderMarkdownStream(output, text);
    const line = output.querySelector(".md-table-tools");
    const wrap = output.querySelector(".markdown-table-wrap");
    expect(line.previousElementSibling).toBe(wrap);
    view.window.morphMarkdown(output, text);
    expect(output.querySelector(".md-table-tools")).toBe(line);
    expect(output.querySelector(".markdown-table-wrap")).toBe(wrap);
    expect(output.querySelectorAll(".md-table-tools")).toHaveLength(1);
    expect(await copied({ output, writeText: view.writeText }, "csv")).toContain('Pump,"1.234,56 €"');
    // A changed table changes what its line copies.
    view.window.morphMarkdown(output, text.replace("900 €", "950 €"));
    expect(output.querySelector(".md-table-tools")).toBe(line);
    expect(await copied({ output, writeText: view.writeText }, "csv")).toContain("Boiler,950 €");
  });
});
