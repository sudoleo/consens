// =====================================================================
// passage-check.js
// "Paste an AI answer to check it": the Agent checked a passage of the
// user's own message against independent answers (review.passage_check,
// see app/services/agent_comparison.py). This module marks that passage
// sentence by sentence ON THE USER'S MESSAGE and puts one short line
// under it: how many sentences hold, are split or disputed, and which
// question the text was checked against.
//
// Why on the message and not in the answer: the user asked about THEIR
// text. The answer below explains the verdict; the marks show where.
// Marks reuse the answer's vocabulary (cx-claim states, the claim popover),
// so a checked sentence looks and opens like a checked answer sentence.
//
// The server sends exact character offsets for every sentence, so nothing
// is searched in the DOM. The bubble normally collapses whitespace; a checked
// passage keeps its line breaks (a pasted list stays a list).
// Exports: window.App.passageCheck.{apply, restore, verdict, from}
// =====================================================================

(function () {
  "use strict";

  window.App = window.App || {};

  const STATES = ["disputed", "split", "unconfirmed", "holds"];
  const MARKS = { disputed: "is-major", split: "is-split", holds: "is-unanimous", unconfirmed: "is-thin" };
  const DONE = new Set(["succeeded", "partial"]);
  const LIVE = new Set(["waiting", "running"]);
  const ANSWER_TO_CHARS = 140;

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
      issues: Array.isArray(check.issues) ? check.issues : [],
      claims
    };
  }

  // Pasted Markdown (ChatGPT's copy button) reads as text in a message:
  // emphasis markers and heading hashes go, list bullets become dots.
  function displayText(piece, atLineStart) {
    let text = piece.replace(/\*\*|__/g, "");
    const lineStart = atLineStart ? /(^|\n)[ \t]*/ : /(\n)[ \t]*/;
    text = text.replace(new RegExp(lineStart.source + "#{1,6}[ \\t]+", "g"), "$1");
    text = text.replace(new RegExp(lineStart.source + "[-*+][ \\t]+", "g"), "$1• ");
    return text.replace(/\n{3,}/g, "\n\n");
  }

  // "View answer" in the popover opens the comparison answer, once the
  // answer's evidence row has built its reader context.
  function navigation(wrap) {
    const context = () => window.App.agentReview?.contextFor?.(wrap._passageReview, wrap._passageCheck?.comparisonId);
    const find = (ctx, name) => (ctx?.answers || []).find(answer =>
      [answer.provider, answer.label].some(value => value?.toLowerCase() === String(name || "").toLowerCase()));
    return {
      canOpen: name => Boolean(find(context(), name)),
      open: (name, quote) => {
        const ctx = context();
        const answer = find(ctx, name);
        if (ctx && answer) window.App.answerReader?.openContext(ctx, { section: "answers", model: answer.provider, quote });
      }
    };
  }

  function openDetails(wrap, span) {
    const claim = wrap._passageCheck?.claims[Number(span.dataset.claim)];
    if (!claim) return;
    window.App.claimPopover?.open(claim, span, wrap._passageCheck.models, navigation(wrap));
  }

  function claimLabel(claim) {
    const state = verdict(claim);
    const total = claim.agree.length + claim.dissent.length;
    if (state === "unconfirmed") return claim.agree.length ? "Only one model says this" : "No other model says this";
    if (state === "holds") return `${claim.agree.length} of ${total} models agree`;
    return `${claim.dissent.length} of ${total} models disagree`;
  }

  function renderText(text, question, check) {
    const full = normalize(question);
    const passage = normalize(check.text);
    const index = passage ? full.indexOf(passage) : -1;
    if (index < 0) return false;
    const before = full.slice(0, index).trim();
    const after = full.slice(index + passage.length).trim();
    const nodes = [];
    if (before) nodes.push(document.createTextNode(before + "\n"));
    const body = document.createElement("span");
    body.className = "passage-check-text";
    let cursor = 0;
    check.claims.forEach((claim, claimIndex) => {
      if (claim.start > cursor) {
        body.append(displayText(check.text.slice(cursor, claim.start), cursor === 0 || check.text[cursor - 1] === "\n"));
      }
      const span = document.createElement("span");
      span.className = `cx-claim pc-claim is-interactive ${MARKS[verdict(claim)]}`;
      span.dataset.claim = String(claimIndex);
      span.dataset.verdict = verdict(claim);
      span.tabIndex = 0;
      span.setAttribute("role", "button");
      span.textContent = displayText(check.text.slice(claim.start, claim.end), false);
      // A button's name replaces its text: the sentence has to be in it.
      span.setAttribute("aria-label", `“${span.textContent}” – ${claimLabel(claim)}. Show details`);
      body.append(span);
      cursor = claim.end;
    });
    if (cursor < check.text.length) {
      body.append(displayText(check.text.slice(cursor), cursor === 0 || check.text[cursor - 1] === "\n"));
    }
    nodes.push(body);
    if (after) nodes.push(document.createTextNode("\n" + after));
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
      const count = Number(issue?.count) || 0;
      if (issue?.code === "models_unavailable" && count) notes.push(`${count} model${count === 1 ? "" : "s"} did not answer`);
      if ((issue?.code === "sentences_unchecked" || issue?.code === "unindexed_sentences") && count) {
        notes.push(`${count} sentence${count === 1 ? "" : "s"} could not be checked`);
      }
    }
    return notes.length ? notes.join(" · ") + "." : "";
  }

  function failureText(check, live) {
    if (LIVE.has(check.status) && !live) return "The check of your text did not finish.";
    if (check.status === "cancelled") return "The check of your text was stopped.";
    if (check.issues.some(issue => issue?.code === "insufficient_answers")) {
      return "Your text could not be checked: too few models answered.";
    }
    if (check.issues.some(issue => issue?.code === "no_time")) {
      return "Your text could not be checked: the answer needed the remaining time.";
    }
    return "Your text could not be checked this time.";
  }

  function quotedQuestion(value) {
    const text = normalize(value);
    return text.length > ANSWER_TO_CHARS ? text.slice(0, ANSWER_TO_CHARS - 1).trimEnd() + "…" : text;
  }

  function line(className, text) {
    const node = document.createElement("p");
    node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function renderSummary(wrap, check, live, marked) {
    let summary = wrap.querySelector(":scope > .passage-check");
    if (!summary) {
      summary = document.createElement("div");
      summary.className = "passage-check";
      summary.setAttribute("role", "status");
      wrap.append(summary);
    }
    summary.dataset.state = DONE.has(check.status) ? "done" : LIVE.has(check.status) && live ? "running" : "failed";
    const lines = [];
    if (LIVE.has(check.status) && live) {
      lines.push(line("passage-check-head", check.status === "running"
        ? "Checking each sentence of your text…"
        : "Checking your text against independent answers…"));
    } else if (!DONE.has(check.status)) {
      lines.push(line("passage-check-head", failureText(check, live)));
    } else {
      // The counts lead: they are what the user came for. Each count with its
      // separator is one unit, so a narrow line never starts with a dot.
      const head = line("passage-check-head");
      if (!check.claims.length) head.append("No checkable statements found in your text.");
      const tally = counts(check);
      for (const state of STATES) {
        if (!tally[state]) continue;
        const unit = document.createElement("span");
        unit.className = "passage-check-unit";
        if (head.childNodes.length) {
          head.append(" ");
          unit.append("· ");
        }
        // A count jumps to its first sentence, so it is a control only
        // where the sentences are marked.
        const chip = document.createElement(marked ? "button" : "span");
        chip.className = `passage-check-count is-${state}`;
        chip.dataset.verdict = state;
        chip.textContent = CHIP_LABELS[state](tally[state]);
        if (marked) {
          chip.type = "button";
          chip.setAttribute("aria-label", `${chip.textContent}: show the first one`);
        }
        unit.append(chip);
        head.append(unit);
      }
      lines.push(head);
    }
    if (check.answerTo && (DONE.has(check.status) || live)) {
      const note = issueNote(check);
      const against = DONE.has(check.status) ? `Checked against ${check.models.length} models as` : "As";
      lines.push(line("passage-check-note",
        `${against} an answer to “${quotedQuestion(check.answerTo)}”. `
        + "The models answered without seeing your text." + (note ? ` ${note}` : "")));
    }
    summary.replaceChildren(...lines);
  }

  function open(wrap) {
    if (wrap.classList.contains("is-open")) return;
    wrap.classList.add("is-open");
    const more = wrap.querySelector(":scope > .thread-ask-more");
    if (more) {
      more.textContent = "Collapse question";
      more.setAttribute("aria-expanded", "true");
    }
  }

  // A count chip jumps to the first sentence with that verdict and opens it.
  function focusVerdict(wrap, state) {
    const span = wrap.querySelector(`.pc-claim[data-verdict="${state}"]`);
    if (!span) return;
    open(wrap);
    span.scrollIntoView({ block: "center", behavior: "smooth" });
    span.focus({ preventScroll: true });
    openDetails(wrap, span);
  }

  function bind(wrap) {
    if (wrap._passageCheckBound) return;
    wrap._passageCheckBound = true;
    wrap.addEventListener("click", event => {
      const chip = event.target.closest(".passage-check-count");
      if (chip && wrap.contains(chip)) {
        focusVerdict(wrap, chip.dataset.verdict);
        return;
      }
      const span = event.target.closest(".pc-claim");
      // Selecting pasted text (to copy it, or for the memory toolbar) is not
      // a request for the card.
      if (window.getSelection?.()?.isCollapsed === false) return;
      if (span && wrap.contains(span)) openDetails(wrap, span);
    });
    wrap.addEventListener("keydown", event => {
      const span = event.target.closest?.(".pc-claim");
      if (!span || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      openDetails(wrap, span);
    });
  }

  function textElement(wrap) {
    return wrap?.querySelector(":scope > .thread-ask-text, :scope > .thread-history-question-text") || null;
  }

  function clear(wrap, text) {
    wrap.querySelector(":scope > .passage-check")?.remove();
    if (!wrap.classList.contains("has-passage-check")) return;
    wrap.classList.remove("has-passage-check");
    if (text) text.textContent = text.dataset.question || normalize(wrap._passageQuestion);
    window.App.syncThreadAskClamp?.(wrap);
  }

  // Draws the check of `review` onto a question bubble, or removes a stale
  // one. Called on every projection; unchanged input does nothing.
  function apply(wrap, text, question, review, options = {}) {
    if (!wrap) return;
    text = text || textElement(wrap);
    const check = from(review);
    const live = Boolean(options.live);
    // A finished check reads the same live or saved; the end of the run must
    // not redraw it (that dropped focus and an open card's anchor).
    const signature = check
      ? JSON.stringify([normalize(question), DONE.has(check.status) ? false : live, review.passage_check]) : "";
    wrap._passageReview = review || null;
    // Unchanged input changes nothing: the summary is a live region, and
    // rebuilding it on every streamed chunk would make it speak again.
    if (wrap._passageSignature === signature) return;
    wrap._passageSignature = signature;
    wrap._passageCheck = check;
    wrap._passageQuestion = question;
    wrap._passageLive = live;
    if (!check || !text) {
      clear(wrap, text);
      return;
    }
    const marked = DONE.has(check.status) && check.claims.length && renderText(text, question, check);
    if (marked) wrap.classList.add("has-passage-check");
    // No marks yet (or none to show): the plain message, plus the line below.
    else if (wrap.classList.contains("has-passage-check")) clear(wrap, text);
    renderSummary(wrap, check, live, Boolean(marked));
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
      clear(wrap, text);
      return;
    }
    const review = wrap._passageReview;
    wrap._passageSignature = "";
    apply(wrap, text, question, review, { live: wrap._passageLive });
  }

  window.App.passageCheck = { apply, restore, verdict, from };
})();
