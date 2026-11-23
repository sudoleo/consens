// =====================================================================
// answer-copy.js
// Copy under an Agent answer, and the one preparation of an answer for the
// clipboard (Copy consensus in consensus-actions.js copies through it too).
// Export: window.App.answerCopy {button, clean, text, payload, write}.
// (write: also what copies one table of an answer, markdown-stream.js.)
// Uses window.App.sourceRefs (sources.js) and App.answerTail
// (agent-workspace.js) at runtime.
// =====================================================================

(function () {
  "use strict";
  const App = window.App = window.App || {};

  // An answer leaves the page as its words, never the page's own controls.
  // A source pill reads "uci.org +2" in the DOM, which is no citation: the
  // copy writes its domains in brackets ("(uci.org, pcs.com)"). The clone
  // carries no JS properties, so the pills are read from the originals.
  // A drawn diagram shows a picture and hides its source (diagram.css); the
  // copy carries the source, as a code block would.
  function clean(body) {
    const clone = body.cloneNode(true);
    clone.querySelectorAll(".claim-badge, .copy-btn, .code-copy, .md-block-tools").forEach(el => el.remove());
    const originalRefs = Array.from(body.querySelectorAll(".src-ref"));
    clone.querySelectorAll(".src-ref").forEach((ref, index) => {
      ref.replaceWith(document.createTextNode(App.sourceRefs?.plainText(originalRefs[index]) || ""));
    });
    clone.querySelectorAll(".src-ref-sep").forEach(el => el.remove());
    clone.querySelectorAll(".md-diagram").forEach(place => {
      const source = place.querySelector(":scope > pre");
      if (source) place.replaceWith(source);
      else place.remove();
    });
    return clone;
  }

  // The words as the page shows them, line breaks included. innerText needs
  // a rendered element (and leaves out display:none children only then), so
  // the copy stands off screen for that moment.
  function text(body) {
    if (!body) return "";
    const clone = clean(body);
    clone.style.position = "absolute";
    clone.style.left = "-99999px";
    clone.style.top = "0";
    document.body.appendChild(clone);
    const words = clone.innerText.trim();
    clone.remove();
    return words;
  }

  // The rendered answer for a target that takes formatting (Word, mail):
  // headings, lists, tables and links stay. What this page draws for itself
  // goes: a picture of the turn (a file of the workspace no one else can
  // open), what is hidden from screen readers (KaTeX's visual copy of a
  // formula beside its MathML, the bars of a column), the buttons. Classes,
  // data and states of this page mean nothing there.
  const KEPT_ATTRIBUTES = { A: ["href"], IMG: ["src", "alt"], TD: ["colspan", "rowspan", "align"],
    TH: ["colspan", "rowspan", "align"], OL: ["start"] };
  const SAFE_URL = /^(https?:|mailto:)/i;
  function html(body) {
    const clone = clean(body);
    // A checklist's box is a button of this page; the copy keeps its state.
    clone.querySelectorAll(".md-task-box").forEach(box => {
      box.replaceWith(document.createTextNode(box.getAttribute("aria-checked") === "true" ? "☑ " : "☐ "));
    });
    clone.querySelectorAll('.md-picture, [aria-hidden="true"], button, input, script, style').forEach(el => el.remove());
    for (const el of [clone, ...clone.querySelectorAll("*")]) {
      const kept = KEPT_ATTRIBUTES[el.tagName] || [];
      for (const { name, value } of Array.from(el.attributes)) {
        const unsafe = (name === "href" || name === "src") && !SAFE_URL.test(value.trim());
        if (!kept.includes(name) || unsafe) el.removeAttribute(name);
      }
    }
    return clone.innerHTML.trim();
  }

  // The Markdown the answer was written in, without the places of the
  // turn's pictures ("![…](picture:p2)", markdown-stream.js), which name
  // nothing outside this page.
  const PICTURE_PLACE = /!\[[^\]\n]*\]\(\s*picture:[A-Za-z0-9_-]{1,64}\s*\)/g;
  function markdown(body) {
    return String(body?.dataset.markdown || "").replace(PICTURE_PLACE, "").replace(/\n{3,}/g, "\n\n").trim();
  }

  // What Copy puts on the clipboard: the Markdown as text, the rendered
  // answer as HTML.
  function payload(body) {
    return { text: markdown(body), html: html(body) };
  }

  // Both kinds at once where the browser takes them; else through a copy
  // event (also within the click), else the text alone.
  async function write({ text: words, html: rich }) {
    if (typeof window.ClipboardItem === "function" && navigator.clipboard?.write) {
      try {
        await navigator.clipboard.write([new window.ClipboardItem({
          "text/plain": new Blob([words], { type: "text/plain" }),
          "text/html": new Blob([rich], { type: "text/html" }),
        })]);
        return;
      } catch (_) { /* a browser that refuses HTML here: the copy event below */ }
    }
    const put = event => {
      event.clipboardData?.setData("text/plain", words);
      event.clipboardData?.setData("text/html", rich);
      event.preventDefault();
    };
    document.addEventListener("copy", put);
    let copied = false;
    try { copied = document.execCommand("copy"); } catch (_) { copied = false; }
    document.removeEventListener("copy", put);
    if (copied) return;
    if (!navigator.clipboard?.writeText) throw new Error("Copy unavailable");
    await navigator.clipboard.writeText(words);
  }

  // The cell under an answer: the build of Watch and Share (watch.js,
  // share-dialog.js), a glyph and a word. Its feedback swaps both in place:
  // "Copied" stands over "Copy" in the same cell (components-watch.css), so
  // nothing beside it moves.
  const COPY_ICON = '<svg class="share-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="agent-copy-glyph" d="M9 9h11v11H9zM15 5V3H3v12h2"></path><path class="agent-copied-glyph" d="M5 12.5l4.5 4.5L19 7"></path></svg>';
  const COPIED_MS = 1600;
  function createPill(body) {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = "consensus-share-pill agent-copy-pill";
    pill.innerHTML = COPY_ICON;
    const word = document.createElement("span");
    word.className = "agent-copy-word";
    const copy = document.createElement("span");
    copy.textContent = "Copy";
    const copied = document.createElement("span");
    copied.textContent = "Copied";
    copied.setAttribute("aria-hidden", "true");
    word.append(copy, copied);
    pill.append(word);
    const label = done => {
      const words = done ? "Copied" : "Copy answer";
      pill.title = words;
      pill.setAttribute("aria-label", words);
    };
    label(false);
    pill.addEventListener("click", async () => {
      // The answer as it stands now: a correction may have rewritten it.
      const owner = pill._answerBody;
      if (!owner?.dataset.markdown?.trim()) return;
      clearTimeout(pill._copiedTimer);
      try {
        await write(payload(owner));
      } catch (_) {
        App.toast?.({ message: "Copy to clipboard failed.", tone: "error" });
        return;
      }
      pill.classList.add("is-copied");
      label(true);
      pill._copiedTimer = setTimeout(() => {
        pill.classList.remove("is-copied");
        label(false);
      }, COPIED_MS);
      App.trackAppEvent?.("app_answer_copied", {});
    });
    pill._answerBody = body;
    return pill;
  }

  const rowOf = pill => pill?.closest(".agent-watch-pill-row") || null;

  // Every finished Agent answer has its Copy: the live one (agent-chat.js,
  // on every projection), a reopened chat's and each turn of the history
  // (thread-history.js, built off the page). It is the first of the answer's
  // actions, right after the evidence links, so it keeps its place whether
  // a Watch pill follows (only under the newest answer) or not; Watch and
  // Share place themselves after it. Without an evidence row it opens the
  // row Watch and Share stand in.
  function syncAnswerCopyButton(answerBody, { eligible = false } = {}) {
    if (!answerBody) return;
    let pill = answerBody._copyPill;
    const ownRow = rowOf(pill);
    if (!eligible) {
      pill?.remove();
      if (ownRow && !ownRow.children.length) ownRow.remove();
      answerBody._copyPill = null;
      return;
    }
    if (!pill) {
      pill = createPill(answerBody);
      answerBody._copyPill = pill;
    }
    // Also off the page: a history turn is built before it is inserted.
    const review = answerBody._agentReview?.parentNode && answerBody._agentReview.parentNode === answerBody.parentNode
      ? answerBody._agentReview : null;
    const nav = review ? review.querySelector(".agent-evidence-links") : null;
    if (nav) {
      if (nav.nextElementSibling !== pill) nav.after(pill);
      if (ownRow && !ownRow.children.length) ownRow.remove();
      return;
    }
    const sharedRow = rowOf(answerBody._watchPill) || rowOf(answerBody._sharePill);
    let row = sharedRow || ownRow;
    if (!row) {
      row = document.createElement("div");
      row.className = "agent-watch-pill-row";
    }
    if (row.firstElementChild !== pill) row.prepend(pill);
    if (ownRow && ownRow !== row && !ownRow.children.length) ownRow.remove();
    const after = review || App.answerTail?.(answerBody) || answerBody;
    if (!row.parentNode || (!sharedRow && after.nextElementSibling !== row)) after.after(row);
  }

  App.answerCopy = { button: syncAnswerCopyButton, clean, text, payload, write };
})();
