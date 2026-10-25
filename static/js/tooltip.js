// =====================================================================
// tooltip.js
// App.tooltip: one way the app explains a mark that has no words of its own
// (Apple audit E12). The browser's own title tooltips came late, looked
// different in every browser and never appeared under a finger or for the
// keyboard. This takes them over, for `title` and `data-tooltip` alike:
//
//   - pointer: after a short rest (500 ms; at once when moving on from one
//     mark to the next), in the app's material, beside the mark;
//   - keyboard: the same line when the mark gets focus;
//   - touch: a tap on a mark that does nothing else (a model logo, a token
//     count, a status) shows it for a moment. A control keeps its tap; what
//     its tooltip says is written out where it leads.
//
// `title` stays the element's attribute (scripts and assistive technology
// keep reading it); only while a pointer rests on the element is it parked
// in data-tooltip-title, so the browser does not draw a second, grey one.
// A tooltip that repeats the element's own visible text is not shown;
// `data-tooltip-overflow` is the exception: the element's own text, shown
// only while the element cuts it off (a chat title in the sidebar).
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};

  const REST_MS = 500;
  const CHAIN_MS = 800;   // moving on to the next mark within this: no wait
  const TOUCH_MS = 2600;
  const INTERACTIVE = "a[href], button, input, select, textarea, summary, label, [role='button'], [role='menuitem'], [role='option'], [role='tab'], [contenteditable='true']";

  let tip = null;
  let target = null;
  let timer = 0;
  let hideTimer = 0;
  let lastHiddenAt = 0;

  function ensure() {
    if (tip?.isConnected) return tip;
    tip = document.querySelector(".global-tooltip");
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "global-tooltip";
      // Faded out it is still in the page: hidden from screen readers until
      // it shows (an empty, nameless tooltip; a11y audit P6).
      tip.setAttribute("aria-hidden", "true");
      document.body.appendChild(tip);
    }
    tip.id = tip.id || "appTooltip";
    tip.setAttribute("role", "tooltip");
    return tip;
  }

  function textOf(element) {
    if (element.hasAttribute("data-tooltip-overflow")) {
      const cutOff = element.scrollWidth > element.clientWidth + 1;
      return cutOff ? (element.textContent || "").replace(/\s+/g, " ").trim() : "";
    }
    const text = element.getAttribute("data-tooltip") || element.getAttribute("data-tooltip-title")
      || element.getAttribute("title") || "";
    const clean = text.replace(/\s+/g, " ").trim();
    if (!clean) return "";
    const visible = (element.textContent || "").replace(/\s+/g, " ").trim();
    return clean === visible ? "" : clean;
  }

  function findTarget(node) {
    return node?.closest?.("[data-tooltip], [title], [data-tooltip-title], [data-tooltip-overflow]") || null;
  }

  function park(element) {
    if (!element.hasAttribute("title")) return;
    element.setAttribute("data-tooltip-title", element.getAttribute("title"));
    element.removeAttribute("title");
  }

  function unpark(element) {
    if (!element?.hasAttribute("data-tooltip-title")) return;
    if (!element.hasAttribute("title")) element.setAttribute("title", element.getAttribute("data-tooltip-title"));
    element.removeAttribute("data-tooltip-title");
  }

  function place(element) {
    const box = element.getBoundingClientRect();
    const node = ensure();
    node.style.left = "0px";
    node.style.top = "0px";
    const size = node.getBoundingClientRect();
    const gap = 6;
    let top = box.bottom + gap;
    if (top + size.height > window.innerHeight - 8) top = Math.max(8, box.top - gap - size.height);
    let left = box.left + box.width / 2 - size.width / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - size.width - 8));
    node.style.left = `${Math.round(left)}px`;
    node.style.top = `${Math.round(top)}px`;
  }

  // Inside an open modal dialog the tooltip lives in that dialog: the page
  // under it is painted below the top layer.
  function host(element) {
    return element.closest("dialog[open]") || document.body;
  }

  function show(element) {
    const text = textOf(element);
    if (!text || !element.isConnected) return;
    const node = ensure();
    const parent = host(element);
    if (node.parentElement !== parent) parent.append(node);
    node.textContent = text;
    node.removeAttribute("aria-hidden");
    node.classList.add("visible");
    place(element);
    target = element;
    const described = (element.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (!described.includes(node.id)) element.setAttribute("aria-describedby", [...described, node.id].join(" "));
  }

  function hide() {
    window.clearTimeout(timer);
    window.clearTimeout(hideTimer);
    timer = 0;
    if (!target && !tip?.classList.contains("visible")) return;
    if (target) {
      const described = (target.getAttribute("aria-describedby") || "").split(/\s+/)
        .filter(id => id && id !== tip?.id);
      if (described.length) target.setAttribute("aria-describedby", described.join(" "));
      else target.removeAttribute("aria-describedby");
      unpark(target);
    }
    target = null;
    tip?.classList.remove("visible");
    tip?.setAttribute("aria-hidden", "true");
    lastHiddenAt = Date.now();
  }

  function schedule(element, wait) {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => show(element), wait);
  }

  function onPointerOver(event) {
    if (event.pointerType === "touch") return;
    const element = findTarget(event.target);
    if (!element || element === target) return;
    if (target) hide();
    park(element);
    target = element;
    schedule(element, Date.now() - lastHiddenAt < CHAIN_MS ? 0 : REST_MS);
  }

  function onPointerOut(event) {
    if (!target || event.pointerType === "touch") return;
    if (target.contains(event.relatedTarget)) return;
    hide();
  }

  function onFocusIn(event) {
    const element = findTarget(event.target);
    if (!element || element !== event.target) return;
    let keyboard = false;
    try { keyboard = element.matches(":focus-visible"); } catch (_) { keyboard = false; }
    if (!keyboard) return;
    hide();
    target = element;
    schedule(element, REST_MS);
  }

  function onPointerUp(event) {
    if (event.pointerType !== "touch") return;
    const element = findTarget(event.target);
    if (!element || event.target.closest(INTERACTIVE)) return;
    hide();
    show(element);
    hideTimer = window.setTimeout(hide, TOUCH_MS);
  }

  let bound = false;
  function init() {
    ensure();
    if (bound) return;
    bound = true;
    document.addEventListener("pointerover", onPointerOver);
    document.addEventListener("pointerout", onPointerOut);
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("focusout", event => { if (event.target === target) hide(); });
    document.addEventListener("pointerdown", event => { if (event.pointerType !== "touch") hide(); }, true);
    document.addEventListener("pointerup", onPointerUp);
    document.addEventListener("keydown", event => { if (event.key === "Escape") hide(); }, true);
    window.addEventListener("scroll", hide, true);
    window.addEventListener("blur", hide);
  }

  App.tooltip = { init, show, hide };
})();
