/* ==========================================================================
   consens.io — landing page: the marked passage in the mockups works

   The mockups on the landing page are rebuilds of the /app surfaces. Since
   2026-10-31 (the Agent's one mode) the reviewers' marks are what an answer
   carries: no agreement ratio behind a sentence any more, so the ratio
   badges and their popover left this file. What stays is the marked
   passage in "03 · Decide", with the behaviour it has in
   static/js/consensus-insights.js:

     hover (pointer devices)  short version in an .insight-preview card
     click / Enter            the card with the reviewer's note opens and
                              flashes (landing.html, data-diff-open)

   The hover preview is read straight out of that card, so the two can
   never drift apart.
   ========================================================================== */
(function () {
  "use strict";

  const HOVER_DELAY_MS = 130;

  const canHover = () =>
    !!(window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches);

  // ---------------------------------------------------------------- preview
  let hoverCard = null;
  let hoverTimer = null;

  function ensureHoverCard() {
    if (hoverCard && hoverCard.isConnected) return hoverCard;
    hoverCard = document.createElement("div");
    hoverCard.className = "insight-preview";
    hoverCard.setAttribute("aria-hidden", "true");
    hoverCard.hidden = true;
    document.body.appendChild(hoverCard);
    return hoverCard;
  }

  function hidePreview() {
    window.clearTimeout(hoverTimer);
    hoverTimer = null;
    if (hoverCard) {
      hoverCard.hidden = true;
      hoverCard.replaceChildren();
    }
  }

  function previewHead(text, sevClass) {
    const head = document.createElement("div");
    head.className = "insight-preview-head";
    if (sevClass) {
      const dot = document.createElement("span");
      dot.className = "sev-dot " + sevClass;
      dot.setAttribute("aria-hidden", "true");
      head.appendChild(dot);
    }
    const label = document.createElement("span");
    label.textContent = text;
    head.appendChild(label);
    return head;
  }

  function previewRow(label, text) {
    const row = document.createElement("div");
    row.className = "insight-preview-row";
    const key = document.createElement("span");
    key.className = "insight-preview-key";
    key.textContent = label;
    const value = document.createElement("span");
    value.className = "insight-preview-value";
    value.textContent = text;
    row.append(key, value);
    return row;
  }

  /* Anchored under the element that owns the mark, flipped above it when the
     bottom of the window is closer than the card is tall. */
  function placePreview(card, anchor) {
    const rect = anchor.getBoundingClientRect();
    const width = Math.min(340, window.innerWidth - 24);
    card.style.width = width + "px";

    const centred = rect.left + rect.width / 2 - width / 2;
    const left = Math.max(12, Math.min(centred, window.innerWidth - width - 12));
    card.style.left = (left + window.scrollX) + "px";

    const height = card.offsetHeight;
    const below = rect.bottom + 8;
    const fitsBelow = below + height <= window.innerHeight - 12;
    const top = fitsBelow ? below : Math.max(12, rect.top - height - 8);
    card.style.top = (top + window.scrollY) + "px";
  }

  function schedulePreview(anchor, build) {
    window.clearTimeout(hoverTimer);
    hoverTimer = window.setTimeout(function () {
      const content = build();
      if (!content) return;
      const card = ensureHoverCard();
      card.replaceChildren(content);
      card.hidden = false;
      placePreview(card, anchor);
    }, HOVER_DELAY_MS);
  }

  // A card pinned to a screen position is wrong the moment anything moves.
  window.addEventListener("scroll", hidePreview, true);
  window.addEventListener("resize", hidePreview);
  // Dismissable without moving the pointer (WCAG 1.4.13).
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && hoverCard && !hoverCard.hidden) hidePreview();
  }, true);

  /* The mark's preview is read out of the card it opens, so the summary can
     never say something the card below does not: its kind, the words it
     concerns, the reviewer's note. */
  function buildNotePreview(cardId) {
    const card = document.getElementById(cardId);
    if (!card) return null;
    const frag = document.createDocumentFragment();
    const sev = card.querySelector(".sev-dot");
    const sevClass = sev && sev.classList.contains("is-crit") ? "is-crit" : "is-warn";
    frag.appendChild(previewHead(
      (card.querySelector(".diff-type-tag") || {}).textContent || "Notes", sevClass));

    const claimText = card.querySelector(".diff-card-claim");
    if (claimText) {
      const el = document.createElement("div");
      el.className = "insight-preview-claim";
      el.textContent = claimText.textContent;
      frag.appendChild(el);
    }

    Array.from(card.querySelectorAll(".diff-position")).slice(0, 2).forEach(pos => {
      const who = pos.querySelector(".diff-position-label");
      const note = pos.querySelector(".diff-position-stance");
      frag.appendChild(previewRow(who ? who.textContent : "", note ? note.textContent : ""));
    });

    const foot = document.createElement("div");
    foot.className = "insight-preview-foot";
    foot.textContent = "Click to open the notes";
    frag.appendChild(foot);
    return frag;
  }

  function wireMark(trigger) {
    if (!canHover()) return;
    const cardId = trigger.dataset.diffOpen;
    trigger.addEventListener("mouseenter", () =>
      schedulePreview(trigger, () => buildNotePreview(cardId)));
    trigger.addEventListener("mouseleave", hidePreview);
  }

  function init() {
    document.querySelectorAll("[data-diff-open]").forEach(wireMark);
    // Clicking a marked passage means "show me the card", not "keep the
    // summary" — landing.html handles the opening, this only clears the hint.
    document.addEventListener("click", hidePreview, true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
