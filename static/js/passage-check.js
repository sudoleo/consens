// =====================================================================
// passage-check.js
// "Paste an AI answer to check it": the Agent checked a passage of the
// user's own message against independent answers (review.passage_check,
// see app/services/agent_comparison.py). This module marks that passage
// sentence by sentence ON THE USER'S MESSAGE and puts one short line
// under it: how many sentences are disputed, split, unconfirmed or hold,
// and which question the text was checked against.
//
// Why on the message and not in the answer: the user asked about THEIR
// text. The answer below explains the verdict; the marks show where.
// Marks reuse the answer's vocabulary (cx-claim states, the claim popover),
// so a checked sentence looks and opens like a checked answer sentence, and
// they follow the same Highlights setting: by default only red and amber are
// painted, every sentence still opens its card.
//
// The server sends exact character offsets (code points) for every sentence,
// so nothing is searched in the DOM. As soon as a check is declared, the
// passage keeps its line breaks (a pasted list stays a list), so the marks
// arriving later change colour, never the bubble's size.
// Exports: window.App.passageCheck.{apply, restore, verdict, from}
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
  const DONE = new Set(["succeeded", "partial"]);
  const LIVE = new Set(["waiting", "running"]);
  const ANSWER_TO_CHARS = 140;
  const bubbles = new Set();

  // Same reading as the claim popover: two supporting models and no dissent
  // hold; any dissent splits; more dissent than support disputes.
  function verdict(claim) {
    const agree = claim.agree.length;
    const dissent = claim.dissent.length;
    if (dissent && dissent > agree) return "disputed";
    if (dissent) return "split";
    return claim.coverage === "supported" || agree >= 2 ? "holds" : "unconfirmed";
  }

  function collapse(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function normalize(value) {
    return collapse(String(value || "").normalize("NFKC"));
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
    const claims = (Array.isArray(check.claims) ? check.claims : [])
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
      .sort((a, b) => a.start - b.start)
      .filter((claim, index, list) => index === 0 || claim.start >= list[index - 1].end);
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

  // What the bubble shows, independent of key order: a saved turn comes back
  // from Firestore with its maps in another order than the live frames had.
  function signatureOf(check, question, live) {
    return JSON.stringify([normalize(question), DONE.has(check.status) ? "done" : live ? "live" : check.status,
      check.status, check.text, check.answerTo, check.models.slice().sort(),
      check.issues.map(issue => [issue.code, issue.count]).sort(),
      check.claims.map(claim => [claim.start, claim.end, verdict(claim), claim.agree.slice().sort(),
        claim.dissent.map(item => [item.model, item.quote]).sort()])]);
  }

  // Pasted Markdown (ChatGPT's copy button) reads as text in a message: bold
  // markers, heading hashes and table rules go, list bullets become dots and
  // table cells are separated by a middle dot. Underscores stay (__init__).
  function displayText(piece, atLineStart) {
    const lineStart = atLineStart ? "(^|\\n)" : "(\\n)";
    return piece
      .replace(/\*\*/g, "")
      .replace(new RegExp(lineStart + "[ \\t]*\\|?[ \\t]*:?-{3,}:?[ \\t]*(\\|[ \\t]*:?-{3,}:?[ \\t]*)*\\|?[ \\t]*(?=\\n|$)", "g"), "$1")
      .replace(new RegExp(lineStart + "[ \\t]*#{1,6}[ \\t]+", "g"), "$1")
      .replace(new RegExp(lineStart + "[ \\t]*[-*+][ \\t]+", "g"), "$1• ")
      .replace(new RegExp(lineStart + "[ \\t]*\\|[ \\t]*", "g"), "$1")
      .replace(/[ \t]*\|[ \t]*(?=\n|$)/g, "")
      .replace(/[ \t]*\|[ \t]*/g, " · ")
      .replace(/\n{3,}/g, "\n\n");
  }

  // "View answer" in the card opens the comparison answer. Until the
  // answer's own evidence row exists (during the run), a minimal reader
  // context is built from the review's comparison.
  function readerContext(wrap) {
    const review = wrap._passageReview;
    const id = wrap._passageCheck?.comparisonId;
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

  function navigation(wrap) {
    const find = (ctx, name) => (ctx?.answers || []).find(answer =>
      [answer.provider, answer.label].some(value => value?.toLowerCase() === String(name || "").toLowerCase()));
    return {
      canOpen: name => Boolean(find(readerContext(wrap), name)),
      open: (name, quote) => {
        const ctx = readerContext(wrap);
        const answer = find(ctx, name);
        if (ctx && answer) window.App.answerReader?.openContext(ctx, { section: "answers", model: answer.provider, quote });
      }
    };
  }

  function openDetails(wrap, anchor, claim) {
    if (!claim) return;
    window.App.claimPopover?.open(claim, anchor, wrap._passageCheck.models, navigation(wrap));
  }

  function claimLabel(claim) {
    const state = verdict(claim);
    const total = claim.agree.length + claim.dissent.length;
    if (state === "unconfirmed") return claim.agree.length ? "Only one model says this" : "No other model says this";
    if (state === "holds") return `${claim.agree.length} of ${total} models agree`;
    return `${claim.dissent.length} of ${total} models disagree`;
  }

  function highlightMode() {
    return PAINTED[document.body?.dataset.consensusHighlightMode] ? document.body.dataset.consensusHighlightMode : "concerns";
  }

  function paint(wrap) {
    const painted = PAINTED[highlightMode()];
    wrap.querySelectorAll(".pc-claim").forEach(span => {
      span.classList.toggle("is-quiet", !painted.has(span.dataset.verdict));
    });
  }

  // Where the passage sits in the displayed question. The user's own words
  // keep their spelling (collapsed whitespace, no NFKC) whenever they can.
  function split(question, passageText) {
    for (const form of [collapse, normalize]) {
      const full = form(question);
      const passage = form(passageText);
      const index = passage ? full.indexOf(passage) : -1;
      if (index >= 0) return [full.slice(0, index).trim(), full.slice(index + passage.length).trim()];
    }
    return null;
  }

  function renderText(text, question, check, marks) {
    const parts = split(question, check.text);
    if (!parts) return false;
    const [before, after] = parts;
    const nodes = [];
    if (before) nodes.push(document.createTextNode(before + "\n\n"));
    const body = document.createElement("span");
    body.className = "passage-check-text";
    const atLine = index => index === 0 || check.text[index - 1] === "\n";
    let cursor = 0;
    (marks ? check.claims : []).forEach((claim, claimIndex) => {
      if (claim.start > cursor) body.append(displayText(check.text.slice(cursor, claim.start), atLine(cursor)));
      const span = document.createElement("span");
      span.className = `cx-claim pc-claim is-interactive ${MARKS[verdict(claim)]}`;
      span.dataset.claim = String(claimIndex);
      span.dataset.verdict = verdict(claim);
      span.tabIndex = 0;
      span.setAttribute("role", "button");
      span.setAttribute("aria-haspopup", "dialog");
      span.textContent = displayText(check.text.slice(claim.start, claim.end), atLine(claim.start));
      // A button's name replaces its text: the sentence has to be in it.
      span.setAttribute("aria-label", `“${span.textContent}” – ${claimLabel(claim)}. Show details`);
      body.append(span);
      cursor = claim.end;
    });
    if (cursor < check.text.length) body.append(displayText(check.text.slice(cursor), atLine(cursor)));
    nodes.push(body);
    if (after) nodes.push(document.createTextNode("\n\n" + after));
    text.replaceChildren(...nodes);
    return true;
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
        notes.push(`${issue.count} sentence${issue.count === 1 ? "" : "s"} could not be checked`);
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

  function line(className, text) {
    const node = document.createElement("p");
    node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function renderSummary(wrap, check, live) {
    let summary = wrap.querySelector(":scope > .passage-check");
    if (!summary) {
      summary = document.createElement("div");
      summary.className = "passage-check";
      summary.setAttribute("role", "status");
      wrap.append(summary);
    }
    const running = LIVE.has(check.status) && live;
    summary.dataset.state = DONE.has(check.status) ? "done" : running ? "running" : "failed";
    const lines = [];
    if (running) {
      lines.push(line("passage-check-head", check.status === "running"
        ? "Checking each sentence of your text…"
        : "Checking your text against independent answers…"));
    } else if (!DONE.has(check.status)) {
      lines.push(line("passage-check-head", failureText(check, live)));
    } else {
      // The counts lead: they are what the user came for. Each count carries
      // the separator after it, so a wrapped line never starts with a dot.
      const head = line("passage-check-head");
      if (!check.claims.length) head.append("No checkable statements found in your text.");
      const tally = counts(check);
      const shown = STATES.filter(state => tally[state]);
      shown.forEach((state, index) => {
        const unit = document.createElement("span");
        unit.className = "passage-check-unit";
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = `passage-check-count is-${state}`;
        chip.dataset.verdict = state;
        chip.textContent = CHIP_LABELS[state](tally[state]);
        chip.setAttribute("aria-label", `${chip.textContent}: show the first one`);
        unit.append(chip);
        if (index < shown.length - 1) unit.append(" ·");
        head.append(unit);
        if (index < shown.length - 1) head.append(" ");
      });
      lines.push(head);
    }
    if (check.answerTo && (DONE.has(check.status) || running)) {
      const note = issueNote(check);
      lines.push(line("passage-check-note", (running
        ? `Checking it as an answer to ${quotedQuestion(check.answerTo)} The models answer without seeing your text.`
        : `Checked against ${check.models.length} models as an answer to ${quotedQuestion(check.answerTo)} `
          + "The models answered without seeing your text.") + (note ? ` ${note}` : "")));
    }
    summary.replaceChildren(...lines);
  }

  function open(wrap) {
    const text = textElement(wrap);
    if (text) text.scrollTop = 0;
    if (wrap.classList.contains("is-open")) return;
    wrap.classList.add("is-open");
    const more = wrap.querySelector(":scope > .thread-ask-more");
    if (more) {
      more.textContent = "Collapse question";
      more.setAttribute("aria-expanded", "true");
    }
  }

  // A count jumps to the first sentence with that verdict and opens its card;
  // without marks on the bubble, the card opens at the count itself.
  function focusVerdict(wrap, chip) {
    const state = chip.dataset.verdict;
    const span = wrap.querySelector(`.pc-claim[data-verdict="${state}"]`);
    const check = wrap._passageCheck;
    if (!span) {
      openDetails(wrap, chip, check?.claims.find(claim => verdict(claim) === state));
      return;
    }
    open(wrap);
    span.scrollIntoView({ block: "center", behavior: "smooth" });
    span.focus({ preventScroll: true });
    openDetails(wrap, span, check?.claims[Number(span.dataset.claim)]);
  }

  function bind(wrap) {
    if (wrap._passageCheckBound) return;
    wrap._passageCheckBound = true;
    wrap.addEventListener("click", event => {
      const chip = event.target.closest(".passage-check-count");
      if (chip && wrap.contains(chip)) {
        focusVerdict(wrap, chip);
        return;
      }
      const span = event.target.closest(".pc-claim");
      // Selecting pasted text (to copy it, or for the memory toolbar) is not
      // a request for the card.
      if (window.getSelection?.()?.isCollapsed === false) return;
      if (span && wrap.contains(span)) openDetails(wrap, span, wrap._passageCheck?.claims[Number(span.dataset.claim)]);
    });
    wrap.addEventListener("keydown", event => {
      const span = event.target.closest?.(".pc-claim");
      if (!span || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      openDetails(wrap, span, wrap._passageCheck?.claims[Number(span.dataset.claim)]);
    });
    // A sentence reached with Tab below the fold unfolds the message; the
    // clamped box must never scroll itself to show it.
    wrap.addEventListener("focusin", event => {
      if (event.target.closest?.(".pc-claim")) open(wrap);
    });
  }

  function textElement(wrap) {
    return wrap?.querySelector(":scope > .thread-ask-text, :scope > .thread-history-question-text") || null;
  }

  function clear(wrap, text) {
    wrap.querySelector(":scope > .passage-check")?.remove();
    bubbles.delete(wrap);
    if (!wrap.classList.contains("has-passage-check")) return;
    wrap.classList.remove("has-passage-check");
    if (text) text.textContent = text.dataset.question ?? normalize(wrap._passageQuestion);
    window.App.syncThreadAskClamp?.(wrap);
  }

  // Draws the check of `review` onto a question bubble, or removes a stale
  // one. Called on every projection; unchanged input does nothing.
  function apply(wrap, text, question, review, options = {}) {
    if (!wrap) return;
    text = text || textElement(wrap);
    const check = from(review);
    const live = Boolean(options.live);
    const signature = check ? signatureOf(check, question, live) : "";
    wrap._passageReview = review || null;
    // Unchanged input changes nothing: the summary is a live region, and
    // rebuilding it would make it speak again, drop focus and detach the
    // anchor of an open card.
    if (wrap._passageSignature === signature) return;
    wrap._passageSignature = signature;
    wrap._passageCheck = check;
    wrap._passageQuestion = question;
    wrap._passageLive = live;
    if (!check || !text) {
      clear(wrap, text);
      return;
    }
    const shown = renderText(text, question, check, DONE.has(check.status));
    if (shown) wrap.classList.add("has-passage-check");
    else if (wrap.classList.contains("has-passage-check")) clear(wrap, text);
    renderSummary(wrap, check, live);
    paint(wrap);
    bubbles.add(wrap);
    bind(wrap);
    window.App.syncThreadAskClamp?.(wrap);
  }

  // app-core.js re-renders the bubble's text when the question changes;
  // the same question keeps its check.
  function restore(wrap, text, question) {
    if (!wrap?._passageCheck) return;
    if (normalize(wrap._passageQuestion) !== normalize(question)) {
      wrap._passageCheck = null;
      wrap._passageSignature = "";
      wrap._passageQuestion = question;
      clear(wrap, text);
      return;
    }
    const review = wrap._passageReview;
    wrap._passageSignature = "";
    apply(wrap, text, question, review, { live: wrap._passageLive });
  }

  // The Highlights setting changes which verdicts are painted, live.
  if (typeof MutationObserver === "function" && document.body) {
    new MutationObserver(() => {
      for (const wrap of [...bubbles]) {
        if (wrap.isConnected) paint(wrap);
        else bubbles.delete(wrap);
      }
    }).observe(document.body, { attributes: true, attributeFilter: ["data-consensus-highlight-mode"] });
  }

  window.App.passageCheck = { apply, restore, verdict, from };
})();
