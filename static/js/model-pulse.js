// Model pulse board. The server renders the first view (also without JS);
// a filter change fetches /api/model-pulse and rebuilds the same markup as
// the template's pulse_row macro. The URL follows the filters, so a view
// can be shared.

(function () {
  const form = document.getElementById("modelPulseFilters");
  const board = document.getElementById("modelPulseBoard");
  const foot = document.getElementById("modelPulseFoot");
  if (!form || !board) return;

  const number = new Intl.NumberFormat(document.documentElement.lang || "en");
  const PRIVACY = " No prompt text or user identity enters this tally.";
  let requestVersion = 0;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function shortName(key) {
    const select = form.querySelector('select[name="with"]');
    const option = select && Array.from(select.options).find(item => item.value === key);
    return option ? option.textContent : key;
  }

  function percent(value, scale) {
    return String((Number(value) || 0) / scale * 100);
  }

  function renderRow(row, scale, rivalShort) {
    const item = el("li", "pulse-row" + (row.is_rival ? " is-rival" : ""));
    item.dataset.family = row.key;

    const iconWrap = el("span", "lp-model-pulse-icon");
    const icon = document.createElement("img");
    icon.src = typeof row.icon === "string" ? row.icon : "/static/favicon.png";
    icon.alt = "";
    iconWrap.appendChild(icon);

    const copy = el("span", "pulse-copy");
    const sub = el("span", "pulse-sub", `${number.format(row.picks)} of ${number.format(row.runs)} runs`);
    if (row.lift !== null && row.lift !== undefined) {
      sub.append(" · ", el("b", "", `${Number(row.lift).toFixed(1)}×`), " fair share");
    }
    if (row.h2h) {
      const h2h = el("span", "pulse-h2h", `vs ${rivalShort} `);
      h2h.appendChild(el("b", "", `${row.h2h.wins}–${row.h2h.losses}`));
      sub.append(" · ", h2h);
    }
    const meter = el("span", "pulse-meter");
    meter.setAttribute("aria-hidden", "true");
    const interval = Array.isArray(row.interval) ? row.interval : [row.rate, row.rate];
    meter.style.setProperty("--rate", percent(row.rate, scale));
    meter.style.setProperty("--fair", percent(row.fair_share, scale));
    meter.style.setProperty("--lo", percent(interval[0], scale));
    meter.style.setProperty("--hi", percent(interval[1], scale));
    meter.append(el("i", "pulse-meter-range"), el("i", "pulse-meter-bar"), el("i", "pulse-meter-fair"));
    copy.append(el("span", "pulse-name", row.family), sub, meter);

    const rate = el("span", "pulse-rate", String(Math.round(Number(row.rate) || 0)));
    rate.appendChild(el("small", "", "%"));

    item.append(el("span", "pulse-rank", String(row.rank).padStart(2, "0")), iconWrap, copy, rate);
    return item;
  }

  function render(view) {
    const scale = Number(view.scale) || 100;
    const rows = Array.isArray(view.rows) ? view.rows : [];
    const sparse = Array.isArray(view.sparse) ? view.sparse : [];
    const rivalShort = view.rival ? shortName(view.rival) : "";
    const fragment = document.createDocumentFragment();

    if (view.rival) {
      const note = el("p", "pulse-rival-note", "Only runs that included ");
      note.append(el("strong", "", rivalShort),
        `. The score beside each family counts the runs in which it beat ${rivalShort} to the pick, and the runs ${rivalShort} won.`);
      fragment.appendChild(note);
    }
    if (rows.length) {
      const list = el("ol", "pulse-list");
      rows.forEach(row => list.appendChild(renderRow(row, scale, rivalShort)));
      const legend = el("div", "pulse-legend");
      legend.setAttribute("aria-hidden", "true");
      [["pulse-key-bar", "Best-answer rate"], ["pulse-key-range", "Plausible range (95%)"], ["pulse-key-fair", "Fair share by chance"]]
        .forEach(([key, label]) => {
          const span = el("span");
          span.append(el("i", key), label);
          legend.appendChild(span);
        });
      fragment.append(list, legend);
    } else {
      fragment.appendChild(el("p", "pulse-empty",
        `No family has ${view.min_runs} judged runs in this view yet. Try a longer period.`));
    }
    if (sparse.length) {
      const line = el("p", "pulse-sparse");
      line.append(el("strong", "", "Too few runs to rank"), ` (under ${view.min_runs}): `);
      sparse.forEach((row, index) => {
        line.append(`${row.short} `, el("span", "", String(row.runs)));
        if (index < sparse.length - 1) line.append(", ");
      });
      fragment.appendChild(line);
    }

    board.classList.remove("is-ready");
    board.replaceChildren(fragment);
    if (foot) {
      foot.textContent = view.runs
        ? `${number.format(view.runs)} judged runs${view.since ? ` since ${view.since}` : ""} · ${view.average_field} answers per run on average.${PRIVACY}`
        : `No judged runs in this view yet.${PRIVACY}`;
    }
    requestAnimationFrame(() => board.classList.add("is-ready"));
  }

  function query() {
    const params = new URLSearchParams();
    new FormData(form).forEach((value, key) => {
      if (value) params.set(key, String(value));
    });
    return params;
  }

  function load() {
    const currentRequest = ++requestVersion;
    const params = query();
    board.classList.add("is-loading");
    board.setAttribute("aria-busy", "true");
    fetch(`/api/model-pulse?${params}`, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(response => {
        if (!response.ok) throw new Error(`Model pulse request failed (${response.status})`);
        return response.json();
      })
      .then(view => {
        if (currentRequest !== requestVersion) return;
        render(view);
        const search = params.toString();
        history.replaceState(null, "", search ? `?${search}` : location.pathname);
      })
      .catch(error => {
        if (currentRequest !== requestVersion) return;
        console.warn("Model pulse unavailable:", error);
        // The last good view stays; only the line under it says so.
        if (foot) foot.textContent = "Could not refresh the board. The previous view is still shown.";
      })
      .finally(() => {
        if (currentRequest !== requestVersion) return;
        board.classList.remove("is-loading");
        board.setAttribute("aria-busy", "false");
      });
  }

  form.addEventListener("change", load);
  form.addEventListener("submit", event => {
    event.preventDefault();
    load();
  });
})();
