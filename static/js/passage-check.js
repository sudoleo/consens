// =====================================================================
// passage-check.js
// "Paste an AI answer to check it": the Agent checked a passage of the
// user's own message against independent answers (review.passage_check,
// see app/services/agent_comparison.py). This module puts the result at
// the top of the ANSWER as one card: the sentences that do not hold,
// verbatim, each with how many models disagree and what one of them says
// instead; everything else is one line under them ("8 other sentences:
// 6 hold, 2 unconfirmed"), and "Show full text" unfolds the whole passage
// with every sentence marked.
//
// Why in the answer and not on the message: the message is what the user
// sent and stays exactly that (the Agent only decides during the run
// whether it checks at all, so a message that changed shape afterwards
// would jump, and only sometimes). The verdict comes from the models and
// reads as their turn; quoting the sentences keeps it tied to the text.
// Marks reuse the answer's vocabulary (cx-claim states, the claim popover),
// and the full text follows the Highlights setting: by default only red and
// amber are painted, every sentence still opens its card.
//
// The server sends exact character offsets (code points) for every
// sentence, so nothing is searched in the DOM.
// Exports: window.App.passageCheck.{apply, verdict, from}
// =====================================================================

(function () {
  "use strict";

  window.App = window.App || {};

  const STATES = ["disputed", "split", "unconfirmed", "holds"];
  const MARKS = { disputed: "is-major", split: "is-split", holds: "is-unanimous", unconfirmed: "is-thin" };
  // Which verdicts each Highlights setting paints (consensus-insights.js).
  const PAINTED = {
    all: new Set(STATES),
    concerns: new Set(["disputed", "split"]),
    contradictions: new Set(["disputed", "split"]),
    critical: new Set(["disputed"]),
    none: new Set()
  };
  // What the folded card quotes: the sentences other models disagree with.
  // A sentence only one model makes is counted, not quoted: in a text full
  // of figures that would be most of it.
  const QUOTED = new Set(["disputed", "split"]);
  const MAX_QUOTES = 8;
  // What a dissenting model says instead, quoted under the sentence.
  const INSTEAD_CHARS = 180;
  const DONE = new Set(["succeeded", "partial"]);
  const LIVE = new Set(["waiting", "running"]);
  const ANSWER_TO_CHARS = 140;
  const cards = new Set();

  // Same reading as the claim popover: two supporting models and no dissent
  // hold; any dissent splits; more dissent than support disputes.
  function verdict(claim) {
    const agree = claim.agree.length;
    const dissent = claim.dissent.length;
    if (dissent && dissent > agree) return "disputed";
    if (dissent) return "split";
    return claim.coverage === "supported" || agree >= 2 ? "holds" : "unconfirmed";
  }

  function normalize(value) {
    return String(value || "").normalize("NFKC").replace(/\s+/g, " ").trim();
  }

  // A stored check, validated: anything malformed renders as no check at all.
  function from(review) {
    const check = review?.passage_check;
    if (!check || typeof check !== "object" || typeof check.text !== "string" || !check.text.trim()) return null;
    const text = check.text;
    // The server counts code points, JavaScript strings UTF-16 units: an
    // emoji (common in pasted ChatGPT answers) would shift every later mark.
    const units = [0];
    for (const character of text) units.push(units[units.length - 1] + character.length);
    const points = units.length - 1;
    let claims = (Array.isArray(check.claims) ? check.claims : [])
      .filter(claim => claim && Number.isInteger(claim.start) && Number.isInteger(claim.end)
        && claim.start >= 0 && claim.end <= points && claim.start < claim.end)
      .map(claim => ({
        ...claim,
        start: units[claim.start],
        end: units[claim.end],
        agree: Array.isArray(claim.agree) ? claim.agree.map(String) : [],
        dissent: (Array.isArray(claim.dissent) ? claim.dissent : [])
          .filter(item => item && item.model).map(item => ({ model: String(item.model), quote: String(item.quote || "") })),
        anchor: String(claim.anchor || text.slice(units[claim.start], units[claim.end]))
      }))
      .sort((a, b) => a.start - b.start);
    // Overlapping spans would print text twice: keep the first of each.
    let kept = 0;
    claims = claims.filter(claim => claim.start >= kept && (kept = claim.end, true));
    return {
      status: String(check.status || ""),
      text,
      answerTo: String(check.answer_to || ""),
      comparisonId: String(check.comparison_id || ""),
      models: Array.isArray(check.models_compared) ? check.models_compared.map(String) : [],
      issues: (Array.isArray(check.issues) ? check.issues : [])
        .filter(issue => issue && issue.code).map(issue => ({ code: String(issue.code), count: Number(issue.count) || 0 })),
      claims
    };
  }

  // What the card shows, independent of key order: a saved turn comes back
  // from Firestore with its maps in another order than the live frames had.
  function signatureOf(check, live) {
    return JSON.stringify([DONE.has(check.status) ? "done" : live ? "live" : check.status,
      check.status, check.text, check.answerTo, check.models.slice().sort(),
      check.issues.map(issue => [issue.code, issue.count]).sort(),
      check.claims.map(claim => [claim.start, claim.end, verdict(claim), claim.agree.slice().sort(),
        claim.dissent.map(item => [item.model, item.quote]).sort()])]);
  }

  // Pasted Markdown (ChatGPT's copy button) reads as text: bold and italic
  // markers, heading hashes, quote marks, code fences and table rules go,
  // links keep their text, list bullets become dots and table cells are
  // separated by a middle dot. Underscores stay (__init__). A piece is part
  // of the passage, so whether it starts or ends a line comes from the whole
  // text: between two table cells " | " is a separator, not a line's end.
  function displayText(piece, atLineStart, atLineEnd = true) {
    const lineStart = atLineStart ? "(^|\\n)" : "(\\n)";
    const lineEnd = atLineEnd ? "(?=\\n|$)" : "(?=\\n)";
    const rule = "[ \\t]*\\|?[ \\t]*:?-{3,}:?[ \\t]*(?:\\|[ \\t]*:?-{3,}:?[ \\t]*)*\\|?[ \\t]*";
    return piece
      .replace(new RegExp(lineStart + "[ \\t]*(?:```|~~~)[^\\n]*" + lineEnd, "g"), "$1")
      .replace(/\*\*/g, "")
      // The rule row goes with its line break: no gap between head and body.
      .replace(new RegExp(lineStart + rule + (atLineEnd ? "(?:\\n|$)" : "\\n"), "g"), "$1")
      .replace(new RegExp(lineStart + "[ \\t]*#{1,6}[ \\t]+", "g"), "$1")
      .replace(new RegExp(lineStart + "[ \\t]*>[ \\t]?", "g"), "$1")
      .replace(new RegExp(lineStart + "[ \\t]*[-*+][ \\t]+", "g"), "$1• ")
      .replace(new RegExp(lineStart + "[ \\t]*\\|[ \\t]*", "g"), "$1")
      .replace(new RegExp("[ \\t]*\\|[ \\t]*" + lineEnd, "g"), "")
      .replace(/[ \t]*\|[ \t]*/g, " · ")
      .replace(/!?\[([^\]\n]+)\]\([^)\s]+\)/g, "$1")
      .replace(/`([^`\n]+)`/g, "$1")
      .replace(/(^|[^\w*\\])\*(?=\S)([^*\n]*?\S)\*(?![\w*])/g, "$1$2")
      .replace(/\n{3,}/g, "\n\n");
  }

  // "View answer" in the claim card opens the comparison answer. Until the
  // answer's own evidence row exists (during the run), a minimal reader
  // context is built from the review's comparison.
  function readerContext(card) {
    const review = card._passageReview;
    const id = card._passageCheck?.comparisonId;
    const built = window.App.agentReview?.contextFor?.(review, id);
    if (built) return built;
    const comparison = (review?.comparisons || []).find(item => item?.id === id);
    if (!comparison) return null;
    return {
      key: `passage-check:${id}`, question: comparison.question || "", scopeLabel: "Comparison focus",
      answers: (comparison.answers || []).map(answer => ({
        provider: answer.provider_label || answer.provider, model: answer.model?.model,
        label: answer.model?.label || answer.provider_label || answer.provider, text: answer.text || "",
        sources: [], sourceReferences: "agent", status: "complete"
      })),
      renderPanel: () => document.createElement("div")
    };
  }

  function navigation(card) {
    const find = (ctx, name) => (ctx?.answers || []).find(answer =>
      [answer.provider, answer.label].some(value => value?.toLowerCase() === String(name || "").toLowerCase()));
    return {
      canOpen: name => Boolean(find(readerContext(card), name)),
      open: (name, quote) => {
        const ctx = readerContext(card);
        const answer = find(ctx, name);
        if (ctx && answer) window.App.answerReader?.openContext(ctx, { section: "answers", model: answer.provider, quote });
      }
    };
  }

  function openDetails(card, anchor, claim) {
    if (!claim) return;
    window.App.claimPopover?.open(claim, anchor, card._passageCheck.models, navigation(card));
  }

  function claimLabel(claim) {
    const state = verdict(claim);
    const total = claim.agree.length + claim.dissent.length;
    if (state === "unconfirmed") return claim.agree.length ? "Only one model says this" : "No other model says this";
    if (state === "holds") return `${claim.agree.length} of ${total} models agree`;
    return `${claim.dissent.length} of ${total} ${claim.dissent.length === 1 ? "models disagrees" : "models disagree"}`;
  }

  function highlightMode() {
    return PAINTED[document.body?.dataset.consensusHighlightMode] ? document.body.dataset.consensusHighlightMode : "concerns";
  }

  // The quoted sentences are always painted: they are quoted because of
  // their verdict. The full text paints what the Highlights setting paints.
  function paint(card) {
    const painted = PAINTED[highlightMode()];
    card.querySelectorAll(".passage-check-text .pc-claim").forEach(span => {
      span.classList.toggle("is-quiet", !painted.has(span.dataset.verdict));
    });
  }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
  }

  function mark(claim, index, text, { quoted = false } = {}) {
    const span = node("span", `cx-claim pc-claim is-interactive ${MARKS[verdict(claim)]}`, text);
    span.dataset.claim = String(index);
    span.dataset.verdict = verdict(claim);
    span.tabIndex = 0;
    span.setAttribute("role", "button");
    span.setAttribute("aria-haspopup", "dialog");
    // A button's name replaces its text: the sentence has to be in it.
    // Quoted, the verdict line right below says the rest.
    span.setAttribute("aria-label", quoted ? `“${text}” – Show details` : `“${text}” – ${claimLabel(claim)}. Show details`);
    return span;
  }

  function fullText(check) {
    const body = node("div", "passage-check-text");
    const atLine = index => index === 0 || check.text[index - 1] === "\n";
    const atEnd = index => index >= check.text.length || check.text[index] === "\n";
    const piece = (from, to) => displayText(check.text.slice(from, to), atLine(from), atEnd(to));
    let cursor = 0;
    check.claims.forEach((claim, index) => {
      if (claim.start > cursor) body.append(piece(cursor, claim.start));
      body.append(mark(claim, index, piece(claim.start, claim.end)));
      cursor = claim.end;
    });
    if (cursor < check.text.length) body.append(piece(cursor, check.text.length));
    return body;
  }

  function sentences(count) {
    return `${count} sentence${count === 1 ? "" : "s"}`;
  }

  // One line for every sentence the card does not quote: "All 9
  // sentences hold", "8 other sentences: 6 hold, 2 unconfirmed".
  function restLabel(claims, quoted) {
    const tally = counts({ claims });
    const count = claims.length;
    const shown = STATES.filter(state => tally[state]);
    if (shown.length === 1 && shown[0] === "holds") {
      if (!quoted) return count === 1 ? "The sentence holds" : `All ${count} sentences hold`;
      return count === 1 ? "The other sentence holds" : `The other ${count} sentences hold`;
    }
    const parts = shown.map(state => CHIP_LABELS[state](tally[state]));
    return `${quoted ? `${count} other ${count === 1 ? "sentence" : "sentences"}` : sentences(count)}: ${parts.join(", ")}`;
  }

  // What one dissenting model says instead, short: the card is a summary,
  // the claim card has every model's own words.
  function instead(claim) {
    const item = claim.dissent.find(dissent => normalize(dissent.quote));
    if (!item) return null;
    let quote = normalize(displayText(item.quote, true)).replace(/^[\s•]+/, "");
    if (quote.length > INSTEAD_CHARS) quote = quote.slice(0, INSTEAD_CHARS - 1).replace(/\s+\S*$/, "") + "…";
    return { model: item.model, quote };
  }

  // Indexes of the sentences the folded card quotes: the ones other models
  // disagree with, at most MAX_QUOTES.
  function quotedIndexes(check) {
    return new Set(check.claims.map((claim, index) => QUOTED.has(verdict(claim)) ? index : -1)
      .filter(index => index >= 0).slice(0, MAX_QUOTES));
  }

  // The folded card: the quoted sentences in reading order, each with its
  // verdict and what the models say instead.
  function quotes(check) {
    const list = node("div", "passage-check-quotes");
    for (const index of quotedIndexes(check)) {
      const claim = check.claims[index];
      const row = node("div", "passage-check-quote");
      // A quoted list item or heading stands alone: no bullet in front.
      const text = displayText(check.text.slice(claim.start, claim.end), true).replace(/^[\s•]+/, "").replace(/\s+/g, " ").trim();
      const sentence = node("p", "passage-check-sentence");
      sentence.append(mark(claim, index, text, { quoted: true }));
      const line = node("p", `passage-check-verdict is-${verdict(claim)}`);
      line.dataset.claim = String(index);
      line.append(node("span", "passage-check-who", claimLabel(claim)));
      const other = instead(claim);
      if (other) line.append(" – ", node("span", "passage-check-instead", `${other.model}: “${other.quote}”`));
      row.append(sentence, line);
      list.append(row);
    }
    return list;
  }

  function counts(check) {
    const result = { disputed: 0, split: 0, unconfirmed: 0, holds: 0 };
    check.claims.forEach(claim => { result[verdict(claim)] += 1; });
    return result;
  }

  const CHIP_LABELS = {
    disputed: count => `${count} disputed`,
    split: count => `${count} split`,
    unconfirmed: count => `${count} unconfirmed`,
    holds: count => `${count} ${count === 1 ? "holds" : "hold"}`
  };

  function issueNote(check) {
    const notes = [];
    for (const issue of check.issues) {
      if (issue.code === "models_unavailable" && issue.count) {
        notes.push(`${issue.count} model${issue.count === 1 ? "" : "s"} did not answer`);
      }
      if ((issue.code === "sentences_unchecked" || issue.code === "unindexed_sentences") && issue.count) {
        notes.push(`${sentences(issue.count)} could not be checked`);
      }
    }
    return notes.length ? notes.join(" · ") + "." : "";
  }

  function failureText(check, live) {
    if (LIVE.has(check.status) && !live) return "The check of your text did not finish.";
    if (check.status === "cancelled") return "The check of your text was stopped.";
    if (check.issues.some(issue => issue.code === "insufficient_answers")) {
      return "Your text could not be checked: too few models answered.";
    }
    if (check.issues.some(issue => issue.code === "no_time")) {
      return "Your text could not be checked: the answer needed the remaining time.";
    }
    return "Your text could not be checked this time.";
  }

  function quotedQuestion(value) {
    const text = normalize(value);
    const short = text.length > ANSWER_TO_CHARS ? text.slice(0, ANSWER_TO_CHARS - 1).trimEnd() + "…" : text;
    // "...need?" ends the sentence already; no second full stop after it.
    return `“${short}”` + (/[.?!…]$/.test(short) ? "" : ".");
  }

  // One uppercase label names the block; the tally under it is its
  // headline, with the verdict colour on the numbers only.
  function head(check, live) {
    const row = node("div", "passage-check-head");
    row.append(node("p", "passage-check-eyebrow", "Your text"));
    if (!DONE.has(check.status)) {
      row.append(node("p", "passage-check-status", LIVE.has(check.status) && live
        ? (check.status === "running" ? "Checking each sentence…" : "Checking against independent answers…")
        : failureText(check, live)));
      return row;
    }
    if (!check.claims.length) {
      row.append(node("p", "passage-check-status", "No sentence of your text could be checked against the answers."));
      return row;
    }
    // Each count carries the separator after it, so a wrapped line never
    // starts with a dot.
    const tally = counts(check);
    const shown = STATES.filter(state => tally[state]);
    const list = node("p", "passage-check-counts");
    shown.forEach((state, index) => {
      const unit = node("span", "passage-check-unit");
      const chip = node("button", `passage-check-count is-${state}`);
      chip.type = "button";
      chip.dataset.verdict = state;
      const [number, ...label] = CHIP_LABELS[state](tally[state]).split(" ");
      chip.append(node("span", "passage-check-num", number), ` ${label.join(" ")}`);
      chip.setAttribute("aria-label", `${chip.textContent}: show the first one`);
      unit.append(chip);
      if (index < shown.length - 1) unit.append(" ·");
      list.append(unit);
      if (index < shown.length - 1) list.append(" ");
    });
    row.append(list);
    return row;
  }

  // Under the rail: one line for the sentences not quoted, with the way to
  // the full text, then where the check comes from.
  function foot(check, live) {
    const running = LIVE.has(check.status) && live;
    const row = node("div", "passage-check-foot");
    if (DONE.has(check.status) && check.claims.length) {
      const rest = node("p", "passage-check-rest");
      const toggle = node("button", "passage-check-toggle");
      toggle.type = "button";
      rest.append(node("span", "passage-check-rest-label"), toggle);
      row.append(rest);
    }
    if (check.answerTo && (DONE.has(check.status) || running)) {
      const note = issueNote(check);
      row.append(node("p", "passage-check-note", (running
        ? `Checking it as an answer to ${quotedQuestion(check.answerTo)} The models answer without seeing your text.`
        : `Checked against ${check.models.length} models that answered ${quotedQuestion(check.answerTo).replace(/\.$/, "")} `
          + "without seeing your text.") + (note ? ` ${note}` : "")));
    }
    return row.childNodes.length ? row : null;
  }

  // Folded (the quotes) or unfolded (the full text): only the body and the
  // toggle change, the counts and the note stay.
  function syncBody(card) {
    const check = card._passageCheck;
    const full = card.classList.contains("is-full");
    const body = card.querySelector(":scope > .passage-check-body");
    const quoted = full ? new Set() : quotedIndexes(check);
    if (body) {
      // Folded without a quote, the line under the rail says it all.
      body.hidden = !full && !quoted.size;
      body.replaceChildren(full ? fullText(check) : quotes(check));
      paint(card);
    }
    const label = card.querySelector(".passage-check-rest-label");
    if (label) {
      const rest = full ? [] : check.claims.filter((claim, index) => !quoted.has(index));
      label.textContent = rest.length ? `${restLabel(rest, quoted.size > 0)}. ` : "";
    }
    const toggle = card.querySelector(".passage-check-toggle");
    if (toggle) {
      toggle.textContent = full ? "Show less" : "Show full text";
      toggle.setAttribute("aria-expanded", String(full));
    }
  }

  function render(card, check, live) {
    const done = DONE.has(check.status);
    card.dataset.state = done ? "done" : LIVE.has(check.status) && live ? "running" : "failed";
    const parts = [head(check, live)];
    if (done && check.claims.length) parts.push(node("div", "passage-check-body"));
    const footer = foot(check, live);
    if (footer) parts.push(footer);
    card.replaceChildren(...parts);
    syncBody(card);
  }

  function unfold(card, full) {
    if (card.classList.contains("is-full") === full) return;
    card.classList.toggle("is-full", full);
    syncBody(card);
  }

  // A count opens the first sentence with that verdict: a quoted one where
  // it stands, any other in the unfolded text.
  function focusVerdict(card, chip) {
    const state = chip.dataset.verdict;
    let span = card.querySelector(`.pc-claim[data-verdict="${state}"]`);
    if (!span) {
      unfold(card, true);
      span = card.querySelector(`.pc-claim[data-verdict="${state}"]`);
    }
    if (!span) return;
    // Instantly: the claim card places itself where the sentence is now.
    span.scrollIntoView({ block: "center" });
    span.focus({ preventScroll: true });
    openDetails(card, span, card._passageCheck?.claims[Number(span.dataset.claim)]);
  }

  function bind(card) {
    card.addEventListener("click", event => {
      const chip = event.target.closest(".passage-check-count");
      if (chip) {
        focusVerdict(card, chip);
        return;
      }
      const toggle = event.target.closest(".passage-check-toggle");
      if (toggle) {
        unfold(card, !card.classList.contains("is-full"));
        toggle.focus?.({ preventScroll: true });
        return;
      }
      // Selecting quoted text (to copy it) is not a request for the card.
      if (window.getSelection?.()?.isCollapsed === false) return;
      // The verdict line under a quoted sentence opens the same card; the
      // sentence stays the keyboard target.
      const line = event.target.closest(".passage-check-verdict");
      const span = event.target.closest(".pc-claim")
        || line?.parentElement.querySelector(`.pc-claim[data-claim="${line.dataset.claim}"]`);
      if (span) openDetails(card, span, card._passageCheck?.claims[Number(span.dataset.claim)]);
    });
    card.addEventListener("keydown", event => {
      const span = event.target.closest?.(".pc-claim");
      if (!span || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      openDetails(card, span, card._passageCheck?.claims[Number(span.dataset.claim)]);
    });
  }

  function remove(body) {
    const card = body._passageCard;
    if (!card) return;
    card.remove();
    cards.delete(card);
    body._passageCard = null;
  }

  // Draws the check of `review` as a card right above the answer `body`, or
  // removes a stale one. Called on every projection; unchanged input does
  // nothing (no rebuilt DOM, no lost focus, no detached anchor of an open
  // claim card).
  function apply(body, review, options = {}) {
    if (!body) return;
    const check = from(review);
    if (!check || !body.parentNode) {
      remove(body);
      return;
    }
    let card = body._passageCard;
    if (!card) {
      card = node("section", "passage-check");
      card.setAttribute("aria-label", "Check of your text");
      body._passageCard = card;
      bind(card);
    }
    // Right above the answer, also after other rows were put there.
    if (card.nextElementSibling !== body) body.before(card);
    card._passageReview = review || null;
    const live = Boolean(options.live);
    const signature = signatureOf(check, live);
    // History cards are rebuilt on every chat switch; the old ones hold a
    // whole review each.
    for (const other of cards) if (!other.isConnected) cards.delete(other);
    cards.add(card);
    if (card._passageSignature === signature) return;
    // The same card shows another turn's text (a chat switch): folded again.
    const previous = card._passageCheck;
    if (previous && (previous.text !== check.text || previous.comparisonId !== check.comparisonId)) {
      card.classList.remove("is-full");
    }
    card._passageSignature = signature;
    card._passageCheck = check;
    render(card, check, live);
  }

  // The Highlights setting changes which verdicts the full text paints, live.
  if (typeof MutationObserver === "function" && document.body) {
    new MutationObserver(() => {
      for (const card of [...cards]) {
        if (card.isConnected) paint(card);
        else cards.delete(card);
      }
    }).observe(document.body, { attributes: true, attributeFilter: ["data-consensus-highlight-mode"] });
  }

  window.App.passageCheck = { apply, verdict, from };
})();
