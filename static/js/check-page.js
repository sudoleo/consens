/* Shared behaviour of the pages built from templates/partials/check_page.html:
 * Watch pages (watch_share.html) and Topic pages (topic.html).
 *
 * All of it is progressive: every page is complete without this file. It is
 * an external file because Topic pages run under a script CSP without
 * 'unsafe-inline' (app/core/security.py).
 */
(function () {
  "use strict";

  // Long questions fold to three lines; with nothing cut off, the link stays
  // hidden.
  function clampQuestion() {
    var question = document.getElementById("shareQuestion");
    var more = document.getElementById("shareQuestionMore");
    if (!question || !more) return;
    question.classList.add("is-clamped");
    function measure() {
      var clamped = question.getBoundingClientRect().height;
      question.classList.remove("is-clamped");
      var full = question.getBoundingClientRect().height;
      var clipped = full - clamped > 4;
      if (clipped) question.classList.add("is-clamped");
      more.hidden = !clipped;
    }
    requestAnimationFrame(measure);
    more.addEventListener("click", function () {
      var open = question.classList.toggle("is-clamped") === false;
      more.setAttribute("aria-expanded", String(open));
      more.textContent = open ? "Collapse question" : "Show full question";
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

  // Sources start folded; a jump from an inline citation (#src-N) opens them.
  function foldSources() {
    var list = document.getElementById("shareSources");
    var toggle = document.getElementById("shareSourcesToggle");
    if (!list || !toggle) return;
    list.classList.add("is-collapsed", "is-short");
    toggle.hidden = false;
    function expand() {
      list.classList.remove("is-collapsed", "is-short");
      toggle.hidden = true;
    }
    toggle.addEventListener("click", expand);
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

  // Missing favicons disappear; inline citations get the one of their source.
  function favicons() {
    document.querySelectorAll(".share-source-favicon").forEach(function (img) {
      function fail() { img.remove(); }
      img.addEventListener("error", fail);
      if (img.complete && img.naturalWidth === 0) fail();
    });
    document.querySelectorAll('.share-md a[href^="#src-"]').forEach(function (link) {
      var target = document.getElementById(decodeURIComponent(link.getAttribute("href").slice(1)));
      var srcImg = target && target.querySelector(".share-source-favicon");
      var url = srcImg && srcImg.getAttribute("src");
      if (!url) return;
      var fav = document.createElement("img");
      fav.className = "cite-favicon";
      fav.setAttribute("src", url);
      fav.setAttribute("alt", "");
      fav.setAttribute("aria-hidden", "true");
      fav.addEventListener("error", function () {
        fav.remove();
        link.classList.remove("has-favicon");
      });
      link.insertBefore(fav, link.firstChild);
      link.classList.add("has-favicon");
    });
  }

  // A link to a check (#watch-run-…) inside a folded group of quiet checks
  // opens the group.
  function revealCheck() {
    function reveal() {
      var hash = window.location.hash || "";
      if (hash.indexOf("#watch-run-") !== 0) return;
      var target = document.getElementById(hash.slice(1));
      var group = target && target.closest("details");
      if (!group || group.open) return;
      group.open = true;
      target.scrollIntoView({ block: "center" });
    }
    window.addEventListener("hashchange", reveal);
    reveal();
  }

  function start() {
    clampQuestion();
    dropMissingImage();
    foldSources();
    favicons();
    revealCheck();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
