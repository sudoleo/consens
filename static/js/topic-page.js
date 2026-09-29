/* Topic page: the check strip readout, the returning-reader band, the follow
 * form and the inline citation chips.
 *
 * All of it is progressive: the page is complete without this file. The strip
 * is rendered server-side and stays readable as a shape; the band is empty
 * until this browser proves it has been here before. Nothing is sent anywhere
 * by the strip or the band -- the last-visit mark lives in this browser only.
 *
 * This file holds every script of templates/topic.html, so the page runs under
 * a script CSP without 'unsafe-inline' (app/core/security.py). Data text such
 * as a change summary is only ever inserted as text.
 */
(function () {
  "use strict";

  var STORE_PREFIX = "topic-seen:";

  function readStrip() {
    var strip = document.getElementById("topicStrip");
    var read = document.getElementById("topicStripRead");
    if (!strip || !read) return null;
    var cells = Array.prototype.slice.call(
      strip.querySelectorAll(".topic-strip-cell")
    );
    // The server-rendered resting line is kept as nodes, never as markup.
    var resting = Array.prototype.map.call(read.childNodes, function (node) {
      return node.cloneNode(true);
    });

    // Without a pointer that can hover there is no way to read a cell before
    // following it, so the first tap previews and the second one opens.
    var canHover = !window.matchMedia || window.matchMedia("(hover: hover)").matches;
    var previewed = null;

    // dataset values are decoded attribute text: a change summary comes from
    // model output, so it is only ever inserted as text, never parsed as HTML.
    function show(cell) {
      var date = document.createElement("b");
      date.textContent = cell.dataset.date || "";
      var parts = [date, " \u2014 " + (cell.dataset.note || "")];
      if (cell.dataset.score) {
        var score = document.createElement("span");
        score.className = "topic-strip-score";
        score.textContent = cell.dataset.score + "/100 agreement";
        parts.push(" ", score);
      }
      read.replaceChildren.apply(read, parts);
    }

    function restore() {
      read.replaceChildren.apply(read, resting.map(function (node) {
        return node.cloneNode(true);
      }));
    }

    cells.forEach(function (cell) {
      cell.addEventListener("mouseenter", function () { show(cell); });
      cell.addEventListener("focus", function () { show(cell); });
      cell.addEventListener("click", function (event) {
        if (!canHover && previewed !== cell) {
          event.preventDefault();
          previewed = cell;
          show(cell);
        }
      });
    });
    strip.addEventListener("mouseleave", restore);
    return {strip: strip, cells: cells};
  }

  function store(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      /* Private mode or blocked storage: the band simply never appears. */
    }
  }

  function readStore(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function returningReader(strip, cells) {
    var band = document.getElementById("topicReturn");
    if (!band || !cells.length) return;
    // Browsing an older version must not mark the newer checks as seen.
    if (window.location.search.indexOf("version=") !== -1) return;
    var key = STORE_PREFIX + (strip.dataset.slug || "");
    var seen = readStore(key);
    var latest = cells[cells.length - 1].dataset.iso || "";

    if (seen && latest && seen < latest) {
      var fresh = cells.filter(function (cell) {
        return (cell.dataset.iso || "") > seen;
      });
      if (fresh.length) {
        fresh.forEach(function (cell) { cell.classList.add("is-unseen"); });
        var moved = fresh.filter(function (cell) {
          return cell.dataset.kind === "material";
        });
        var stirred = fresh.filter(function (cell) {
          return cell.dataset.kind === "event";
        });
        var count = fresh.length + " check" + (fresh.length === 1 ? "" : "s");
        var line;
        if (moved.length) {
          band.classList.add("is-moved");
          line = count + " since your last visit, and the answer moved on " +
            moved[moved.length - 1].dataset.date + ".";
        } else if (stirred.length) {
          line = count + " since your last visit. The answer held; " +
            stirred.length + " of those check" + (stirred.length === 1 ? "" : "s") +
            " changed which statements were made.";
        } else {
          line = count + " since your last visit. The answer did not move.";
        }
        var tag = document.createElement("span");
        tag.className = "topic-return-tag";
        tag.textContent = "Since your last visit";
        var text = document.createElement("p");
        var link = document.createElement("a");
        link.href = "#facts";
        link.textContent = "See the statements";
        text.append(line + " ", link);
        band.replaceChildren(tag, text);
        band.hidden = false;
      }
    }
    if (latest) store(key, latest);
  }

  function followForm() {
    var form = document.getElementById("topicFollowForm");
    if (!form) return;
    var status = document.getElementById("topicFollowStatus");
    var button = form.querySelector("button");
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      button.disabled = true;
      status.textContent = "Sending confirmation…";
      try {
        var response = await fetch("/api/topics/" + encodeURIComponent(form.dataset.slug) + "/follow", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({email: form.email.value})
        });
        var data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not follow this Topic.");
        status.textContent = data.message;
        form.reset();
      } catch (error) {
        status.textContent = error.message;
        status.classList.add("is-error");
      } finally {
        button.disabled = false;
      }
    });
  }

  // Inline citations behave as chips that reveal their embedded source.
  function citationChips() {
    var prose = document.querySelector(".topic-consensus");
    if (!prose) return;
    var timer = null;
    function flash(target) {
      if (!target) return;
      var holder = target.closest("details");
      if (holder && !holder.open) holder.open = true;
      target.scrollIntoView({behavior: "smooth", block: "center"});
      target.classList.add("is-cited");
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(function () { target.classList.remove("is-cited"); }, 2200);
    }
    prose.querySelectorAll('a[href^="#src-"]').forEach(function (link) {
      link.classList.add("source-chip");
      var target = document.getElementById(decodeURIComponent(link.getAttribute("href").slice(1)));
      if (target) {
        var srcImg = target.querySelector(".src-favicon-img");
        var url = srcImg && srcImg.getAttribute("src");
        if (!url) {
          // e.g. X cards carry no favicon slot: derive it from the source URL.
          try {
            var host = new URL(target.getAttribute("href"), window.location.href).hostname.replace(/^www\./, "");
            if (host) url = "/api/topics/favicon?d=" + encodeURIComponent(host);
          } catch (e) { /* keep the dot fallback */ }
        }
        if (url) {
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
        }
      }
      link.addEventListener("click", function (event) {
        if (!target) return;
        event.preventDefault();
        flash(target);
      });
    });
  }

  // Drop favicons that fail to load so the monogram fallback shows through.
  function faviconFallback() {
    document.querySelectorAll(".src-favicon-img").forEach(function (img) {
      function fail() { img.remove(); }
      img.addEventListener("error", fail);
      if (img.complete && img.naturalWidth === 0) fail();
    });
  }

  function start() {
    followForm();
    citationChips();
    faviconFallback();
    var found = readStrip();
    if (!found) return;
    returningReader(found.strip, found.cells);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
