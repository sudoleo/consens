// Shapes an answer draws from what a model already writes as plain Markdown.
// The rules read the structure alone: no syntax a model would have to learn,
// no word of any language. One file for /app (markdown-stream.js asks it for
// every rendered answer) and for the public pages, which load it on their
// own and draw their server-rendered answers with the same rules.
//
//   figures   a table of one row: its values large over their headings
//   timeline  a table whose first column holds only dates: dates on a rail
//   facing    a table of two text columns whose rows are no pairs: two sides
//   bars      a column of comparable amounts: a bar under each
//   pick      bars with exactly one row whose label is bold: that row in green
//   steps     a numbered list whose items open with a bold title: a rail
(function () {
  "use strict";

  const textOf = node => (node?.textContent || "").replace(/\s+/g, " ").trim();
  const bodyRows = table => Array.from(table.tBodies || []).flatMap(body => Array.from(body.rows || []));
  const headCells = table => (table.tHead?.rows.length === 1 ? Array.from(table.tHead.rows[0].cells) : []);
  const docOf = node => node.ownerDocument || document;

  // The nodes that carry something: no blank text between tags.
  const meaningful = host => Array.from(host.childNodes).filter(node => node.nodeType !== 3 || node.nodeValue.trim());
  const isBold = node => node?.nodeType === 1 && (node.tagName === "STRONG" || node.tagName === "B");
  // A cell written in bold throughout, "**Air heat pump**".
  const wholeBold = cell => {
    const nodes = meaningful(cell);
    return nodes.length === 1 && isBold(nodes[0]) && textOf(nodes[0]).length > 0;
  };

  // "12.000 €", "€1,200.50", "4,6 t", "35 %": the amount and its unit. Both
  // thousands conventions occur; a lone separator before exactly three
  // digits is read as thousands.
  const AMOUNT = /^([€$£¥]\s?)?(\d[\d.,\s]*)(\s?[^\d\s.,()+-][^\d()]{0,9})?$/;

  function parseAmount(text) {
    const match = String(text || "").replace(/[  ]/g, " ").trim().match(AMOUNT);
    if (!match) return null;
    let digits = match[2].replace(/\s/g, "");
    if (/[.,]$/.test(digits)) return null;
    const dot = digits.lastIndexOf("."), comma = digits.lastIndexOf(",");
    if (dot !== -1 && comma !== -1) {
      const decimal = dot > comma ? "." : ",";
      digits = digits.split(decimal === "." ? "," : ".").join("").replace(decimal, ".");
    } else if (dot !== -1 || comma !== -1) {
      const mark = dot !== -1 ? "." : ",";
      const parts = digits.split(mark);
      digits = parts.length > 2 || parts[1].length === 3 ? parts.join("") : parts.join(".");
    }
    const value = Number(digits);
    return Number.isFinite(value) ? { value, unit: (match[1] || match[3] || "").trim() } : null;
  }

  // --- Figures --------------------------------------------------------------
  // A table of one row has nothing to compare: its two to four short values
  // are the figures of the answer, each over its heading.
  function figures(table) {
    const head = headCells(table);
    const rows = bodyRows(table);
    const cells = rows.length === 1 ? Array.from(rows[0].cells) : [];
    if (head.length < 2 || head.length > 4 || cells.length !== head.length) return false;
    const short = cell => textOf(cell).length <= 18 && !cell.querySelector("br, img, a, code");
    if (!cells.every(cell => short(cell) && /\d/.test(cell.textContent))) return false;
    if (!head.every(cell => textOf(cell))) return false;

    const doc = docOf(table);
    const list = doc.createElement("dl");
    list.className = "md-figures";
    // Long values take a smaller size, so four of them still share a line.
    const longest = Math.max(...cells.map(cell => textOf(cell).length));
    if (longest > 10) list.classList.add("is-long");
    head.forEach((label, index) => {
      const group = doc.createElement("div");
      const term = doc.createElement("dt");
      const value = doc.createElement("dd");
      term.append(...label.childNodes);
      value.append(...cells[index].childNodes);
      group.append(term, value);
      list.append(group);
    });
    table.replaceWith(list);
    return true;
  }

  // --- Timeline -------------------------------------------------------------
  // A point in time, read from its digits: a year (1000 to 2199, also with a
  // short ending such as "1990s"), a full date in any of the common orders,
  // a day and month with their dots ("12.3."), a month and year ("3/2024")
  // or a time of day ("09:30"). Words around it ("since", a month's name in
  // any language) are allowed but never needed: no list of month names.
  const WHEN = /^(?:\d{4}\p{L}{0,3}|\d{1,2}\.\d{1,2}\.(?:\d{2}|\d{4})?|\d{4}-\d{1,2}(?:-\d{1,2})?|\d{1,2}\/\d{1,2}\/\d{2,4}|\d{1,2}\/\d{4}|\d{1,2}:\d{2}|\d{1,2}\.\s?\p{L}{2,12}\.?)$/u;
  const WORD = /^[\p{L}][\p{L}.']{0,11}$/u;

  function when(cell) {
    const text = textOf(cell);
    if (!text || text.length > 22 || cell.querySelector("img, a, code, br")) return null;
    // "12. März" is one point, "2020-2023" two years. No lookbehind: older
    // Safari cannot parse one, and this file shares its bundle with others.
    const tokens = text.replace(/(\d{1,2}\.)\s+(?=\p{L})/gu, "$1").replace(/(\d)-(\d{4})/g, "$1 $2")
      .split(/[\s,–—]+/u).filter(Boolean);
    if (tokens.length > 4) return null;
    let year = null, point = false, small = false;
    for (const token of tokens) {
      if (WHEN.test(token)) {
        point = true;
        const digits = token.match(/^\d{4}(?=\p{L}{0,3}$)/u);
        if (digits) {
          year = Number(digits[0]);
          if (year < 1000 || year > 2199) return null;
        }
      } else if (/^\d{1,2}\.?$/.test(token)) {
        small = true;
      } else if (!WORD.test(token) && !/^[-–]$/.test(token) && !/^Q[1-4]$/.test(token)) {
        return null;
      }
    }
    // A day on its own ("March 12, 2024") needs the year beside it.
    if (!point || (small && year === null)) return null;
    return { text, year, last: tokens[tokens.length - 1] };
  }

  // Two columns, three rows or more, the first only points in time and the
  // second words, not amounts: that is a sequence of events. A year that
  // carries the same word in every row ("1500 m", "2000 m") is a quantity
  // with its unit, and round hundreds alone ("1000", "1500", "2000") are
  // more often amounts than years: both stay a table.
  function timeline(table) {
    const head = headCells(table);
    const rows = bodyRows(table);
    if (head.length !== 2 || rows.length < 3 || rows.some(row => row.cells.length !== 2)) return false;
    const points = rows.map(row => when(row.cells[0]));
    if (points.some(point => !point)) return false;
    if (rows.some(row => !textOf(row.cells[1]) || parseAmount(textOf(row.cells[1])))) return false;
    const lasts = new Set(points.map(point => point.last));
    if (lasts.size === 1 && !WHEN.test(points[0].last) && points.every(point => point.year !== null)) return false;
    const years = points.map(point => point.year);
    if (years.every(year => year !== null && year % 100 === 0)) return false;
    if (points.every(point => /^\d{4}$/.test(point.text)) && years.every(year => year % 50 === 0)) return false;
    table.classList.add("md-timeline");
    return true;
  }

  // --- Facing ---------------------------------------------------------------
  // A table of two text columns is one of two things. Its rows are pairs (a
  // label and what it means: "Noise" | "About 45 dB at five metres"), and
  // then it reads across and stays a table. Or each column is a list of its
  // own (for | against, buy | rent, option A | option B), and then a row
  // only puts unrelated points side by side: such a table is drawn as two
  // sides. The rule, from the structure alone:
  //  - a first column written in bold throughout, or asking only questions,
  //    is a column of labels: pairs;
  //  - the shorter column's typical cell (the median) must be at least half
  //    as long as the other's: labels are much shorter than their meaning;
  //  - and at least 16 characters, a statement rather than a word; 12 where a
  //    cell is empty, because an empty cell only happens when the two sides
  //    have a different number of points, which pairs never have.
  // Any amount in a cell makes it a table of figures, and anything beyond
  // words in a cell (a list, code, a picture) keeps the table. In doubt the
  // table stays.
  const median = values => {
    const sorted = values.slice().sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  };

  function isFacing(table) {
    const head = headCells(table);
    const rows = bodyRows(table);
    if (head.length !== 2 || rows.length < 2 || rows.some(row => row.cells.length !== 2)) return false;
    if (!head.every(cell => textOf(cell)) || rows.every(row => when(row.cells[0]))) return false;
    const columns = [0, 1].map(index => rows.map(row => row.cells[index]));
    if (columns.flat().some(cell => cell.querySelector("ul, ol, pre, table, img, .md-figures")
        || (textOf(cell) && parseAmount(textOf(cell))))) return false;
    const filled = columns.map(column => column.filter(cell => textOf(cell)));
    if (filled.some(column => !column.length)) return false;
    if (filled[0].every(wholeBold) || filled[0].every(cell => /[?？؟]$/u.test(textOf(cell)))) return false;
    const gaps = filled[0].length + filled[1].length < rows.length * 2;
    const [left, right] = filled.map(column => median(column.map(cell => textOf(cell).length)));
    const shorter = Math.min(left, right);
    return shorter >= (gaps ? 12 : 16) && shorter >= Math.max(left, right) * 0.5;
  }

  let facingCount = 0;
  function facing(table) {
    if (!isFacing(table)) return false;
    const doc = docOf(table);
    const rows = bodyRows(table);
    const box = doc.createElement("div");
    box.className = "md-facing";
    facingCount += 1;
    headCells(table).forEach((cell, index) => {
      const side = doc.createElement("div");
      side.className = "md-facing-side";
      const title = doc.createElement("p");
      title.className = "md-facing-head";
      title.id = `md-facing-${facingCount}-${index}`;
      title.append(...cell.childNodes);
      // Each side is a list named by its heading: a reader hears "for, list,
      // three items", as the table said with its column header.
      const list = doc.createElement("ul");
      list.setAttribute("aria-labelledby", title.id);
      rows.forEach(row => {
        const source = row.cells[index];
        if (!textOf(source) && !source.querySelector(".katex, math")) return;
        const item = doc.createElement("li");
        item.append(...source.childNodes);
        list.append(item);
      });
      side.append(title, list);
      box.append(side);
    });
    table.replaceWith(box);
    return true;
  }

  // --- Bars -----------------------------------------------------------------
  // Bars under the amounts of a column that can be compared: one unit,
  // nothing negative, three rows or more. Years and running numbers are not
  // amounts, and a last row that sums the others would dwarf them, so it
  // gets no bar. Exactly one row whose label is bold throughout is the one
  // the answer points to: its bars take the house green. Several bold rows
  // or none say nothing, and all stays grey.
  function bars(table) {
    const rows = bodyRows(table);
    const columnCount = Math.max(0, ...rows.map(row => row.cells.length));
    const doc = docOf(table);
    const drawn = [];
    let barred = [];
    for (let column = 1; column < columnCount; column += 1) {
      let cells = rows.map(row => row.cells[column]);
      if (cells.length < 3 || cells.some(cell => !cell || cell.querySelector(".md-bar"))) continue;
      const amounts = cells.map(cell => parseAmount(cell.textContent));
      if (amounts.some(amount => !amount) || new Set(amounts.map(amount => amount.unit)).size > 1) continue;
      let values = amounts.map(amount => amount.value);
      const others = values.slice(0, -1).reduce((sum, value) => sum + value, 0);
      if (values.length >= 3 && others > 0 && Math.abs(values[values.length - 1] - others) <= others * 0.005) {
        cells = cells.slice(0, -1);
        values = values.slice(0, -1);
      }
      const plain = !amounts[0].unit && values.every(Number.isInteger);
      if (plain && values.every(value => value >= 1900 && value <= 2100)) continue;
      if (plain && values.every((value, index) => value === index + 1)) continue;
      const max = Math.max(...values);
      if (!(max > 0) || new Set(values).size < 2) continue;

      Array.from(table.rows).forEach(row => row.cells[column]?.classList.add("is-numeric"));
      cells.forEach((cell, index) => {
        const bar = doc.createElement("span");
        bar.className = "md-bar";
        bar.setAttribute("aria-hidden", "true");
        const fill = bar.appendChild(doc.createElement("i"));
        fill.style.width = `${Math.max(1, Math.round(values[index] / max * 1000) / 10)}%`;
        cell.classList.add("md-bar-cell");
        cell.append(bar);
      });
      drawn.push(column);
      barred = cells.map(cell => cell.parentElement);
    }
    if (!drawn.length) return "";
    // Label and one amount: the bar has the row to itself, beside the amount.
    if (drawn.length === 1 && columnCount === 2) {
      table.classList.add("md-bar-rows");
      const longest = Math.max(...Array.from(table.rows).map(row => textOf(row.cells[1]).length));
      table.style.setProperty("--md-bar-amount", `${longest}ch`);
      // Beside an amount this long a phone has room for a stub only.
      if (longest > 8) table.classList.add("has-long-amounts");
    }
    const bold = rows.filter(row => row.cells[0] && wholeBold(row.cells[0]));
    if (bold.length === 1 && barred.includes(bold[0])) {
      bold[0].classList.add("md-pick");
      return "pick";
    }
    return "bars";
  }

  // --- Steps ----------------------------------------------------------------
  // A numbered list whose every item opens with its title in bold is a way
  // to go: the numbers stand on a rail, each title on a line of its own,
  // where the point or colon that closed it in running text has no work left.
  // While an answer streams, its last item may still be only its title (or
  // nothing yet): `growing` lets it count, so a list of steps stands on its
  // rail from its first words instead of jumping there once text follows.
  function titleOf(item) {
    const host = item.firstElementChild?.tagName === "P" ? item.firstElementChild : item;
    const first = meaningful(host)[0];
    return isBold(first) ? { host, first } : null;
  }

  function steps(root, { growing = false } = {}) {
    let count = 0;
    root.querySelectorAll?.("ol").forEach(list => {
      if (list.classList.contains("md-task-list")) return;
      const items = Array.from(list.children).filter(child => child.tagName === "LI");
      const titled = item => {
        const title = titleOf(item);
        // A title, not a sentence that happens to start bold or is bold throughout.
        return Boolean(title) && textOf(title.first).length <= 80 && textOf(title.host).length > textOf(title.first).length;
      };
      const last = items[items.length - 1];
      const open = growing && last && (!textOf(last) || (titleOf(last) && textOf(titleOf(last).first).length <= 80));
      const body = open ? items.slice(0, -1) : items;
      if (!items.length || !body.every(titled)) return;
      list.classList.add("md-steps");
      const start = Number(list.getAttribute("start"));
      if (start > 1) list.style.counterReset = `md-step ${start - 1}`;
      items.forEach(item => dropTitleStop(titleOf(item)));
      count += 1;
    });
    return count;
  }

  // "**Ask.** Three offers" and "**Ask**: three offers" both stand as "Ask".
  // An ellipsis is part of the title and stays.
  function dropTitleStop(title) {
    if (!title) return;
    const walker = docOf(title.first).createTreeWalker(title.first, 4);
    let lastText = null;
    while (walker.nextNode()) if (walker.currentNode.nodeValue.trim()) lastText = walker.currentNode;
    if (lastText && /[^.][.:]\s*$/.test(lastText.nodeValue)) {
      lastText.nodeValue = lastText.nodeValue.replace(/[.:](\s*)$/, "$1");
      return;
    }
    const after = title.first.nextSibling;
    if (after?.nodeType === 3 && /^[.:](?!\.)/.test(after.nodeValue)) after.nodeValue = after.nodeValue.slice(1);
  }

  // --- Entry points ---------------------------------------------------------
  // A table that becomes something else: figures or two sides. Returns the
  // shape's name, or "" when it stays a table.
  function replaceTable(table) {
    if (figures(table)) return "figures";
    if (facing(table)) return "facing";
    return "";
  }

  // A table that stays one, with a form of its own: dates on a rail or bars.
  function decorateTable(table) {
    if (timeline(table)) return "timeline";
    return bars(table);
  }

  // Everything in `root` at once (public pages: the server rendered the
  // answer, the page draws it). Returns the names of the shapes drawn.
  function draw(root) {
    const drawn = new Set();
    Array.from(root?.querySelectorAll?.("table") || []).forEach(table => {
      if (table.closest(".md-facing, .md-figures") || table.classList.contains("md-shaped")) return;
      const replaced = replaceTable(table);
      if (replaced) return void drawn.add(replaced);
      table.classList.add("md-shaped");
      const decorated = decorateTable(table);
      if (decorated) drawn.add(decorated);
    });
    if (steps(root)) drawn.add("steps");
    return [...drawn];
  }

  // The shapes standing in `root`, by their names (counting, agent-chat.js).
  function present(root) {
    const found = [];
    const has = selector => Boolean(root?.querySelector?.(selector));
    if (has(".md-figures")) found.push("figures");
    if (has(".md-facing")) found.push("facing");
    if (has("table.md-timeline")) found.push("timeline");
    if (has(".md-bar")) found.push("bars");
    if (has("tr.md-pick")) found.push("pick");
    if (has("ol.md-steps")) found.push("steps");
    return found;
  }

  window.AnswerShapes = { parseAmount, replaceTable, decorateTable, steps, draw, present, isFacing };

  // A public page names the answers it draws on its script tag
  // (partials/answer_blocks.html); in /app the renderer asks instead.
  const answers = document.currentScript?.dataset?.drawAnswers;
  if (answers) document.querySelectorAll(answers).forEach(draw);
})();
