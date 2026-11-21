// =====================================================================
// first-run.js
// App.firstRun: the dialog a new account sees before its first question
// goes out (ai-consent.js asks through it). Two short steps:
//
//   setup     what the reviewers do, played as a short scene on one answer,
//             and how much of it this person wants to see; whether the app
//             remembers them; "I like it raw" switches to Raw HTML at once
//   consent   who answers, and the agreement to send the question there
//
//   const choice = await App.firstRun.ask({ providers });
//     null                the X, Escape or the backdrop: nothing was agreed
//     { view, memory }    agreed; view is a key of VIEWS
//   App.firstRun.apply(choice)   writes the choice to the account
//
// A view is a reading habit, not a list of features: someone who has not
// seen an answer yet cannot judge "highlights" or "detailed progress", but
// can say how much they want to see. Both choices have an answer already,
// so two clicks take a person in a hurry through.
//
// There is no "Not now" button: a way out beside the way on invites people
// to leave before they have seen an answer. The X says no just as well.
// Loaded in the "auth" group after confirm-dialog.js and before
// ai-consent.js; styles in first-run.css.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};

  // null: the app's default (user_settings.py), so a later change of that
  // default reaches these accounts too.
  const VIEWS = Object.freeze({
    answer: Object.freeze({ consensus_highlights: "critical", detailed_progress: null }),
    doubts: Object.freeze({ consensus_highlights: null, detailed_progress: null }),
    all: Object.freeze({ consensus_highlights: "all", detailed_progress: true }),
  });
  const DEFAULT_VIEW = "doubts";
  const CLOSE_ICON = '<svg class="close-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    + '<path d="M4 4l8 8M12 4l-8 8"/></svg>';

  let dialog = null;
  let pending = null;

  function t(text, params) {
    return App.t ? App.t(text, params) : text;
  }

  function viewText(view) {
    if (view === "answer") return [t("Just the answer"), t("Mistakes get fixed before you read them.")];
    if (view === "all") return [t("Everything"), t("Plus what they confirm and every step, live.")];
    return [t("With doubts"), t("You see what was fixed and what is still open.")];
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // The answer of the scene, word by word so it can come in like a stream:
  // <3> is the claim the reviewers mark wrong, <0> the year in it, <1> what
  // the agent corrects that year to, <2> the passage they doubt. The
  // translation keeps the tags and may move them; <0> and <1> stay together
  // inside <3>. --i is each word's place in the stream (first-run.css).
  function sceneAnswer() {
    const line = element("p", "first-run-answer");
    let year = null;
    let place = 0;
    let into = line;
    const open = [];
    const words = text => text.split(/(\s+)/).forEach(piece => {
      if (!piece) return;
      if (/^\s+$/.test(piece)) return into.append(" ");
      const word = element("span", "first-run-word", piece);
      word.style.setProperty("--i", String(place++));
      into.append(word);
    });
    t("The Eiffel Tower <3>opened in <0>1887</0><1>1889</1></3> and is <2>the most visited monument in the world</2>.")
      .split(/(<\/?\d>)/).forEach(part => {
        const tag = /^<(\/?)(\d)>$/.exec(part);
        if (!tag) return year?.contains(into) ? into.append(part) : words(part);
        if (tag[1]) return void (into = open.pop() || line);
        open.push(into);
        if (tag[2] === "0" || tag[2] === "1") {
          if (!year) {
            year = element("span", "first-run-word first-run-year");
            year.style.setProperty("--i", String(place++));
            into.append(year);
          }
          into = year.appendChild(element("span", tag[2] === "0" ? "is-old" : "is-new"));
          return;
        }
        into = into.appendChild(element("span", tag[2] === "3" ? "first-run-claim" : "first-run-mark"));
      });
    return line;
  }

  // The scene: a question, its answer streaming in, the reviewers finding
  // the wrong claim, the correction, the doubt. Their progress runs in one
  // line above the answer, where the app shows it; under "Everything" that
  // line shows their steps. Decoration; the caption under it says in words
  // what the chosen view shows.
  function scene() {
    const stage = element("div", "first-run-stage");
    stage.setAttribute("aria-hidden", "true");
    const play = element("div", "first-run-scene");
    const status = element("div", "first-run-status");
    const phases = element("span", "first-run-phases");
    phases.append(
      element("span", "is-checking", t("Checking the answer")),
      ...[t("Thinking: is 1887 right?"), t("Searching: Eiffel Tower opening year"), t("Reading toureiffel.paris")]
        .map(step => element("span", "is-step", step)),
      element("span", "is-found", t("Found a mistake")),
      element("span", "is-done", t("Corrected and checked")));
    status.append(element("span", "first-run-reviewers"), phases);
    play.append(status, sceneAnswer());
    stage.append(element("p", "first-run-ask", t("When did the Eiffel Tower open?")), play);
    return stage;
  }

  function closeButton() {
    const button = element("button", "close close-button");
    button.type = "button";
    button.dataset.answer = "false";
    button.setAttribute("aria-label", t("Close"));
    button.innerHTML = CLOSE_ICON;
    return button;
  }

  function build() {
    if (dialog?.isConnected) return dialog;
    dialog = element("dialog", "modal confirm-dialog first-run-dialog");
    dialog.id = "firstRunDialog";
    const content = element("div", "modal-content confirm-modal-content first-run-content");

    const setup = element("div", "first-run-step");
    setup.dataset.step = "setup";
    const pitch = element("h2", "", t("Every answer gets a second opinion"));
    pitch.id = "firstRunSetupTitle";
    const question = element("p", "first-run-lead", t("Other AI models check it and the mistakes get fixed. How much of that do you want to see?"));
    question.id = "firstRunViewLabel";
    const views = element("div", "first-run-views");
    views.setAttribute("role", "radiogroup");
    views.setAttribute("aria-labelledby", "firstRunViewLabel");
    Object.keys(VIEWS).forEach(key => {
      const [name, says] = viewText(key);
      const row = element("label", "first-run-view");
      const input = element("input");
      input.type = "radio";
      input.name = "firstRunView";
      input.value = key;
      input.setAttribute("aria-description", says);
      row.append(input, element("span", "", name));
      views.append(row);
    });
    const sample = scene();
    const caption = element("p", "first-run-caption");
    caption.setAttribute("aria-live", "polite");

    const memory = element("label", "first-run-memory");
    const memoryWords = element("span", "first-run-memory-words");
    memoryWords.append(
      element("strong", "", t("Remember what matters to you")),
      element("small", "", t("So you never have to explain yourself twice.")));
    const toggle = element("span", "switch");
    const memoryInput = element("input");
    memoryInput.type = "checkbox";
    memoryInput.id = "firstRunMemory";
    toggle.append(memoryInput, element("span", "slider"));
    memory.append(memoryWords, toggle);

    const next = element("button", "btn-pro first-run-next", t("Continue"));
    next.type = "button";
    // Raw HTML (Settings > Display) is a look, not a step: it switches at
    // once, this dialog included, and a second press takes it back.
    const raw = element("button", "text-link first-run-raw", t("I like it raw"));
    raw.type = "button";
    raw.setAttribute("aria-description", t("Shows the app as plain HTML, the way the browser draws it."));
    setup.append(pitch, question, views, sample, caption, memory, next, raw);

    const consent = element("div", "first-run-step");
    consent.dataset.step = "consent";
    const title = element("h2", "", t("Almost there"));
    title.id = "firstRunConsentTitle";
    const body = element("p", "first-run-lead", t("Your answers come from the leading AI models of these providers:"));
    // Closed, the providers are a row of logos: marks people know reassure,
    // ten names in a list look like work. The names are one click away.
    const providers = element("details", "first-run-providers");
    const summary = element("summary");
    summary.append(element("span", "first-run-logos"), element("span", "first-run-providers-more", t("Show names")));
    const list = element("ul", "confirm-modal-list");
    list.setAttribute("data-i18n-skip", "");
    providers.append(summary, list);
    const note = element("p", "confirm-modal-note", t("Your question only goes to the models working on it."));
    const anchor = element("a", "", t("More in the privacy notice"));
    anchor.href = "/privacy#providers";
    anchor.target = "_blank";
    anchor.rel = "noopener";
    note.append(" ", anchor);
    const accept = element("button", "btn-pro confirm-accept", t("Agree and start"));
    accept.type = "button";
    accept.dataset.answer = "true";
    consent.append(title, body, providers, note, accept);

    content.append(closeButton(), setup, consent);
    dialog.append(content);
    document.body.append(dialog);

    App.modalDialog?.bind(dialog, { onClose: () => answer(null) });
    views.addEventListener("change", showView);
    raw.addEventListener("click", () => {
      App.userSettings?.set?.("raw_display", !rawDisplay(), { source: "first_run" });
      showRaw();
    });
    next.addEventListener("click", () => {
      if (!dialog.classList.contains("has-consent")) return finish(chosen());
      showStep("consent");
      accept.focus({ preventScroll: true });
    });
    dialog.addEventListener("click", event => {
      const button = event.target.closest?.("[data-answer]");
      if (button) finish(button.dataset.answer === "true" ? chosen() : null);
    });
    return dialog;
  }

  // The answer before the close: closing settles the rest as a no.
  function finish(value) {
    answer(value);
    if (App.modalDialog) App.modalDialog.close(dialog);
    else dialog.close();
  }

  function chosen() {
    const view = dialog.querySelector('input[name="firstRunView"]:checked')?.value;
    return {
      view: Object.prototype.hasOwnProperty.call(VIEWS, view) ? view : DEFAULT_VIEW,
      memory: dialog.querySelector("#firstRunMemory").checked,
    };
  }

  // The scene keeps playing; the view decides what it marks (first-run.css).
  function showView() {
    const { view } = chosen();
    dialog.dataset.view = view;
    dialog.querySelector(".first-run-caption").textContent = viewText(view)[1];
  }

  function rawDisplay() {
    return App.userSettings?.get?.("raw_display") === true;
  }

  function showRaw() {
    dialog.querySelector(".first-run-raw").setAttribute("aria-pressed", String(rawDisplay()));
  }

  function showStep(step) {
    dialog.dataset.step = step;
    dialog.setAttribute("aria-labelledby", step === "consent" ? "firstRunConsentTitle" : "firstRunSetupTitle");
  }

  function fillProviders(items) {
    const rows = (Array.isArray(items) ? items : []).filter(item => item?.text).map(item => {
      const row = element("li");
      if (item.icon) {
        const icon = element("img", ["confirm-modal-list-icon", item.iconClass].filter(Boolean).join(" "));
        icon.src = String(item.icon);
        icon.alt = "";
        row.append(icon);
      }
      row.append(element("span", "", String(item.text)));
      return row;
    });
    const providers = dialog.querySelector(".first-run-providers");
    providers.querySelector("ul").replaceChildren(...rows);
    const logos = rows.map(row => row.querySelector("img")?.cloneNode()).filter(Boolean);
    providers.querySelector(".first-run-logos").replaceChildren(...logos);
    // The scene's reviewers wear the first three of the same logos.
    dialog.querySelector(".first-run-reviewers").replaceChildren(...logos.slice(0, 3).map(logo => logo.cloneNode()));
    // Without logos there is no row to stand for the names: show them.
    providers.open = logos.length < rows.length;
  }

  function answer(value) {
    if (!pending) return;
    const { resolve } = pending;
    pending = null;
    resolve(value);
  }

  // steps: both by default; ["consent"] asks only for the agreement (its
  // answer then carries the default view), ["setup"] only the two choices.
  function ask({ providers = [], steps = ["setup", "consent"] } = {}) {
    const node = build();
    answer(null);
    fillProviders(providers);
    node.querySelector(`input[name="firstRunView"][value="${DEFAULT_VIEW}"]`).checked = true;
    node.querySelector("#firstRunMemory").checked = false;
    const setup = steps.includes("setup");
    const consent = steps.includes("consent");
    node.classList.toggle("has-consent", consent);
    node.querySelector(".first-run-next").textContent = consent ? t("Continue") : t("Done");
    showView();
    showRaw();
    showStep(setup ? "setup" : "consent");
    return new Promise(resolve => {
      pending = { resolve };
      const focus = node.querySelector(setup ? ".first-run-next" : ".confirm-accept");
      if (App.modalDialog) App.modalDialog.open(node, { focus });
      else node.showModal();
    });
  }

  function apply(choice) {
    const view = VIEWS[choice?.view];
    if (!view) return;
    Object.entries(view).forEach(([name, value]) => {
      if (value !== null) App.userSettings?.set?.(name, value, { source: "first_run" });
    });
    // What the dialog promises in every view, the agent correcting its
    // answer with the reviewers' findings, is the default (findings_to_agent).
    if (choice.memory) App.userMemory?.enableAgentMemory?.("first_run");
    App.trackAppEvent?.("app_first_run", { view: choice.view, memory: choice.memory === true });
  }

  App.firstRun = { VIEWS, DEFAULT_VIEW, ask, apply };
})();
