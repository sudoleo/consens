// =====================================================================
// i18n.js
// German for German readers: the browser half of app/core/i18n.py (the
// module docstring there has the whole story and the rules).
//
// The server sends a German page already translated and this file as the
// first script of <head>, behind the dictionary (window.__consensI18n,
// served together as /i18n/<lang>.<hash>.js). From then on a
// MutationObserver translates every word a script writes, with the
// server's rules: a run of text and inline elements is looked up whole
// (inline elements as numbered markers, moved, not rebuilt, so their
// listeners stay), else piece by piece; {name} placeholders match any
// value. Scripts keep their English words: they compare, store and send
// them as before, and only the page changes.
//
//   App.lang   "de" or "en"
//   App.t      a sentence that never reaches the DOM (confirm(), the
//              clipboard, the tab title before it is set): App.t("Copy"),
//              App.t("{n} chats", {n: 3}). English without a dictionary.
//
// Never translated: script, style, textarea, pre, code, svg, math,
// [translate="no"], .notranslate, [data-i18n-skip], editable text, and
// the content regions in SKIP_SELECTOR (answers, questions, chat titles):
// their words are the reader's or a model's, in their own language. The
// app's controls inside one ([data-i18n-ui]) are translated again.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const data = window.__consensI18n || null;
  const lang = data && data.lang ? data.lang : "en";

  const PLACEHOLDER = /\{([A-Za-z_]\w*|\d+)\}/g;
  const PLACEHOLDER_SPLIT = /\{([A-Za-z_]\w*|\d+)\}/;
  const MARKER = /<(\d+)>|<\/(\d+)>|<(\d+)\/>/g;
  const HAS_MARKER = /<\d+\/?>/;
  const LETTER = /\p{L}/u;

  function normalize(text) {
    return String(text).replace(/\s+/g, " ").trim();
  }

  function fill(text, params) {
    if (!params) return text;
    return text.replace(PLACEHOLDER, (match, name) => (Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match));
  }

  // ------------------------------------------------------------------
  // Dictionary
  // ------------------------------------------------------------------
  const exact = new Map();
  const templates = new Map();
  const patterns = [];
  const values = new Set();
  const misses = new Set();

  function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  if (data && data.entries) {
    for (const [key, value] of Object.entries(data.entries)) {
      values.add(value);
      if (!PLACEHOLDER_SPLIT.test(key)) {
        exact.set(key, value);
        continue;
      }
      const parts = key.split(PLACEHOLDER_SPLIT);
      const literals = parts.filter((_, index) => index % 2 === 0);
      const names = parts.filter((_, index) => index % 2 === 1);
      const source = literals.map((literal, index) => escapeRegExp(literal) + (index < names.length ? "([\\s\\S]+?)" : "")).join("");
      templates.set(key, value);
      patterns.push({
        regex: new RegExp("^" + source + "$"),
        names,
        value,
        hint: literals.reduce((longest, literal) => (literal.length > longest.length ? literal : longest), ""),
        weight: literals.reduce((sum, literal) => sum + literal.length, 0),
      });
    }
    patterns.sort((a, b) => b.weight - a.weight);
  }

  function lookup(text, nested = true) {
    const hit = exact.get(text);
    if (hit !== undefined) return hit;
    if (misses.has(text)) return null;
    for (const pattern of patterns) {
      if (pattern.hint && text.indexOf(pattern.hint) === -1) continue;
      const match = pattern.regex.exec(text);
      if (!match) continue;
      const captured = {};
      pattern.names.forEach((name, index) => {
        if (!Object.prototype.hasOwnProperty.call(captured, name)) captured[name] = capturedValue(match[index + 1], nested);
      });
      if (Object.values(captured).some(value => value === null)) continue;
      return fill(pattern.value, captured);
    }
    if (nested) {
      if (misses.size > 5000) misses.clear();
      misses.add(text);
    }
    return null;
  }

  // Words no name is made of (app/core/i18n.py, GLUE_WORDS).
  const GLUE_WORDS = new Set([
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it",
    "not", "of", "on", "or", "than", "that", "the", "there", "this", "to", "was", "were", "with", "your",
  ]);

  // Every marker the text opens it also closes, in order: no half element
  // (app/core/i18n.py, whole_elements).
  function wholeElements(text) {
    const opened = [];
    for (const match of text.matchAll(MARKER)) {
      if (match[1] !== undefined) opened.push(match[1]);
      else if (match[2] !== undefined && (!opened.length || opened.pop() !== match[2])) return false;
    }
    return !opened.length;
  }

  // A value a pattern caught, translated when it has an entry of its own:
  // one level deep, the space around it kept (app/core/i18n.py, _captured).
  // English prose without an entry is no value (null): the pattern does not
  // apply, rather than leaving half a sentence English. Nor is half an
  // element: "{answered} of {length}" must not take a line of spans.
  function capturedValue(value, nested) {
    if (!wholeElements(value)) return null;
    const key = normalize(value);
    if (!key || !LETTER.test(key)) return value;
    let found = exact.get(key);
    if (found === undefined && nested) found = lookup(key, false);
    if (found === undefined || found === null) {
      return (key.toLowerCase().match(/[a-z]+/g) || []).some(word => GLUE_WORDS.has(word)) ? null : value;
    }
    const [lead, trail] = edges(value);
    return lead + found + trail;
  }

  // "ctx|key" entries win where an element names its data-i18n-context
  // ("agent freedom|Free" is not the plan Free).
  function find(key, context) {
    if (context) {
      const hit = exact.get(context + "|" + key);
      if (hit !== undefined) return hit;
    }
    return lookup(key);
  }

  App.lang = lang;
  // A context entry wins, a pattern too ("watch schedule|In {city} time"):
  // an open pattern lives only there (app/core/i18n.py, t).
  App.t = function (text, params, context) {
    const key = normalize(text);
    let found;
    if (context) {
      found = exact.get(context + "|" + key);
      if (found === undefined) found = templates.get(context + "|" + key);
    }
    if (found === undefined) found = exact.get(key);
    if (found === undefined) found = templates.get(key);
    if (found === undefined) found = lookup(key);
    return fill(found !== null && found !== undefined ? found : String(text), params);
  };

  if (!data || !data.entries || lang === "en") return;

  // ------------------------------------------------------------------
  // Elements
  // ------------------------------------------------------------------
  const PHRASING = new Set([
    "a", "abbr", "b", "bdi", "bdo", "cite", "data", "del", "dfn", "em", "font", "i", "ins",
    "mark", "q", "s", "small", "span", "strong", "sub", "sup", "time", "u",
  ]);
  const OPAQUE = new Set([
    "br", "wbr", "img", "svg", "math", "code", "kbd", "samp", "var", "input",
    "picture", "video", "audio", "canvas", "iframe", "object", "output", "meter", "progress",
  ]);
  const SKIP = new Set(["script", "style", "textarea", "pre", "svg", "math", "noscript", "code", "kbd", "samp", "var"]);
  const TEXT_ATTRIBUTES = [
    "title", "aria-label", "aria-description", "aria-placeholder", "aria-roledescription",
    "aria-valuetext", "placeholder", "alt", "label", "data-tooltip", "data-short", "data-label",
    "data-ghost", "data-compact", "data-description", "data-type-loop", "data-type-text",
    "data-placeholder", "data-drop-label", "data-show", "data-hide",
  ];
  // Words that belong to the reader or a model: never looked up. The
  // markup's own marks (translate="no", data-i18n-skip) cover the rest.
  // Rendered Markdown marks itself (markdown-stream.js).
  const CONTENT_REGIONS = [
    ".bookmark > p", ".thread-ask-text", ".watch-question-preview",
  ];
  const SKIP_SELECTOR = [
    "script", "style", "textarea", "pre", "svg", "math", "noscript", "code", "kbd", "samp", "var",
    '[translate="no" i]', ".notranslate", "[data-i18n-skip]",
    '[contenteditable=""]', '[contenteditable="true" i]', '[contenteditable="plaintext-only" i]',
  ].concat(CONTENT_REGIONS).join(",");

  function skipped(element) {
    if (SKIP.has(element.localName)) return true;
    return element.matches(SKIP_SELECTOR);
  }

  // The app's own controls inside a content region (a picture the agent
  // placed in its answer, agent-workspace.js) mark themselves
  // [data-i18n-ui]: from there down to the next skipped element, words are
  // ours again.
  const UI_SELECTOR = "[data-i18n-ui]";

  function inSkipped(element) {
    const skip = element && element.closest ? element.closest(SKIP_SELECTOR) : null;
    if (!skip) return false;
    const ui = element.closest(UI_SELECTOR);
    return !(ui && ui !== skip && skip.contains(ui));
  }

  function contextOf(node) {
    const element = node && (node.nodeType === 1 ? node : node.parentElement);
    const holder = element && element.closest ? element.closest("[data-i18n-context]") : null;
    return holder ? holder.getAttribute("data-i18n-context") : "";
  }

  function hasWords(node) {
    if (node.nodeType === 3) return LETTER.test(node.data);
    if (node.nodeType !== 1) return false;
    for (const child of node.childNodes) {
      if (child.nodeType === 1 && kind(child) === "opaque") continue;
      if (hasWords(child)) return true;
    }
    return false;
  }

  // "phrasing" (words of the sentence), "opaque" (a marker) or "block".
  function kind(element) {
    const tag = element.localName;
    if (OPAQUE.has(tag)) return "opaque";
    if (!PHRASING.has(tag)) return "block";
    if (skipped(element)) return "opaque";
    for (const child of element.childNodes) {
      if (child.nodeType === 8) return "block";
      if (child.nodeType === 1 && kind(child) === "block") return "block";
    }
    return hasWords(element) ? "phrasing" : "opaque";
  }

  function words(node) {
    if (node.nodeType === 3) return node.data.trim() !== "";
    return node.nodeType === 1 && kind(node) === "phrasing";
  }

  function edges(text) {
    const lead = text.match(/^\s*/)[0];
    const trail = text.length > lead.length ? text.match(/\s*$/)[0] : "";
    return [lead, trail];
  }

  // What this file wrote, so a later change of the same container does
  // not translate German a second time.
  const ours = new WeakMap();
  const oursAttr = new WeakMap();

  function isOurs(node) {
    return ours.get(node) === node.data;
  }

  function remember(node) {
    ours.set(node, node.data);
  }

  function runKey(nodes) {
    const parts = [];
    const elements = [];
    let fresh = false;
    function visit(node) {
      if (node.nodeType === 3) {
        parts.push(node.data);
        if (node.data.trim() && !isOurs(node)) fresh = true;
      } else if (node.nodeType === 1 && kind(node) === "phrasing") {
        const index = elements.length;
        elements.push(node);
        parts.push("<" + index + ">");
        node.childNodes.forEach(visit);
        parts.push("</" + index + ">");
      } else if (node.nodeType === 1) {
        const index = elements.length;
        elements.push(node);
        parts.push("<" + index + "/>");
      }
    }
    nodes.forEach(visit);
    return { key: normalize(parts.join("")), elements, fresh };
  }

  function build(value, elements) {
    const root = document.createDocumentFragment();
    const stack = [root];
    let position = 0;
    function text(chunk) {
      if (!chunk) return;
      const node = document.createTextNode(chunk);
      remember(node);
      stack[stack.length - 1].appendChild(node);
    }
    MARKER.lastIndex = 0;
    let match;
    while ((match = MARKER.exec(value))) {
      text(value.slice(position, match.index));
      position = match.index + match[0].length;
      if (match[1] !== undefined) {
        const element = elements[Number(match[1])];
        while (element.firstChild) element.removeChild(element.firstChild);
        stack[stack.length - 1].appendChild(element);
        stack.push(element);
      } else if (match[2] !== undefined) {
        stack.pop();
      } else {
        stack[stack.length - 1].appendChild(elements[Number(match[3])]);
      }
    }
    text(value.slice(position));
    return root;
  }

  function replaceRun(parent, core, value, elements) {
    if (core.length === 1 && core[0].nodeType === 3 && !HAS_MARKER.test(value)) {
      // One text node: changed in place, so a script holding it keeps
      // writing to the page.
      const node = core[0];
      const [lead, trail] = edges(node.data);
      node.data = lead + value + trail;
      remember(node);
      return;
    }
    const first = core[0];
    const last = core[core.length - 1];
    const lead = first.nodeType === 3 ? edges(first.data)[0] : "";
    const trail = last.nodeType === 3 ? edges(last.data)[1] : "";
    const anchor = last.nextSibling;
    const fragment = build(value, elements);
    if (lead) {
      const node = document.createTextNode(lead);
      remember(node);
      fragment.insertBefore(node, fragment.firstChild);
    }
    if (trail) {
      const node = document.createTextNode(trail);
      remember(node);
      fragment.appendChild(node);
    }
    for (const node of core) {
      if (node.parentNode === parent && !elements.includes(node)) parent.removeChild(node);
    }
    parent.insertBefore(fragment, anchor && anchor.parentNode === parent ? anchor : null);
  }

  function translateText(node) {
    if (isOurs(node)) return;
    const key = normalize(node.data);
    if (!key || !LETTER.test(key) || values.has(key)) return;
    const found = find(key, contextOf(node));
    if (found === null || HAS_MARKER.test(found)) return;
    const [lead, trail] = edges(node.data);
    node.data = lead + found + trail;
    remember(node);
  }

  function translateRun(parent, nodes) {
    for (const node of nodes) {
      if (node.nodeType === 1 && kind(node) !== "block" && !skipped(node)) translateAttributes(node, true);
    }
    let start = 0;
    let end = nodes.length;
    while (start < end && !words(nodes[start])) start += 1;
    while (end > start && !words(nodes[end - 1])) end -= 1;
    if (start === end) return;
    const core = nodes.slice(start, end);
    if (core.length === 1 && core[0].nodeType === 1) {
      translateRun(core[0], Array.from(core[0].childNodes));
      return;
    }
    const { key, elements, fresh } = runKey(core);
    if (!fresh || !LETTER.test(key)) return;
    // The text itself types a marker ("<0/>" in a file name): no entry can
    // say which element it means; its pieces still translate
    // (app/core/i18n.py, _Translator.run).
    const expected = elements.reduce((sum, element) => sum + (kind(element) === "phrasing" ? 2 : 1), 0);
    const typed = (key.match(MARKER) || []).length !== expected;
    const found = typed || (values.has(key) && !exact.has(key)) ? null : find(key, contextOf(parent));
    if (found !== null) {
      replaceRun(parent, core, found, elements);
      return;
    }
    if (values.has(key)) return;
    for (const node of core) {
      if (node.nodeType === 3) translateText(node);
      else if (node.nodeType === 1 && kind(node) === "phrasing") translateRun(node, Array.from(node.childNodes));
    }
  }

  function translateAttribute(element, name) {
    const value = element.getAttribute(name);
    if (!value || !value.trim()) return;
    let mine = oursAttr.get(element);
    if (mine && mine[name] === value) return;
    let found = null;
    if (name === "value") {
      if (element.localName !== "input" || !/^(submit|button|reset)$/i.test(element.type || "")) return;
    } else if (TEXT_ATTRIBUTES.indexOf(name) === -1) {
      return;
    }
    const key = normalize(value);
    if (!LETTER.test(key) || values.has(key)) return;
    found = find(key, contextOf(element));
    if (found === null) return;
    if (!mine) {
      mine = {};
      oursAttr.set(element, mine);
    }
    mine[name] = found;
    element.setAttribute(name, found);
  }

  function translateAttributes(element) {
    for (const name of TEXT_ATTRIBUTES) {
      if (element.hasAttribute(name)) translateAttribute(element, name);
    }
    if (element.localName === "input" && element.hasAttribute("value")) translateAttribute(element, "value");
  }

  // A field's text is the reader's; its placeholder and label are ours.
  const MARKED_SELECTOR = '[translate="no" i], .notranslate, [data-i18n-skip]';

  function fieldAttributesAllowed(element) {
    return element.localName === "textarea" && !element.closest(MARKED_SELECTOR) && !inSkipped(element.parentElement);
  }

  function translateContainer(element, deep) {
    if (skipped(element)) {
      if (fieldAttributesAllowed(element)) translateAttributes(element);
      return;
    }
    translateAttributes(element);
    let run = [];
    const flush = () => {
      if (run.length) translateRun(element, run);
      run = [];
    };
    for (const child of Array.from(element.childNodes)) {
      const type = child.nodeType;
      if (type === 3 || (type === 1 && kind(child) !== "block")) {
        run.push(child);
        continue;
      }
      flush();
      if (deep && type === 1) translateContainer(child, true);
    }
    flush();
  }

  function blockOf(node) {
    let element = node.nodeType === 1 ? node : node.parentElement;
    while (element && element.parentElement && (PHRASING.has(element.localName) || OPAQUE.has(element.localName))) {
      element = element.parentElement;
    }
    return element;
  }

  // ------------------------------------------------------------------
  // Observer
  // ------------------------------------------------------------------
  const observer = new MutationObserver(handle);

  function handle(records) {
    const shallow = new Set();
    const deep = new Set();
    for (const record of records) {
      if (record.type === "attributes") {
        const element = record.target;
        if (!inSkipped(element) || fieldAttributesAllowed(element)) translateAttribute(element, record.attributeName);
        continue;
      }
      if (record.type === "characterData") {
        const block = blockOf(record.target);
        if (block) shallow.add(block);
        continue;
      }
      let changed = record.removedNodes.length > 0;
      for (const node of record.addedNodes) {
        if (node.nodeType === 1 && kind(node) === "block") deep.add(node);
        else changed = true;
      }
      if (changed) {
        const block = blockOf(record.target);
        if (block) shallow.add(block);
      }
    }
    for (const element of deep) {
      if (element.isConnected && !skipped(element) && (element.matches(UI_SELECTOR) || !inSkipped(element.parentElement))) {
        translateContainer(element, true);
      }
    }
    for (const element of shallow) {
      if (element.isConnected && !inSkipped(element)) translateContainer(element, false);
    }
    observer.takeRecords();
  }

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: TEXT_ATTRIBUTES.concat(["value"]),
  });

  App.i18n = {
    lookup(text) {
      return lookup(normalize(text));
    },
    // Translates a detached tree now (a tooltip measured before it is attached).
    translate(element) {
      if (element && element.nodeType === 1) translateContainer(element, true);
      return element;
    },
    flush() {
      handle(observer.takeRecords());
    },
  };
})();
