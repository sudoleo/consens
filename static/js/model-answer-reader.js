// One turn-scoped reader for live, saved and direct-comparison answers.
// Legacy response boxes remain render/configuration targets; never move them.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const host = document.querySelector(".response-section");
  if (!host) return;

  const composer = document.querySelector('.input-section');
  const composerAnchor = document.createComment('composer-home');
  composer?.before(composerAnchor);
  const stored = new WeakMap();
  const positions = new Map();
  const wideScreen = window.matchMedia("(min-width: 1400px)");
  const pairScreen = window.matchMedia("(min-width: 760px)");
  let live = null;
  let savedDirect = null;
  let selected = null;
  let open = false;
  let direct = false;
  let pair = false;
  let expanded = false;
  let primary = "";
  let secondary = "";
  let mobileSide = "a";
  let opener = null;
  let renderKey = "";
  let pendingSync = null;
  let inspector = null;

  const root = document.createElement("section");
  root.id = "modelAnswerReader";
  root.className = "model-answer-reader";
  root.hidden = true;
  root.setAttribute("aria-label", "Model answers");
  root.innerHTML = `
    <header class="answer-reader-header">
      <div class="answer-reader-heading"><h2 id="answerReaderTitle">Model answers</h2><span id="answerReaderStatus" role="status" aria-live="polite"></span></div>
      <div class="answer-reader-actions">
        <button type="button" id="answerReaderExpand" class="answer-reader-icon-button" aria-pressed="false" aria-label="Expand" title="Expand"></button>
        <button type="button" id="answerReaderClose" class="answer-reader-icon-button" aria-label="Back to chat" title="Back to chat"></button>
      </div>
    </header>
    <p id="answerReaderMode" class="answer-reader-mode" hidden>Agent Mode is off for this comparison. Each model answers independently.</p>
    <div class="answer-reader-context">
      <div class="answer-reader-context-top"><label for="answerReaderTurn">Conversation</label><select id="answerReaderTurn" aria-label="Question in this conversation"></select><span id="answerReaderTurnLabel">Current question</span></div>
      <details id="answerReaderQuestion"><summary><span></span></summary></details>
    </div>
    <nav class="answer-reader-sections" id="answerReaderSections" aria-label="Answer details">
      <button type="button" data-section="answers">Answers</button><button type="button" data-section="differences">Differences</button><button type="button" data-section="sources">Sources</button>
    </nav>
    <div class="answer-reader-toolbar"><span class="answer-reader-nav-label">Explore answers</span><button type="button" id="answerReaderCompare" aria-pressed="false"></button></div>
    <div class="answer-reader-models" id="answerReaderModels" aria-label="Choose a model answer"></div>
    <label class="answer-reader-single" id="answerReaderSingle" hidden>
      <select id="answerReaderModel" aria-label="Model answer"></select>
    </label>
    <div class="answer-reader-pair" id="answerReaderPair" hidden>
      <label>Answer A<select id="answerReaderA"></select></label>
      <label>Answer B<select id="answerReaderB"></select></label>
    </div>
    <div class="answer-reader-mobile-tabs" id="answerReaderMobile" hidden>
      <button type="button" id="answerReaderSideA" aria-pressed="true"></button>
      <button type="button" id="answerReaderSideB" aria-pressed="false"></button>
    </div>
    <div class="answer-reader-scroll" id="answerReaderScroll">
      <div class="answer-reader-columns" id="answerReaderColumns"></div>
      <div class="answer-reader-inspector" id="answerReaderInspector" hidden></div>
    </div>`;
  const dialog = document.createElement("dialog");
  dialog.className = "answer-reader-dialog";
  dialog.setAttribute("aria-labelledby", "answerReaderTitle");
  document.body.appendChild(dialog);
  host.prepend(root);
  const get = id => root.querySelector(`#answerReader${id}`);
  const pickers = new Map();
  let activePicker = null;
  // Small interface icons inherit the app's ink in both themes.
  function icon(name) {
    const paths = { close: 'M6 6l12 12M18 6 6 18', expand: 'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5',
      reduce: 'M3 8h5V3m8 0v5h5M8 21v-5H3m13 5v-5h5', compare: 'M3 5h18v14H3zM12 5v14',
      read: 'M5 4h14v16H5zM9 8h6m-6 4h6', copy: 'M9 9h11v11H9zM15 5V3H3v12h2' };
    return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.read}"/></svg>`;
  }
  function control(button, name, label, iconOnly = false) {
    if (button.dataset.label === label) return;
    button.innerHTML = icon(name);
    if (!iconOnly) { const text = document.createElement("span"); text.textContent = label; button.append(text); }
    button.dataset.label = label;
    button.setAttribute("aria-label", label);
    button.title = label;
  }
  control(get("Close"), "close", "Back to chat", true);
  function modelMark(answer) {
    const mark = document.createElement("span"); mark.className = "answer-reader-model-mark";
    const pref = (App.modelPrefs || []).find(p => normalize(p.key) === normalize(answer.provider) || normalize(p.provider) === normalize(answer.provider));
    const original = pref && document.getElementById(pref.responseId)?.querySelector("img");
    if (original) {
      const image = document.createElement("img"); image.src = original.src; image.alt = "";
      // Preserve the existing dark-theme treatment of monochrome provider logos.
      ['chatgpt-logo', 'grok-logo', 'mono-logo'].forEach(name => {
        if (original.classList.contains(name)) image.classList.add(name);
      });
      mark.append(image);
    } else mark.textContent = answer.label.slice(0, 1).toUpperCase();
    mark.setAttribute("aria-hidden", "true");
    return mark;
  }

  function closePicker(focus = false) {
    if (!activePicker) return;
    const current = activePicker; activePicker = null;
    if (current.menu.hidePopover && current.menu.matches(":popover-open")) current.menu.hidePopover();
    current.menu.hidden = true;
    current.button.setAttribute("aria-expanded", "false");
    if (focus) current.button.focus({ preventScroll: true });
  }
  function placePicker(picker) {
    const rect = picker.button.getBoundingClientRect();
    const bounds = root.getBoundingClientRect();
    const leftEdge = Math.max(12, bounds.left + 12);
    const rightEdge = Math.min(window.innerWidth - 12, bounds.right - 12);
    const width = Math.min(Math.max(rect.width, picker.select.id.endsWith("Turn") ? 320 : 240), rightEdge - leftEdge);
    const below = window.innerHeight - rect.bottom - 12;
    const above = rect.top - 12;
    const up = below < 220 && above > below;
    Object.assign(picker.menu.style, { width: `${width}px`, left: `${Math.max(leftEdge, Math.min(rect.right - width, rightEdge - width))}px`,
      top: up ? "auto" : `${rect.bottom + 6}px`, bottom: up ? `${window.innerHeight - rect.top + 6}px` : "auto",
      maxHeight: `${Math.max(80, Math.min(360, (up ? above : below) - 6))}px` });
  }
  function updatePicker(select, descriptions = []) {
    let picker = pickers.get(select);
    if (!picker) {
      const wrapper = document.createElement("span"); wrapper.className = "answer-reader-picker";
      const button = document.createElement("button"); button.type = "button";
      button.id = `${select.id}Picker`; button.className = "answer-reader-picker-button";
      button.setAttribute("aria-haspopup", "listbox"); button.setAttribute("aria-expanded", "false");
      const label = select.getAttribute("aria-label") || (select.id.endsWith("A") ? "Answer A" : "Answer B");
      button.setAttribute("aria-label", label);
      const menu = document.createElement("div"); menu.className = "answer-reader-picker-menu";
      menu.id = `${select.id}Options`; menu.setAttribute("role", "listbox"); menu.setAttribute("aria-label", label);
      menu.setAttribute("popover", "manual"); menu.hidden = true;
      button.setAttribute("aria-controls", menu.id);
      select.before(wrapper); wrapper.append(button, menu);
      select.style.display = "none"; select.setAttribute("aria-hidden", "true"); select.tabIndex = -1;
      picker = { select, wrapper, button, menu }; pickers.set(select, picker);
      button.addEventListener("click", () => {
        if (activePicker === picker) { closePicker(true); return; }
        closePicker(); activePicker = picker; menu.hidden = false;
        if (menu.showPopover) menu.showPopover();
        placePicker(picker); button.setAttribute("aria-expanded", "true");
        menu.querySelector('[aria-selected="true"]')?.focus({ preventScroll: true });
      });
      button.addEventListener("keydown", event => {
        if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); button.click(); }
      });
      let search = ""; let searchTime = 0;
      menu.addEventListener("keydown", event => {
        const items = Array.from(menu.children); const index = items.indexOf(document.activeElement);
        let next;
        if (event.key === "ArrowDown") next = (index + 1) % items.length;
        if (event.key === "ArrowUp") next = (index - 1 + items.length) % items.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = items.length - 1;
        if (event.key.length === 1 && event.key !== " " && !event.ctrlKey && !event.metaKey && !event.altKey) {
          const now = Date.now(); search = (now - searchTime < 700 ? search : "") + event.key.toLowerCase(); searchTime = now;
          const match = items.findIndex(item => item.querySelector('.answer-reader-option-text > span')?.textContent.toLowerCase().startsWith(search));
          if (match >= 0) next = match;
        }
        if (next !== undefined) { event.preventDefault(); items[next]?.focus(); }
        if (event.key === "Tab") closePicker(true);
      });
    }
    picker.wrapper.hidden = select.hidden;
    picker.button.disabled = select.disabled;
    const current = select.options[select.selectedIndex];
    picker.button.setAttribute("aria-label", `${picker.menu.getAttribute("aria-label")}: ${current?.textContent || "Choose"}`);
    picker.button.replaceChildren();
    const answer = selected?.answers.find(a => a.provider === select.value);
    if (answer && !select.id.endsWith("Turn")) picker.button.append(modelMark(answer));
    const title = document.createElement("span"); title.textContent = current?.textContent || "Choose";
    picker.button.append(title);
    const arrow = document.createElement("span"); arrow.className = "answer-reader-chevron"; arrow.setAttribute("aria-hidden", "true"); picker.button.append(arrow);
    const signature = JSON.stringify([select.dataset.options, select.value, descriptions]);
    if (picker.menu.dataset.signature !== signature) {
      const focused = picker.menu.contains(document.activeElement) ? document.activeElement.dataset.value : null;
      picker.menu.replaceChildren(...Array.from(select.options).map((option, i) => {
        const item = document.createElement("button"); item.type = "button"; item.tabIndex = -1;
        item.setAttribute("role", "option"); item.setAttribute("aria-selected", String(option.selected)); item.dataset.value = option.value;
        const model = selected?.answers.find(a => a.provider === option.value);
        if (model && !select.id.endsWith("Turn")) item.append(modelMark(model));
        const text = document.createElement("span"); text.className = "answer-reader-option-text";
        const name = document.createElement("span"); name.textContent = option.textContent; text.append(name);
        if (descriptions[i]) { const detail = document.createElement("small"); detail.textContent = descriptions[i]; text.append(detail); }
        const check = document.createElement("span"); check.className = "answer-reader-option-check"; check.textContent = "✓"; check.setAttribute("aria-hidden", "true");
        item.append(text, check);
        item.addEventListener("click", () => { select.value = option.value; closePicker(true); select.dispatchEvent(new Event("change", { bubbles: true })); });
        return item;
      }));
      picker.menu.dataset.signature = signature;
      if (focused) Array.from(picker.menu.children).find(item => item.dataset.value === focused)?.focus({ preventScroll: true });
    }
    if (activePicker === picker) {
      if (!picker.button.getClientRects().length) closePicker(); else placePicker(picker);
    }
  }
  document.addEventListener("pointerdown", event => {
    if (activePicker && !activePicker.wrapper.contains(event.target)) closePicker();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && activePicker) { event.preventDefault(); event.stopImmediatePropagation(); closePicker(true); }
  }, true);
  window.addEventListener("resize", () => { if (activePicker) placePicker(activePicker); });
  document.addEventListener("scroll", event => {
    if (activePicker && !activePicker.menu.contains(event.target)) closePicker();
  }, true);

  function normalize(value) { return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, ""); }
  function selectedTurn() {
    return Array.from(document.querySelectorAll('.thread-history-turn')).find(node => {
      const turn = stored.get(node); return turn && keyFor(turn) === selected?.key;
    }) || null;
  }
  function panelNodes(kind, turn) {
    if (turn) {
      const content = turn.querySelector(kind === "differences" ? '.thread-history-differences' : '.thread-history-sources');
      if (content) return [content];
      if (kind === "differences") return Array.from(turn.querySelectorAll('.thread-history-detail-body'));
      return [];
    }
    if (kind === "sources") return [document.getElementById('consensusSourcesList')].filter(Boolean);
    const cards = document.getElementById('differencesCards');
    if (cards && !cards.hidden && cards.childNodes.length) return [cards];
    const fallback = document.querySelector('#consensusDifferencesPanel .consensus-differences-content > p');
    // Keep the legacy streaming target in place; its text is only a fallback.
    return fallback ? [fallback.cloneNode(true)] : [];
  }
  function releaseInspector() {
    if (!inspector) return;
    for (const item of inspector.items) {
      if (item.placeholder.parentNode) item.placeholder.replaceWith(item.node);
      else item.node.remove();
    }
    inspector.trigger?.setAttribute('aria-expanded', 'false');
    inspector = null; get('Inspector').replaceChildren();
  }
  function polishInspector() {
    const allCards = get('Inspector').querySelectorAll('.diff-card');
    get('Inspector').querySelectorAll('.diff-card:not([data-reader-ready])').forEach(card => {
      const key = card.querySelector('.diff-card-claim')?.textContent;
      if (!inspector.seenClaims.has(key) && allCards.length === 1) inspector.expanded.add(key);
      inspector.seenClaims.add(key);
      card.dataset.readerReady = 'true'; card.open = inspector.expanded.has(key);
      const meta = document.createElement('span'); meta.className = 'answer-reader-diff-meta';
      const count = card.querySelectorAll('.diff-position').length;
      meta.textContent = `${count} ${count === 1 ? 'position' : 'positions'}`;
      card.querySelector('summary')?.append(meta);
    });
    get('Inspector').querySelectorAll('.consensus-source-snippet:not([data-reader-ready])').forEach(snippet => {
      snippet.dataset.readerReady = 'true';
      const disclosure = document.createElement('details'); disclosure.className = 'answer-reader-source-excerpt';
      const summary = document.createElement('summary'); summary.textContent = 'Source excerpt';
      snippet.before(disclosure); disclosure.append(summary, snippet);
    });
    get('Inspector').querySelectorAll('.thread-history-sources > li:not([data-reader-ready])').forEach(item => {
      item.dataset.readerReady = 'true';
      const link = item.querySelector('a'); if (!link) return;
      const body = document.createElement('div'); body.className = 'consensus-source-body';
      const domain = document.createElement('span'); domain.className = 'consensus-source-host';
      domain.textContent = new URL(link.href).hostname.replace(/^www\./, '');
      link.classList.add('consensus-source-title'); item.append(body); body.append(link, domain);
    });
    polishSources(get('Inspector'));
  }
  function polishSources(container) {
    container.querySelectorAll('.consensus-source-item, .thread-history-sources > li, .answer-reader-sources li').forEach((item, index) => {
      if (item.dataset.sourcePolished) return;
      item.dataset.sourcePolished = 'true'; item.classList.add('answer-reader-source-card');
      const link = item.querySelector('a');
      let url; try { url = link && new URL(link.href); } catch (_) {}
      const hostName = url?.hostname.replace(/^www\./, '') || '';
      let body = item.querySelector('.consensus-source-body');
      if (!body) {
        body = document.createElement('div'); body.className = 'consensus-source-body';
        body.append(...Array.from(item.childNodes)); item.append(body);
      }
      let domain = body.querySelector('.consensus-source-host');
      if (!domain) { domain = document.createElement('span'); domain.className = 'consensus-source-host'; domain.textContent = hostName || 'Reference'; }
      body.prepend(domain); link?.classList.add('consensus-source-title');
      const badge = document.createElement('span'); badge.className = 'answer-reader-site-icon'; badge.setAttribute('aria-hidden', 'true');
      const fallback = document.createElement('span'); fallback.textContent = (hostName || 'S').slice(0, 1).toUpperCase(); badge.append(fallback);
      if (hostName) {
        const img = document.createElement('img'); img.alt = ''; img.width = 20; img.height = 20; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer';
        img.src = '/api/topics/favicon?d=' + encodeURIComponent(hostName);
        img.addEventListener('load', () => { fallback.hidden = true; });
        img.addEventListener('error', () => { img.remove(); fallback.hidden = false; }); badge.append(img);
      }
      item.prepend(badge);
      let number = item.querySelector('.consensus-source-index');
      if (!number) { number = document.createElement('span'); number.className = 'consensus-source-index'; number.textContent = String(index + 1); item.append(number); }
      if (link) {
        const arrow = document.createElement('span'); arrow.className = 'answer-reader-source-out'; arrow.setAttribute('aria-hidden', 'true'); arrow.textContent = '↗'; item.append(arrow);
      }
    });
  }
  function openPanel(kind, trigger, turn = null, index = null) {
    if (inspector?.kind === kind && inspector.turn === turn && trigger && index === null) { close(); return true; }
    releaseInspector(); closePicker(); savePosition();
    const data = turn && stored.get(turn);
    const snapshot = data ? fromStored(data) : (App.runRegistry?.visible?.() ? fromRun(App.runRegistry.visible()) : fromDOM());
    const nodes = panelNodes(kind, turn);
    selected = snapshot; if (!turn) live = snapshot;
    open = true; direct = false; pair = false; opener = trigger || document.activeElement;
    inspector = { kind, turn, trigger, items: [], expanded: new Set(), seenClaims: new Set() };
    for (const node of nodes) {
      const placeholder = document.createComment('answer-reader-panel');
      if (node.parentNode) node.before(placeholder);
      inspector.items.push({ node, placeholder }); get('Inspector').append(node);
    }
    if (!get('Inspector').textContent.trim()) {
      const empty = document.createElement('p'); empty.className = 'answer-reader-inspector-empty';
      empty.textContent = kind === 'sources' ? 'No sources are available for this question.' : 'No differences analysis is available for this question yet.';
      get('Inspector').append(empty);
    }
    polishInspector(); render(); get('Scroll').scrollTop = 0;
    trigger?.setAttribute('aria-expanded', 'true'); get('Close').focus({ preventScroll: true });
    if (index !== null) {
      const card = get('Inspector').querySelectorAll('.diff-card')[index];
      if (card) { card.open = true; card.scrollIntoView({ block: 'nearest' }); }
    }
    return true;
  }
  new MutationObserver(() => { if (inspector) polishInspector(); }).observe(get('Inspector'), { childList: true, subtree: true });
  get('Inspector').addEventListener('toggle', event => {
    if (!inspector || !event.target.matches('.diff-card') || !get('Inspector').contains(event.target)) return;
    const key = event.target.querySelector('.diff-card-claim')?.textContent;
    if (event.target.open) inspector.expanded.add(key); else inspector.expanded.delete(key);
  }, true);
  get('Sections').addEventListener('click', event => {
    const kind = event.target.closest('[data-section]')?.dataset.section; if (!kind) return;
    const turn = inspector?.turn || selectedTurn();
    if (kind === 'answers') {
      const snapshot = selected; openSnapshot(snapshot, null, opener);
    } else if (inspector?.kind !== kind) openPanel(kind, null, turn);
  });
  function keyFor(turn) {
    if (turn.turn_id) return `turn:${turn.turn_id}`;
    // Old bookmarks have no turn ID. Include both question and answer so two
    // repeated questions with different results cannot share a reading state.
    return `legacy:${JSON.stringify([turn.question, turn.consensus || ""])}`;
  }
  function fromStored(turn) {
    return {
      key: keyFor(turn), question: String(turn.question || ""), runId: null,
      answers: Object.entries(turn.model_answers || {}).map(([provider, raw]) => {
        const item = typeof raw === "string" ? { answer: raw } : raw || {};
        return { provider: String(item.provider || provider), label: String(item.model_label || item.provider || provider),
          text: String(item.answer || ""), sources: Array.isArray(item.sources) ? item.sources : turn.sources || [],
          status: "complete" };
      }).filter(item => item.text.trim())
    };
  }
  function fromRun(context) {
    const completed = context.consensus?.completedTurn;
    return {
      key: completed?.turn_id ? `turn:${completed.turn_id}` : `run:${context.runId}`,
      runId: context.runId, question: String(context.question || ""),
      answers: (context.config?.providers || []).map(config => {
        const result = context.modelResults?.[config.provider] || {};
        return { provider: config.provider, label: config.modelLabel || config.provider,
          text: String(result.text || result.streamText || ""), status: result.status || "pending",
          error: result.error?.message || result.error, sources: result.sources || context.evidenceSources || [] };
      })
    };
  }
  function fromDOM() {
    const turn = App.followup?.lastExchange?.turn;
    if (turn?.model_answers && !document.body.classList.contains("direct-comparison-active")) return fromStored(turn);
    const answers = (App.modelPrefs || []).flatMap(pref => {
      const box = document.getElementById(pref.responseId);
      if (!box || box.classList.contains("excluded")) return [];
      const content = box.querySelector(".collapsible-content");
      const waiting = box.dataset.responseState === 'pending';
      const text = String(box.dataset.consensusAnswer || "");
      if (!waiting && !text && !content?.textContent?.trim()) return [];
      let sources = window.currentEvidenceSources || [];
      try { sources = JSON.parse(box.dataset.consensusSources || "null") || sources; } catch (_) {}
      return [{ provider: pref.key, label: document.getElementById(pref.textId)?.textContent || pref.label || pref.key,
        text: waiting ? "" : text || content?.textContent || "", html: waiting || text ? null : content?.innerHTML, sources,
        status: box.dataset.responseSkipped === "true" ? "skipped" : box.dataset.responseState || "complete",
        error: box.dataset.responseError === "true" ? content?.textContent : "" }];
    });
    const question = String(window.lastQuestion || App.followup?.lastExchange?.question
      || document.getElementById("threadAskText")?.textContent || "");
    return { key: turn ? keyFor(turn) : `dom:${question}`, question, answers, runId: null };
  }
  function turns() {
    const result = Array.from(document.querySelectorAll(".thread-history-turn"))
      .map(node => stored.get(node)).filter(Boolean).map(fromStored);
    if (live?.answers.length) result.push(live);
    if (selected && !result.some(item => item.key === selected.key)) result.unshift(selected);
    return result.filter((item, i, list) => list.findIndex(other => other.key === item.key) === i);
  }
  function findProvider(model, snapshot = selected) {
    const pref = (App.modelPrefs || []).find(item => normalize(item.key) === normalize(model)
      || normalize(item.responseId) === normalize(model));
    const aliases = { claude: "anthropic", gpt: "openai", muse: "meta" };
    const wanted = aliases[normalize(model)] || normalize(pref?.key || model);
    return snapshot?.answers.find(item => normalize(item.provider) === wanted || normalize(item.label) === normalize(model))?.provider;
  }
  function positionKey() { return JSON.stringify([selected?.key, primary, pair ? secondary : "", mobileSide]); }
  function scrollArea() { return root.scrollHeight > root.clientHeight + 1 ? root : get("Scroll"); }
  function savePosition() {
    if (!selected) return;
    positions.set(positionKey(), direct
      ? Math.max(0, 80 - root.getBoundingClientRect().top)
      : scrollArea().scrollTop);
    if (positions.size > 100) positions.delete(positions.keys().next().value);
  }
  function restorePosition() {
    const top = positions.get(positionKey()) || 0;
    if (direct) {
      const y = root.getBoundingClientRect().top + window.scrollY;
      window.scrollTo({ top: Math.max(0, y + top - 80), behavior: "instant" });
    } else scrollArea().scrollTop = top;
  }
  function chooseModels() {
    if (!selected?.answers.some(a => a.provider === primary)) primary = selected?.answers[0]?.provider || "";
    if (secondary === primary || !selected?.answers.some(a => a.provider === secondary)) {
      secondary = selected?.answers.find(a => a.provider !== primary)?.provider || "";
    }
    if (!secondary) pair = false;
  }
  function modeLayout() {
    root.hidden = !open && !direct;
    const modal = open && !direct && (!wideScreen.matches || expanded || pair);
    const docked = open && !direct && !modal;
    document.body.classList.toggle("answer-reader-docked", docked);
    document.body.classList.toggle("answer-reader-modal", modal);
    root.classList.toggle("is-direct", direct);
    if (composer && composerAnchor.parentNode) {
      if (direct && host.nextElementSibling !== composer) host.after(composer);
      else if (!direct && composerAnchor.nextSibling !== composer) composerAnchor.after(composer);
    }
    dialog.classList.toggle("is-docked", docked);
    if (direct) {
      if (dialog.open) dialog.close();
      if (root.parentElement !== host) host.prepend(root);
    } else if (open) {
      if (root.parentElement !== dialog) dialog.appendChild(root);
      if (dialog.open && dialog.dataset.modal !== String(modal)) dialog.close();
      if (!dialog.open) {
        dialog.dataset.modal = String(modal);
        if (modal) dialog.showModal(); else dialog.show();
      }
    } else if (dialog.open) dialog.close();
    get("Close").hidden = direct;
    get("Expand").hidden = direct || !wideScreen.matches || pair;
    control(get("Expand"), expanded ? "reduce" : "expand", expanded ? "Reduce" : "Expand", true);
    get("Expand").setAttribute("aria-pressed", String(expanded));
  }
  function fillSelect(select, options, value) {
    const signature = JSON.stringify(options);
    if (select.dataset.options !== signature) {
      select.replaceChildren(...options.map(([key, label]) => new Option(label, key)));
      select.dataset.options = signature;
    }
    select.value = value;
  }
  function stateLabel(answer) {
    return ({ complete: "Ready", pending: "Waiting", reasoning: "Reasoning", streaming: "Writing",
      error: "Failed", skipped: "Skipped", canceled: "Stopped", idle: "Waiting" })[answer.status] || "Waiting";
  }
  function pane(answer, side) {
    const article = document.createElement("article");
    article.dataset.side = side;
    article.className = "answer-reader-answer";
    article.setAttribute("aria-label", `${answer.label} answer`);
    const header = document.createElement("header");
    header.className = "answer-reader-answer-header";
    const title = document.createElement("h3");
    const providerName = ({ OpenAI: 'ChatGPT', Anthropic: 'Claude', Meta: 'Muse' })[answer.provider] || answer.provider;
    const knownModel = answer.label && answer.label !== 'Model not recorded';
    title.textContent = direct ? providerName : (knownModel ? answer.label : providerName);
    const status = document.createElement("span");
    status.className = "answer-reader-state";
    status.textContent = stateLabel(answer);
    status.dataset.state = answer.status;
    status.hidden = answer.status === "complete";
    const identity = document.createElement("div"); identity.className = "answer-reader-identity";
    const caption = document.createElement("span"); caption.className = "answer-reader-caption"; caption.textContent = direct
      ? (knownModel && answer.label !== answer.provider ? answer.label : 'Model version unavailable')
      : 'Original response';
    const names = document.createElement("div"); names.append(title, caption);
    identity.append(modelMark(answer), names);
    header.append(identity, status);
    const body = document.createElement("div");
    body.className = "consensus-answer-body answer-reader-body";
    body.dataset.provider = answer.provider;
    if (answer.text && !answer.error) {
      if (window.injectMarkdown) window.injectMarkdown(body, answer.html || answer.text, answer.sources);
      else body.textContent = answer.text;
    } else {
      body.classList.add("is-empty");
      body.hidden = direct && !answer.error && ['pending', 'idle', 'reasoning', 'streaming'].includes(answer.status);
      body.textContent = String(answer.error || ({ pending: "Waiting for this model…", reasoning: "This model is reasoning…",
        streaming: "This model is writing…", skipped: "This model was skipped.", canceled: "This model was stopped.",
        error: "This model could not answer." })[answer.status] || "No answer is available.");
    }
    const actions = document.createElement("div");
    actions.className = "answer-reader-answer-actions";
    const copy = document.createElement("button");
    copy.type = "button";
    control(copy, "copy", "Copy answer");
    copy.setAttribute("aria-live", "polite");
    copy.disabled = !answer.text || Boolean(answer.error);
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(answer.text); control(copy, "copy", "Copied"); }
      catch (_) { control(copy, "copy", "Copy unavailable"); }
    });
    actions.append(copy);
    article.append(header, body);
    if (!direct) article.append(actions);
    if (answer.sources?.length) {
      const details = document.createElement("details");
      details.className = "answer-reader-sources";
      const summary = document.createElement("summary");
      summary.textContent = `Sources · ${answer.sources.length}`;
      const list = document.createElement("ol");
      answer.sources.forEach(source => {
        const li = document.createElement("li");
        let url;
        try { url = new URL(source.url); } catch (_) {}
        const link = document.createElement(url && ["https:", "http:"].includes(url.protocol) ? "a" : "span");
        link.textContent = String(source.title || source.url || "Source");
        if (link.tagName === "A") { link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; }
        li.appendChild(link); list.appendChild(li);
      });
      details.append(summary, list); article.appendChild(details);
      polishSources(article);
      // injectMarkdown already gives citations safe URLs and source metadata
      // from this answer. Preserve native link / modifier-click behaviour.
    }
    return article;
  }
  function render() {
    modeLayout();
    if ((!open && !direct) || !selected) return;
    chooseModels();
    const options = turns().map((turn, i) => [turn.key, `Question ${i + 1}`]);
    fillSelect(get("Turn"), options, selected.key);
    get("Turn").disabled = options.length < 2;
    get("Turn").hidden = options.length < 2;
    get("TurnLabel").hidden = options.length > 1;
    root.querySelector('.answer-reader-context-top label').hidden = options.length < 2;
    get("Question").querySelector("summary span").textContent = selected.question || "Question";
    const questionText = get('Question').querySelector('summary span');
    const longQuestion = questionText.scrollHeight > questionText.clientHeight + 1;
    // Measure the collapsed text; expanded questions retain their close control.
    get('Question').classList.toggle('is-truncated', longQuestion || get('Question').open);
    get('Question').querySelector('summary').tabIndex = longQuestion || get('Question').open ? 0 : -1;
    get('Question').querySelector('summary').setAttribute('aria-disabled', String(!longQuestion && !get('Question').open));
    get('Sections').hidden = direct;
    get('Sections').querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.section === (inspector?.kind || 'answers'))));
    root.classList.toggle('is-inspecting', !!inspector);
    get('Inspector').hidden = !inspector; get('Columns').hidden = !!inspector;
    get('Title').textContent = inspector ? (inspector.kind === 'differences' ? 'Differences' : 'Sources') : (direct ? 'Direct comparison' : 'Model answers');
    get('Mode').hidden = !direct;
    if (inspector) {
      inspector.trigger?.setAttribute('aria-expanded', 'true');
      get('Status').textContent = inspector.kind === 'differences' ? 'Compare claims, then explore the detail' : 'References for this answer';
      fillSelect(get('Turn'), options, selected.key);
      updatePicker(get('Turn'), turns().map(turn => turn.question));
      syncTriggers();
      return;
    }
    const compactNavigation = (root.clientWidth || (pairScreen.matches ? 900 : 390)) < 500;
    get("Models").hidden = pair || compactNavigation;
    get("Single").hidden = pair || !compactNavigation;
    fillSelect(get("Model"), selected.answers.map(a => [a.provider, a.label + (a.status === "complete" ? "" : ` · ${stateLabel(a)}`)]), primary);
    const navigationKey = JSON.stringify(selected.answers.map(a => [a.provider, a.label]));
    if (get("Models").dataset.key !== navigationKey) {
      get("Models").replaceChildren(...selected.answers.map(answer => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.provider = answer.provider;
        const label = document.createElement("span"); label.className = "answer-reader-model-name"; label.textContent = answer.label;
        const dot = document.createElement("span"); dot.className = "answer-reader-model-dot"; dot.setAttribute("aria-hidden", "true");
        button.append(modelMark(answer), label, dot);
        button.addEventListener("click", () => { savePosition(); primary = answer.provider; mobileSide = "a"; render(); restorePosition(); });
        return button;
      }));
      get("Models").dataset.key = navigationKey;
    }
    Array.from(get("Models").children).forEach((button, i) => {
      const answer = selected.answers[i];
      const label = `${answer.label} · ${stateLabel(answer)}`;
      button.setAttribute("aria-label", label);
      button.title = label;
      button.dataset.state = answer.status;
      button.setAttribute("aria-pressed", String(answer.provider === primary));
    });
    const count = selected.answers.filter(a => a.status === "complete").length;
    const failures = selected.answers.filter(a => ["error", "skipped", "canceled"].includes(a.status)).length;
    const statusText = `${count} of ${selected.answers.length} ready${failures ? ` · ${failures} unavailable` : ""}`;
    if (get("Status").textContent !== statusText) get("Status").textContent = statusText;
    get("Compare").disabled = selected.answers.length < 2;
    control(get("Compare"), pair ? "read" : "compare", pair ? "Read one" : "Compare two");
    get("Compare").setAttribute("aria-pressed", String(pair));
    get("Pair").hidden = !pair;
    const modelOptions = selected.answers.map(a => [a.provider, a.label]);
    fillSelect(get("A"), modelOptions, primary); fillSelect(get("B"), modelOptions, secondary);
    ["Turn", "Model", "A", "B"].forEach(id => updatePicker(get(id), id === "Turn" ? turns().map(turn => turn.question) : []));
    const readingWidth = get("Scroll").clientWidth || root.clientWidth;
    const roomForPair = readingWidth ? readingWidth >= 760 : pairScreen.matches;
    get("Mobile").hidden = !pair || roomForPair;
    const a = selected.answers.find(item => item.provider === primary);
    const b = selected.answers.find(item => item.provider === secondary);
    get("SideA").textContent = a?.label || "Answer A"; get("SideB").textContent = b?.label || "Answer B";
    get("SideA").setAttribute("aria-pressed", String(mobileSide === "a"));
    get("SideB").setAttribute("aria-pressed", String(mobileSide === "b"));
    const columns = get("Columns");
    columns.classList.toggle("is-pair", pair && !direct);
    columns.classList.toggle("is-grid", direct);
    columns.classList.toggle("is-narrow", !roomForPair);
    columns.dataset.mobileSide = mobileSide;
    const visibleAnswers = direct ? selected.answers : [a, pair ? b : null].filter(Boolean);
    const nextKey = JSON.stringify([selected.key, direct, visibleAnswers]);
    if (renderKey !== nextKey) {
      const scroller = scrollArea();
      const scroll = scroller.scrollTop;
      if (direct) {
        // A streaming sibling must not destroy selection, focus or open sources
        // in an answer that the user is already reading.
        visibleAnswers.forEach((answer, index) => {
          const signature = JSON.stringify([selected.key, answer]);
          const current = columns.children[index];
          if (current?.dataset.answerKey === signature) return;
          const next = pane(answer, index === 0 ? "a" : "b");
          next.dataset.answerKey = signature;
          if (current) current.replaceWith(next); else columns.append(next);
        });
        while (columns.children.length > visibleAnswers.length) columns.lastElementChild.remove();
      } else {
        columns.replaceChildren(...visibleAnswers.map((answer, index) => pane(answer, index === 0 ? "a" : "b")));
      }
      renderKey = nextKey;
      scroller.scrollTop = scroll;
    }
    syncTriggers();
  }
  function syncTriggers() {
    [['consensusDifferencesTab', 'differences'], ['consensusSourcesTab', 'sources']].forEach(([id, kind]) => {
      document.getElementById(id)?.setAttribute('aria-expanded', String(open && inspector?.kind === kind && !inspector.turn));
    });
    const toggle = document.getElementById("agentModeAnswersToggle");
    if (toggle) {
      const active = open && !inspector && selected?.key === live?.key;
      toggle.setAttribute("aria-expanded", String(active));
      toggle.setAttribute("aria-controls", root.id);
      toggle.setAttribute("aria-label", active ? "Hide answers" : "Compare answers");
      toggle.title = active ? "Hide answers" : "Compare answers";
      const label = toggle.querySelector(".consensus-tab-label");
      if (label) {
        const text = active ? "Hide answers" : "Compare answers";
        if (label.textContent !== text) label.textContent = text;
        label.dataset.short = active ? "Hide" : "Answers";
      }
    }
    document.querySelectorAll(".answer-reader-trigger").forEach(button => {
      const data = stored.get(button.closest(".thread-history-turn"));
      button.setAttribute("aria-expanded", String(open && !inspector && data && keyFor(data) === selected?.key));
    });
  }
  function close({ focus = true } = {}) {
    releaseInspector();
    closePicker();
    savePosition(); open = false; expanded = false;
    render(); syncTriggers();
    if (focus && !direct) {
      const target = opener?.isConnected ? opener : document.getElementById("agentModeAnswersToggle");
      target?.focus?.({ preventScroll: true });
    }
  }
  function openSnapshot(snapshot, model, trigger, quote) {
    if (!snapshot?.answers.length) return false;
    releaseInspector();
    savePosition();
    selected = snapshot;
    primary = findProvider(model, snapshot) || primary;
    if (model) { pair = false; mobileSide = "a"; }
    opener = trigger || document.activeElement;
    open = true;
    render(); restorePosition();
    if (!direct) get("Close").focus({ preventScroll: true });
    if (quote) {
      const body = Array.from(root.querySelectorAll(".answer-reader-body"))
        .find(node => node.dataset.provider === primary);
      const needle = String(quote).replace(/\s+/g, " ").trim().toLowerCase();
      const block = Array.from(body?.querySelectorAll("p,li,blockquote,td,pre") || [])
        .find(node => node.textContent.replace(/\s+/g, " ").toLowerCase().includes(needle));
      if (block && needle) {
        block.classList.add("quote-flash-block");
        block.scrollIntoView({ block: "center" });
        window.setTimeout(() => block.classList.remove("quote-flash-block"), 2400);
      }
    }
    return true;
  }
  function update(next, isDirect) {
    const previous = live;
    const changedRun = previous && previous.runId !== next.runId;
    // The live inspector holds the shared render targets, not an immutable
    // turn snapshot. Release it when those targets start serving another run.
    if (changedRun && inspector && !inspector.turn) close({ focus: false });
    live = next;
    if (changedRun && open) {
      const history = turns().filter(t => t !== selected && t !== live);
      const sameTurn = history.find(t => t.key === selected?.key || (t.question === selected?.question
        && t.answers.some(a => selected.answers.some(b => a.provider === b.provider && a.text === b.text))));
      if (sameTurn) selected = sameTurn;
      else close({ focus: false });
    }
    if (!selected || direct || isDirect || (!changedRun && selected.key === previous?.key)
      || (selected.runId && selected.runId === next.runId)) selected = next;
    if (direct !== isDirect) { if (direct) open = false; direct = isDirect; }
    render();
  }
  function syncDOM() {
    pendingSync = null;
    if (App.runRegistry?.visible?.()) return;
    const isDirect = document.body.classList.contains("direct-comparison-active");
    const next = isDirect && savedDirect ? savedDirect : fromDOM();
    if (next.answers.length) update(next, isDirect);
    else { direct = false; close({ focus: false }); live = null; selected = null; }
  }
  function scheduleSync() {
    if (pendingSync === null) pendingSync = window.setTimeout(syncDOM, 60);
  }

  get("Close").addEventListener("click", () => close());
  dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
  dialog.addEventListener("keydown", event => { if (event.key === "Escape" && dialog.dataset.modal === "false") close(); });
  let backdropPress = false;
  const onBackdrop = event => {
    const rect = dialog.getBoundingClientRect();
    return event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom);
  };
  dialog.addEventListener("pointerdown", event => { backdropPress = onBackdrop(event); });
  dialog.addEventListener("click", event => {
    if (backdropPress && onBackdrop(event) && dialog.dataset.modal === "true") close();
    backdropPress = false;
  });
  get("Expand").addEventListener("click", () => { expanded = !expanded; render(); get("Expand").focus(); });
  get("Compare").addEventListener("click", () => { savePosition(); pair = !pair; mobileSide = "a"; render(); restorePosition(); get("Compare").focus(); });
  get("Turn").addEventListener("change", () => {
    const kind = inspector?.kind;
    savePosition(); selected = turns().find(turn => turn.key === get("Turn").value) || selected;
    get("Question").open = false;
    if (kind) { openPanel(kind, null, selectedTurn()); return; }
    render(); restorePosition();
  });
  get('Question').querySelector('summary').addEventListener('click', event => {
    if (!get('Question').classList.contains('is-truncated')) event.preventDefault();
  });
  get("Model").addEventListener("change", () => {
    savePosition(); primary = get("Model").value; mobileSide = "a"; render(); restorePosition();
  });
  ["A", "B"].forEach(side => get(side).addEventListener("change", () => {
    savePosition();
    const next = get(side).value;
    if (side === "A") { if (next === secondary) secondary = primary; primary = next; }
    else { if (next === primary) primary = secondary; secondary = next; }
    render(); restorePosition();
  }));
  ["a", "b"].forEach(side => get(side === "a" ? "SideA" : "SideB").addEventListener("click", () => {
    savePosition(); mobileSide = side; render(); restorePosition();
  }));
  const resize = () => { const scroll = get("Scroll").scrollTop; render(); get("Scroll").scrollTop = scroll; };
  wideScreen.addEventListener("change", resize); pairScreen.addEventListener("change", resize);
  if (window.ResizeObserver) {
    let lastWidth = 0;
    new ResizeObserver(entries => {
      const width = Math.round(entries[0].contentRect.width);
      if (width !== lastWidth) { lastWidth = width; resize(); }
    }).observe(root);
  }
  new MutationObserver(records => {
    if (records.some(record => (record.target.nodeType === 1 ? record.target : record.target.parentElement)
      ?.closest?.(".response-box"))) scheduleSync();
  }).observe(host, { childList: true, subtree: true, attributes: true,
    attributeFilter: ["data-response-state", "data-consensus-answer", "data-response-error", "data-response-skipped"] });
  // The observer above also sees the inline reader. Only schedule a DOM sync
  // for legacy render targets, not for the reader's own mutations.
  let bodyMode = document.body.classList.contains("direct-comparison-active");
  new MutationObserver(() => {
    const mode = document.body.classList.contains("direct-comparison-active");
    if (mode !== bodyMode) { bodyMode = mode; scheduleSync(); }
  }).observe(document.body, { attributes: true, attributeFilter: ["class"] });
  window.addEventListener("consensio:run-registry-change", event => {
    if (["saved-view", "visible-cleared", "reset"].includes(event.detail?.type)) {
      direct = false; close({ focus: false }); live = null; savedDirect = null; selected = null; positions.clear(); scheduleSync();
    }
  });

  App.answerReader = Object.freeze({
    close,
    openPanel,
    project(context) { if (context) { savedDirect = null; update(fromRun(context), context.config?.agentMode === false); } },
    showDirectBookmark(bookmark) {
      const modelAnswers = {};
      (App.modelPrefs || []).forEach(pref => {
        const answer = bookmark.responses?.[pref.key];
        if (typeof answer === 'string' && answer.trim()) modelAnswers[pref.key] = {
          answer, model_label: bookmark.model_labels?.[pref.key] || pref.key,
          sources: bookmark.sources || []
        };
      });
      savedDirect = fromStored({turn_id: `bookmark:${bookmark.id || ''}`, question: bookmark.query,
        model_answers: modelAnswers});
      update(savedDirect, true);
    },
    openLive(model, quote, trigger) {
      const context = App.runRegistry?.visible?.();
      live = context ? fromRun(context) : fromDOM();
      return openSnapshot(live, model, trigger, quote);
    },
    toggleLive(trigger) {
      if (open && !inspector && selected?.key === live?.key) { close(); return false; }
      return this.openLive(null, null, trigger);
    },
    isLiveOpen() { return open && !inspector && selected?.key === live?.key; },
    registerTurn(node, turn, tabs) {
      stored.set(node, turn);
      const count = fromStored(turn).answers.length;
      if (!count) return;
      const button = document.createElement("button");
      button.type = "button"; button.className = "consensus-tab answer-reader-trigger";
      button.setAttribute("aria-controls", root.id); button.setAttribute("aria-expanded", "false");
      const label = document.createElement("span"); label.className = "consensus-tab-label";
      label.dataset.short = "Answers"; label.textContent = "Compare answers";
      const badge = document.createElement("span"); badge.className = "consensus-tab-count"; badge.textContent = String(count);
      button.append(label, badge);
      button.addEventListener("click", () => openSnapshot(fromStored(turn), null, button));
      tabs.appendChild(button);
    },
    canOpenStored(node, model) { const turn = stored.get(node); return !!turn && !!findProvider(model, fromStored(turn)); },
    openStored(node, model, quote) {
      const turn = stored.get(node);
      return !!turn && openSnapshot(fromStored(turn), model, node.querySelector(".answer-reader-trigger"), quote);
    },
    reset() { direct = false; close({ focus: false }); live = null; savedDirect = null; selected = null; positions.clear(); }
  });
  document.body.classList.add("answer-reader-ready");
  scheduleSync();
})();
