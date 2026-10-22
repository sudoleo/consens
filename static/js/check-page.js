/* Shared behaviour of the pages built from templates/partials/check_page.html
 * (Watch pages, Topic pages) and of the one-off share page (share.html).
 *
 * All of it is progressive: every page is complete without this file. It is
 * an external file because Topic pages run under a script CSP without
 * 'unsafe-inline' (app/core/security.py).
 *
 * Since 2026-10-20 (Apple-Audit) nothing here changes the layout after the
 * first paint unless the reader asks for it: the long question and the long
 * source list arrive folded from the server (I2, L11), a missing site icon
 * keeps its box (I7), and every fold opens and closes with one height
 * movement and leaves the focus in what it opened (L9, L14).
 */
(function () {
  "use strict";

  var reducedMotion = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // --dur-layer * 1.6 with --ease-standard (foundation.css): long enough that
  // a tall fold does not move tens of pixels per frame.
  var FOLD_MS = 320 * 1.6;
  var FOLD_EASE = "cubic-bezier(0.2, 0, 0, 1)";

  // Height of `element` from `from` to its natural height (or to `to`).
  // Returns a promise for when it is done; instant with reduced motion or
  // where the Web Animations API is missing.
  function animateHeight(element, from, to) {
    if (reducedMotion || typeof element.animate !== "function" || from === to) {
      return Promise.resolve();
    }
    var animation = element.animate(
      [{ height: from + "px", overflow: "hidden" }, { height: to + "px", overflow: "hidden" }],
      { duration: FOLD_MS, easing: FOLD_EASE }
    );
    return new Promise(function (resolve) {
      animation.onfinish = resolve;
      animation.oncancel = resolve;
    });
  }

  function height(element) {
    return element.getBoundingClientRect().height;
  }

  // ---- Long question --------------------------------------------------

  // The template folds a long question to three lines (is-clamped); here we
  // only learn whether anything is actually cut off. The link sits on the
  // third line (public-pages.css), so showing it moves nothing.
  function clampQuestion() {
    var question = document.getElementById("shareQuestion");
    var more = document.getElementById("shareQuestionMore");
    if (!question || !more) return;
    if (!question.classList.contains("is-clamped")) question.classList.add("is-clamped");
    var open = false;

    function measure() {
      if (open) return;
      // Measured in one go, inside one frame: nothing is painted unfolded.
      var clamped = height(question);
      question.classList.remove("is-clamped");
      var full = height(question);
      question.classList.add("is-clamped");
      var clipped = full - clamped > 4;
      more.hidden = !clipped;
      question.parentNode.classList.toggle("is-clipped", clipped);
    }

    window.requestAnimationFrame(measure);
    var resizeFrame = 0;
    window.addEventListener("resize", function () {
      if (resizeFrame) return;
      resizeFrame = window.requestAnimationFrame(function () {
        resizeFrame = 0;
        measure();
      });
    });

    more.addEventListener("click", function () {
      var from = height(question);
      open = !open;
      question.classList.toggle("is-clamped", !open);
      question.parentNode.classList.toggle("is-open", open);
      more.setAttribute("aria-expanded", String(open));
      more.textContent = open ? "Collapse question" : "Show full question";
      animateHeight(question, from, height(question));
    });
  }

  // The page is cached briefly; a picture removed in the meantime disappears
  // instead of standing there broken.
  function dropMissingImage() {
    var img = document.querySelector(".wp-image img");
    if (!img) return;
    function drop() {
      var figure = img.closest(".wp-image");
      if (figure && figure.parentNode) figure.parentNode.classList.remove("has-image");
      if (figure) figure.remove();
    }
    img.addEventListener("error", drop);
    if (img.complete && img.naturalWidth === 0) drop();
  }

  // ---- Sources ----------------------------------------------------------

  // Folded in the template (is-collapsed); "Show all" opens the list with one
  // movement and moves the focus to the first source that was hidden, so the
  // next Tab does not skip all of them (L9). A jump from an inline citation
  // (#src-N) opens it too.
  function foldSources() {
    var list = document.getElementById("shareSources");
    var toggle = document.getElementById("shareSourcesToggle");
    if (!list || !toggle) return;
    // Pages cached from before 2026-10-20 still fold here.
    if (!list.classList.contains("is-collapsed")) list.classList.add("is-collapsed", "is-short");
    toggle.hidden = false;

    // The folded list shows five sources (is-short, Watch and Topic pages) or
    // eight (share page), as public-pages.css cuts them.
    function hiddenItems() {
      var shown = list.classList.contains("is-short") ? 5 : 8;
      return Array.prototype.slice.call(list.children, shown);
    }

    function expand(options) {
      if (!list.classList.contains("is-collapsed")) return;
      var revealed = hiddenItems();
      var from = height(list);
      list.classList.remove("is-collapsed", "is-short");
      toggle.setAttribute("aria-expanded", "true");
      toggle.hidden = true;
      animateHeight(list, from, height(list));
      if (options && options.focus && revealed.length) {
        var target = revealed[0].querySelector("a") || revealed[0];
        if (!target.hasAttribute("href") && !target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
        try { target.focus({ preventScroll: true }); } catch (_) { target.focus(); }
      }
    }
    toggle.addEventListener("click", function () { expand({ focus: true }); });

    function expandForHash() {
      var hash = window.location.hash || "";
      if (hash.indexOf("#src-") !== 0) return;
      expand();
      var target = document.getElementById(hash.slice(1));
      if (target) target.scrollIntoView({ block: "center" });
    }
    window.addEventListener("hashchange", expandForHash);
    expandForHash();
  }

  // ---- Site icons -------------------------------------------------------

  // A neutral globe in the same box as the icon it replaces.
  var GLOBE = "data:image/svg+xml," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#8a8d93" stroke-width="1.6">'
    + '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.6 3.5 5.4 3.5 8.5s-1.1 5.9-3.5 8.5c-2.4-2.6-3.5-5.4-3.5-8.5S9.6 6.1 12 3.5Z"/></svg>'
  );

  // Icons fade in once loaded (the stylesheet holds them transparent while
  // script runs); a failed one becomes the globe instead of leaving the row.
  function watchIcon(img, onFail) {
    function loaded() { img.classList.add("is-loaded"); }
    function failed() {
      if (img.getAttribute("src") === GLOBE) return;
      img.classList.add("is-missing");
      img.setAttribute("src", GLOBE);
      if (onFail) onFail();
    }
    img.addEventListener("load", loaded);
    img.addEventListener("error", failed);
    if (img.complete) {
      if (img.naturalWidth > 0) loaded();
      else if (img.getAttribute("src")) failed();
    }
  }

  function favicons() {
    document.querySelectorAll(".share-source-favicon, .wp-link-icon, .share-md .wp-ref-icon, .share-md .src-ref-favicon").forEach(function (img) {
      watchIcon(img);
    });
    // Inline citations get the icon of their source (same URL, no request).
    document.querySelectorAll('.share-md a[href^="#src-"]').forEach(function (link) {
      var id = "";
      try { id = decodeURIComponent(link.getAttribute("href").slice(1)); } catch (_) { return; }
      var target = document.getElementById(id);
      var srcImg = target && target.querySelector(".share-source-favicon");
      var url = srcImg && srcImg.getAttribute("src");
      if (!url) return;
      var fav = document.createElement("img");
      fav.className = "cite-favicon site-icon";
      fav.setAttribute("src", url);
      fav.setAttribute("alt", "");
      fav.setAttribute("aria-hidden", "true");
      link.insertBefore(fav, link.firstChild);
      link.classList.add("has-favicon");
      watchIcon(fav);
    });
  }

  // ---- Disclosures --------------------------------------------------------

  // <details class="wp-disclosure">: quiet checks and "How the models
  // compared". The summary toggles it; the body below it opens and closes
  // with one height movement instead of appearing in one frame.
  function animateDisclosures() {
    document.querySelectorAll("details.wp-disclosure").forEach(function (details) {
      var summary = details.querySelector("summary");
      var body = details.querySelector(".wp-disclosure-body");
      if (!summary || !body) return;
      var busy = false;
      summary.addEventListener("click", function (event) {
        if (reducedMotion || typeof body.animate !== "function") return;
        event.preventDefault();
        if (busy) return;
        busy = true;
        if (!details.open) {
          details.open = true;
          animateHeight(body, 0, height(body)).then(function () { busy = false; });
        } else {
          details.classList.add("is-closing");
          animateHeight(body, height(body), 0).then(function () {
            details.open = false;
            details.classList.remove("is-closing");
            busy = false;
          });
        }
      });
    });
  }

  // ---- Jumps to a check -------------------------------------------------

  // A link to a check (#watch-run-…, from the curve or the state line) opens
  // its folded group and marks the check for a moment, so the eye finds what
  // it jumped to.
  function revealCheck() {
    function flash(target) {
      target.classList.remove("is-flash");
      void target.offsetWidth;
      target.classList.add("is-flash");
      window.setTimeout(function () { target.classList.remove("is-flash"); }, 1800);
    }
    function reveal() {
      var hash = window.location.hash || "";
      if (hash.indexOf("#watch-run-") !== 0) return;
      var target = document.getElementById(hash.slice(1));
      if (!target) return;
      var group = target.closest("details");
      if (group && !group.open) {
        group.open = true;
        target.scrollIntoView({ block: "center" });
      }
      flash(target);
    }
    window.addEventListener("hashchange", reveal);
    reveal();
  }

  // ---- Quotes of a difference ---------------------------------------------

  // A side's quote backs its claim and so repeats it: it opens on request, as
  // in the app ("Show quote" in the side's line, the quote under it).
  function quoteToggles() {
    document.addEventListener("click", function (event) {
      var toggle = event.target.closest && event.target.closest(".diff-quote-toggle");
      if (!toggle) return;
      var side = toggle.closest(".diff-position");
      var quote = side && side.querySelector(".diff-position-quote");
      if (!quote) return;
      quote.hidden = !quote.hidden;
      toggle.setAttribute("aria-expanded", String(!quote.hidden));
      toggle.textContent = quote.hidden ? "Show quote" : "Hide quote";
    });
  }

  function start() {
    clampQuestion();
    dropMissingImage();
    foldSources();
    favicons();
    animateDisclosures();
    revealCheck();
    quoteToggles();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
