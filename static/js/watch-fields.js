// The parts a watch is set up with, built once for the "New watch" dialog
// (watch.js) and the card settings on /app/watches (watch-dashboard.js), so
// both say the same thing with the same controls (Apple-Audit J7), plus the
// one way a watch's times are written (J5, J30). Classic script; exports
// window.App.watchFields. Loads before watch.js.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  const MINUTE = 60 * 1000;

  function capitalize(text) {
    const value = String(text || "");
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function browserTimezone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    } catch (_) {
      return "UTC";
    }
  }

  // A watch's time zone is named only when it is not the reader's own, and
  // as a place ("New York time"), never as "America/New_York".
  function timezoneCity(timezone, own = browserTimezone()) {
    const zone = String(timezone || "");
    if (!zone || zone === own) return "";
    if (/^(Etc\/)?(UTC|GMT|Universal|Zulu)$/i.test(zone)) return "UTC";
    return zone.split("/").pop().replace(/_/g, " ");
  }

  function timezoneNote(timezone, own) {
    const city = timezoneCity(timezone, own);
    return !city ? "" : city === "UTC" ? "UTC" : city + " time";
  }

  // "weekly on Tuesday at 09:00 (New York time)": dialog, card, Agent card
  // and the success line all write a schedule this way. Sentence case is the
  // caller's (scheduleLabel for the start of a line).
  function scheduleText(watch, { own } = {}) {
    const interval = ["daily", "monthly"].includes(watch?.interval) ? watch.interval : "weekly";
    let text = interval;
    if (interval === "weekly" && WEEKDAYS.includes(watch?.run_weekday)) text += " on " + capitalize(watch.run_weekday);
    if (watch?.run_time) text += " at " + watch.run_time;
    const note = timezoneNote(watch?.timezone, own);
    if (note) text += ` (${note})`;
    return text;
  }

  function scheduleLabel(watch, options) {
    return capitalize(scheduleText(watch, options));
  }

  // A watch's times are written by App.format (app-text.js), the one
  // formatter of the app (Apple-Audit H8): the 24-hour clock, "Oct 21",
  // the year only when it is not this one.
  const format = () => App.format;

  // Tooltips: "Tue, Oct 21, 09:00".
  function dateTimeTitle(value) {
    return format().dateTime(value, { weekday: true });
  }

  function shortDay(value) {
    return format().date(value);
  }

  // A time ahead: "today, 14:30", "tomorrow, 09:00", "Monday, 09:00", "Oct 30, 09:00".
  function dayAndTime(value, now = Date.now()) {
    return format().upcoming(value, now);
  }

  // A time behind: "just now", "12m ago", "3h ago", "yesterday", then the
  // date. Re-read every minute by the page (watch-dashboard.js).
  function relativePast(value, now = Date.now()) {
    return format().relative(value, now);
  }

  // When the next check is, honestly: a check that runs says so, a time
  // that has passed is due (the scheduler picks it up within its tick), and
  // a time ahead is the clock. `checking` and `due` come from the server
  // (_serialize_watch); without them the time alone decides.
  function nextCheck(watch, now = Date.now()) {
    if (watch?.checking === true) return { state: "checking", text: "Checking now…" };
    const date = format().toDate(watch?.next_run_at);
    if (!date) return { state: "none", text: "" };
    const ahead = date.getTime() - now;
    if (watch?.due === true || ahead <= 0) return { state: "due", text: "Check due now" };
    const minutes = Math.round(ahead / MINUTE);
    if (minutes < 1) return { state: "soon", text: "Next check in under a minute" };
    if (minutes < 60) return { state: "soon", text: `Next check in ${format().duration(minutes * MINUTE, { minutes: true })}` };
    return { state: "scheduled", text: "Next check " + dayAndTime(date, now) };
  }

  // ------------------------------------------------------------------
  // Controls. Each builder returns the element; ids are the caller's
  // (the dialog keeps its #watch… ids, cards prefix theirs).
  // ------------------------------------------------------------------

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function option(value, label, { selected = false, disabled = false } = {}) {
    const node = el("option", "", label);
    node.value = value;
    if (selected) node.selected = true;
    if (disabled) node.disabled = true;
    return node;
  }

  function select(id, options) {
    const node = el("select", "watch-select wd-select");
    if (id) node.id = id;
    options.forEach(item => node.appendChild(item));
    return node;
  }

  function intervalSelect(id, selected, dailyAllowed) {
    return select(id, [
      option("weekly", "Weekly", { selected: selected !== "monthly" && selected !== "daily" }),
      option("monthly", "Monthly", { selected: selected === "monthly" }),
      option("daily", dailyAllowed ? "Daily" : "Daily (Pro)", { selected: selected === "daily", disabled: !dailyAllowed })
    ]);
  }

  function weekdaySelect(id, selected) {
    const current = WEEKDAYS.includes(selected) ? selected : WEEKDAYS[(new Date().getDay() + 6) % 7];
    return select(id, WEEKDAYS.map(day => option(day, capitalize(day), { selected: day === current })));
  }

  // Alert rules in the words of the evidence model. Short enough for one
  // line in the narrowest settings column (J28).
  function alertLabels(hasGoal) {
    return {
      changes_only: hasGoal ? "When it moves or is reached" : "When it moves on evidence",
      condition: "Only when it is reached",
      every_run: "After every check"
    };
  }

  function alertSelect(id, selected, hasGoal) {
    const labels = alertLabels(hasGoal);
    const current = ["condition", "every_run"].includes(selected) ? selected : "changes_only";
    return select(id, Object.entries(labels).map(([value, label]) => option(value, label, { selected: value === current })));
  }

  // The goal decides how the first rule reads; the choice itself stays.
  function relabelAlerts(selectNode, hasGoal) {
    const labels = alertLabels(hasGoal);
    Array.from(selectNode.options).forEach(item => {
      if (labels[item.value]) item.textContent = labels[item.value];
    });
  }

  function visibilitySelect(id, value) {
    return select(id, [
      option("private", "Private, only you", { selected: value !== "public" }),
      option("public", "Public, anyone with the link", { selected: value === "public" })
    ]);
  }

  function timeInput(id, value) {
    const node = el("input", "watch-input watch-time");
    if (id) node.id = id;
    node.type = "time";
    node.value = value || "";
    node.required = true;
    return node;
  }

  function detailsInput(id, value) {
    const node = el("textarea", "watch-input watch-details-input");
    if (id) node.id = id;
    node.rows = 2;
    node.maxLength = 500;
    node.placeholder = "Example: Only new, from a shop. No eBay or private sellers. Size 44.5.";
    node.value = value || "";
    return node;
  }

  let groupSerial = 0;

  // One field: its label and its control. A label element only for a single
  // control; a group of controls (channels) is a group, so a click on its
  // heading never toggles the first box in it (J10).
  function field({ label, control, hint = "", id = "", group = false, wide = false, className = "" }) {
    const wrap = el("div", "watch-field" + (wide ? " is-wide" : "") + (className ? " " + className : ""));
    const head = el("div", "watch-field-head");
    let labelNode;
    if (group) {
      labelNode = el("span", "watch-field-label", label);
      labelNode.id = (id || "watchField" + (groupSerial += 1)) + "Label";
      wrap.setAttribute("role", "group");
      wrap.setAttribute("aria-labelledby", labelNode.id);
    } else {
      labelNode = el("label", "watch-field-label", label);
      if (control.id) labelNode.htmlFor = control.id;
    }
    const status = el("span", "watch-field-status");
    status.setAttribute("aria-live", "polite");
    head.append(labelNode, status);
    wrap.append(head, control);
    if (hint) {
      const note = el("p", "watch-field-hint", hint);
      if (id) note.id = id + "Hint";
      wrap.appendChild(note);
    }
    const error = el("p", "watch-field-error");
    error.setAttribute("role", "alert");
    error.hidden = true;
    if (id) error.id = id + "Error";
    wrap.appendChild(error);
    if (id && !group && control.id) {
      control.setAttribute("aria-describedby", (hint ? id + "Hint " : "") + error.id);
    }
    return wrap;
  }

  // "Saved" beside a field's label once a change has landed; it fades by
  // itself (CSS). The error line under the field says what failed.
  const savedTimers = new WeakMap();
  function markSaved(fieldNode, text = "Saved") {
    const status = fieldNode?.querySelector(":scope > .watch-field-head > .watch-field-status, :scope > legend > .watch-field-status");
    if (!status) return;
    clearTimeout(savedTimers.get(status));
    status.textContent = text;
    status.classList.remove("is-shown");
    void status.offsetWidth;
    status.classList.add("is-shown");
    savedTimers.set(status, setTimeout(() => status.classList.remove("is-shown"), 1800));
    setError(fieldNode, "");
  }

  function setError(fieldNode, message) {
    const error = fieldNode?.querySelector(":scope > .watch-field-error");
    if (!error) return;
    error.textContent = message || "";
    error.hidden = !message;
    fieldNode.querySelectorAll("input, select, textarea").forEach(control => {
      if (message) control.setAttribute("aria-invalid", "true");
      else control.removeAttribute("aria-invalid");
    });
  }

  // "What are you waiting for?": one radio list -- offered events, "Something
  // else…" with its own line, "Any change to the answer". The dialog fills
  // the offered rows from goal suggestions, a card from its current goal.
  function goalList({ prefix = "watchGoal", name = "watchGoalChoice", label = "What are you waiting for?", ids = true } = {}) {
    const root = el("fieldset", "watch-goal");
    const legend = el("legend", "watch-goal-label", label);
    const legendStatus = el("span", "watch-field-status");
    legendStatus.setAttribute("aria-live", "polite");
    legend.appendChild(legendStatus);
    const options = el("div", "watch-goal-options");
    const offered = el("div", "watch-goal-suggestions");
    offered.setAttribute("aria-live", "polite");
    const custom = el("div", "watch-goal-option is-custom");
    const customChoice = el("input");
    customChoice.type = "radio";
    customChoice.name = name;
    customChoice.value = "custom";
    customChoice.setAttribute("aria-label", "Something else");
    const input = el("input", "watch-goal-input");
    input.type = "text";
    input.maxLength = 500;
    input.placeholder = "Something else…";
    input.autocomplete = "off";
    input.setAttribute("aria-label", "Something else: the event you are waiting for");
    custom.append(customChoice, input);
    const any = el("label", "watch-goal-option");
    const anyChoice = el("input");
    anyChoice.type = "radio";
    anyChoice.name = name;
    anyChoice.value = "none";
    any.append(anyChoice, el("span", "", "Any change to the answer"));
    options.append(offered, custom, any);
    const hint = el("p", "watch-goal-hint");
    const error = el("p", "watch-field-error");
    error.setAttribute("role", "alert");
    error.hidden = true;
    root.append(legend, options, hint, error);
    if (ids) {
      legend.id = prefix + "Label";
      offered.id = prefix + "Suggestions";
      customChoice.id = prefix + "CustomChoice";
      input.id = prefix;
      anyChoice.id = prefix + "None";
      hint.id = prefix + "Hint";
      error.id = prefix + "Error";
      root.setAttribute("aria-describedby", hint.id);
      input.setAttribute("aria-describedby", error.id);
    }

    function offeredOption(goal) {
      const row = el("label", "watch-goal-option");
      const radio = el("input");
      radio.type = "radio";
      radio.name = name;
      radio.value = "suggested";
      radio.dataset.goal = goal;
      row.append(radio, el("span", "", goal));
      return row;
    }
    function checked() {
      return root.querySelector(`input[name="${name}"]:checked`);
    }
    function value() {
      const choice = checked();
      if (!choice) return { kind: null, goal: "" };
      if (choice.value === "none") return { kind: "none", goal: "" };
      if (choice.value === "custom") return { kind: "custom", goal: input.value.replace(/\s+/g, " ").trim() };
      return { kind: "suggested", goal: choice.dataset.goal || "" };
    }
    function offeredRadios() {
      return Array.from(offered.querySelectorAll(`input[name="${name}"]`));
    }
    function setOffered(goals) {
      const keep = value();
      offered.replaceChildren(...goals.map(offeredOption));
      if (keep.kind === "suggested") {
        const again = offeredRadios().find(radio => radio.dataset.goal === keep.goal);
        if (again) again.checked = true;
      }
    }
    function select(goal) {
      if (goal === "none") { anyChoice.checked = true; return; }
      if (goal === "custom") { customChoice.checked = true; return; }
      const radio = offeredRadios().find(item => item.dataset.goal === goal);
      if (radio) radio.checked = true;
    }
    // The custom row is a div (two controls); its padding answers clicks
    // like the label rows around it, and typing or focusing picks it.
    custom.addEventListener("click", event => {
      if (event.target === custom) input.focus();
    });
    return { root, offered, input, customChoice, anyChoice, hint, error, checked, value, setOffered, offeredRadios, select };
  }

  App.watchFields = {
    WEEKDAYS,
    capitalize,
    browserTimezone,
    timezoneCity,
    timezoneNote,
    scheduleText,
    scheduleLabel,
    dateTimeTitle,
    shortDay,
    dayAndTime,
    relativePast,
    nextCheck,
    intervalSelect,
    weekdaySelect,
    alertSelect,
    relabelAlerts,
    alertLabels,
    visibilitySelect,
    timeInput,
    detailsInput,
    field,
    markSaved,
    setError,
    goalList
  };
})();
