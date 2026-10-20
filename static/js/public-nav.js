/* The navigation of every public page (templates/partials/public_nav.html).
 *
 * An external file, because Topic pages run under a script CSP without
 * 'unsafe-inline' (app/core/security.py). Everything here is progressive: the
 * bar, the <details> menu and every link work without it.
 *
 * 1. The menu (<details class="nav-menu">, phones) closes the way a menu
 *    does: tapping beside it, choosing a link, Escape, scrolling. It leaves
 *    with the same short movement it arrives with.
 * 2. Smooth scrolling is a reply to a click on this page, never part of
 *    arriving. A link to /#watch from another page used to land on the top of
 *    the landing page and then glide 8,000 px through every scene; now the
 *    browser jumps straight to the section, and only once the page has loaded
 *    does `html.is-scroll-smooth` (landing.css, public-pages.css) switch the
 *    glide on for in-page links.
 * 3. On the landing page the bar marks the section you are in: "Watches"
 *    while #watch fills the screen, "Product" everywhere else.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var reducedMotion = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- 1. Menu ---------------------------------------------------------

  function setupMenu(menu) {
    var summary = menu.querySelector("summary");
    var panel = menu.querySelector(".nav-menu-panel");
    if (!summary || !panel) return;
    var closing = 0;
    var openedAtScroll = 0;

    function finish() {
      window.clearTimeout(closing);
      closing = 0;
      menu.classList.remove("is-closing");
      menu.open = false;
    }

    function close(returnFocus) {
      if (!menu.open || closing) return;
      if (returnFocus) summary.focus();
      if (reducedMotion) {
        finish();
        return;
      }
      menu.classList.add("is-closing");
      // animationend is the signal; the timer is the net for a panel whose
      // animation never ran (display changes, a backgrounded tab).
      closing = window.setTimeout(finish, 260);
    }

    panel.addEventListener("animationend", function (event) {
      if (event.animationName === "nav-menu-out") finish();
    });

    summary.addEventListener("click", function (event) {
      if (!menu.open) {
        openedAtScroll = window.scrollY || 0;
        return;
      }
      // Closing through the mark gets the exit movement too.
      event.preventDefault();
      close(false);
    });

    document.addEventListener("click", function (event) {
      if (!menu.open) return;
      if (!menu.contains(event.target)) close(false);
      else if (event.target.closest && event.target.closest(".nav-menu-panel a")) close(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && menu.open) close(true);
    });

    // A menu that rides along over the text is in the way: a real scroll
    // (not the few pixels a tap can nudge) closes it.
    window.addEventListener("scroll", function () {
      if (menu.open && Math.abs((window.scrollY || 0) - openedAtScroll) > 24) close(false);
    }, { passive: true });

    // Grown past the phone layout, the menu mark is gone: so is the menu.
    if (window.matchMedia) {
      var wide = window.matchMedia("(min-width: 701px)");
      var onWide = function () { if (wide.matches && menu.open) finish(); };
      if (wide.addEventListener) wide.addEventListener("change", onWide);
    }
  }

  // ---- 2. Smooth scrolling only after arriving -------------------------

  function enableSmoothScroll() {
    // Two frames after load: the browser's own jump to the #fragment (and its
    // re-check once layout has settled) is done by then.
    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        root.classList.add("is-scroll-smooth");
      });
    });
  }

  // Late layout (a picture without a size, the scenes measuring themselves)
  // can push the section after the browser has jumped to it. As long as the
  // reader has not scrolled yet, put the section back under the bar.
  function keepFragmentInPlace() {
    var id = "";
    try { id = decodeURIComponent((window.location.hash || "").slice(1)); } catch (_) { return; }
    if (!id) return;
    // Back, forward and reload restore the reader's own position; only a
    // fresh visit to a #fragment is the browser's jump to keep.
    var entry = window.performance && performance.getEntriesByType
      ? performance.getEntriesByType("navigation")[0] : null;
    if (entry && entry.type && entry.type !== "navigate") return;
    var touched = false;
    var mark = function () { touched = true; };
    ["wheel", "touchstart", "keydown", "pointerdown"].forEach(function (type) {
      window.addEventListener(type, mark, { passive: true, once: true });
    });
    function realign() {
      if (touched) return;
      var target = document.getElementById(id);
      if (!target) return;
      var bar = document.querySelector(".site-nav");
      var expected = bar ? bar.getBoundingClientRect().height : 0;
      var top = target.getBoundingClientRect().top;
      if (Math.abs(top - expected) > 2 && Math.abs(top - expected) < window.innerHeight * 3) {
        window.scrollBy(0, top - expected);
      }
    }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(realign).catch(function () {});
    window.addEventListener("load", realign);
  }

  // ---- 3. The section you are in (landing page) ------------------------

  function trackSections() {
    if (window.location.pathname !== "/") return;
    var links = Array.prototype.slice.call(
      document.querySelectorAll('.site-nav a[href^="/#"]')
    );
    var watch = document.getElementById("watch");
    if (!links.length || !watch) return;
    var current = "";
    var frame = 0;

    function update() {
      frame = 0;
      var box = watch.getBoundingClientRect();
      var middle = window.innerHeight / 2;
      var section = box.top <= middle && box.bottom > middle ? "watch" : "product";
      if (section === current) return;
      current = section;
      links.forEach(function (link) {
        if (link.getAttribute("href") === "/#" + section) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
    }

    window.addEventListener("scroll", function () {
      if (!frame) frame = window.requestAnimationFrame(update);
    }, { passive: true });
    window.addEventListener("resize", update, { passive: true });
    update();
  }

  function start() {
    Array.prototype.forEach.call(document.querySelectorAll(".site-nav .nav-menu"), setupMenu);
    trackSections();
  }

  keepFragmentInPlace();
  if (document.readyState === "complete") enableSmoothScroll();
  else window.addEventListener("load", enableSmoothScroll);

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
