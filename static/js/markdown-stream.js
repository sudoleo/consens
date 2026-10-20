// =====================================================================
// markdown-stream.js
// Markdown-Rendering (sanitised) + SSE-Streaming-Helfer.
// Extrahiert aus templates/index.html (initApp-Closure).
// Exporte: window.injectMarkdown, window.morphMarkdown,
// window.isPlainMarkdown, window.keepTextSelection,
// window.renderMarkdownStream, window.resetMarkdownStream,
// window.createStreamRenderer, window.streamSSERequest.
// (readSSEStream bleibt modul-privat.)
// Call-time-Abhaengigkeiten: DOMPurify, marked (CDN), window.ConsensusMath,
// window.addCopyButtons, window.addNewTabToLinks, window.linkifySourceTags,
// window.currentEvidenceSources.
// =====================================================================

function reportMarkdownFallback(missingDependency) {
  window.App?.reportCriticalError?.({
    type: "dependency_unavailable",
    phase: "markdown_render",
    message: "Markdown renderer unavailable; displaying unformatted text.",
    details: missingDependency
  });
}

// Model output is untrusted: an injected instruction (web page, file, mail,
// calendar event) could make the model emit markup that loads a remote URL
// with private data in it the moment the answer renders. Nothing in a model
// answer may therefore trigger a request on its own: no remote images, media,
// <style> blocks or CSS with url()/functions. Links still need a click.
const MODEL_HTML_CONFIG = {
  FORBID_TAGS: ["style", "video", "audio", "source", "picture", "track", "form", "input", "link", "meta"],
  FORBID_ATTR: ["srcset", "poster", "background", "ping"]
};

function isInlineImageSource(src) {
  return /^data:image\//i.test(src) || (src.startsWith("/") && !src.startsWith("//"));
}

// Runs while the nodes still belong to DOMPurify's inert document: an <img>
// starts loading as soon as it is adopted into the page, even detached.
function neutralizeRemoteMedia(root) {
  const doc = root.ownerDocument || document;
  root.querySelectorAll("img").forEach(img => {
    const src = (img.getAttribute("src") || "").trim();
    if (isInlineImageSource(src)) return;
    const note = doc.createElement("span");
    note.className = "blocked-remote-image";
    const alt = (img.getAttribute("alt") || "").trim();
    note.textContent = alt ? `[Image not loaded: ${alt}]` : "[External image not loaded]";
    img.replaceWith(note);
  });
  root.querySelectorAll("[style]").forEach(el => {
    if (/[()\\]|url|image|@import|expression/i.test(el.getAttribute("style") || "")) {
      el.removeAttribute("style");
    }
  });
}

function plainTextFragment(text) {
  const fragment = document.createDocumentFragment();
  if (text) fragment.append(document.createTextNode(text));
  return fragment;
}

// Markdown -> sanitized nodes of this document, parsed once: DOMPurify hands
// over its own DOM instead of a string that would be parsed again for the
// media check and once more for the page (Apple audit D4).
function renderMarkdownFragment(md) {
  const prepared = window.ConsensusMath
    ? window.ConsensusMath.prepareMarkdown(md)
    : (md || "");
  const missing = [
    typeof window.marked?.parse !== "function" ? "marked" : "",
    typeof window.DOMPurify?.sanitize !== "function" ? "DOMPurify" : ""
  ].filter(Boolean);
  if (missing.length) {
    // A CDN or local-network failure must not turn a usable model answer into
    // an unhandled Promise rejection. Plain text is safe and keeps the run
    // readable until the dependency is available again.
    reportMarkdownFallback(missing.join(", "));
    return plainTextFragment(prepared);
  }
  try {
    let fragment = window.DOMPurify.sanitize(window.marked.parse(prepared),
      { ...MODEL_HTML_CONFIG, RETURN_DOM_FRAGMENT: true });
    if (typeof fragment === "string") {
      // A sanitizer that only returns markup: an inert template parses it.
      const template = document.createElement("template");
      template.innerHTML = fragment;
      fragment = template.content;
    }
    neutralizeRemoteMedia(fragment);
    return fragment.ownerDocument === document ? fragment : document.adoptNode(fragment);
  } catch (error) {
    reportMarkdownFallback("render error");
    return plainTextFragment(prepared);
  }
}

function isNumericTableValue(value) {
  const normalized = String(value || "")
    .replace(/\u00a0/g, " ")
    .trim();
  if (!normalized) return false;
  return /^\(?[+-]?\s*(?:[$€£¥]\s*)?(?:\d{1,3}(?:[.,\s]\d{3})+|\d+)(?:[.,]\d+)?(?:\s*%)?\)?$/.test(normalized);
}

function markNumericTableColumns(table) {
  const rows = Array.from(table.tBodies || [])
    .flatMap(body => Array.from(body.rows || []));
  if (!rows.length) return;

  const columnCount = Math.max(...rows.map(row => row.cells.length), 0);
  for (let column = 0; column < columnCount; column += 1) {
    const cells = rows
      .map(row => row.cells[column])
      .filter(Boolean);
    const numericCount = cells.filter(cell => isNumericTableValue(cell.textContent)).length;
    // Allow one label row such as "Total" in an otherwise numeric column.
    if (numericCount < Math.max(2, cells.length - 1)) continue;

    Array.from(table.rows || []).forEach(row => {
      const cell = row.cells[column];
      if (cell && (cell.closest("thead") || isNumericTableValue(cell.textContent))) {
        cell.classList.add("is-numeric");
      }
    });
  }
}

function enhanceMarkdownTables(root) {
  const tables = Array.from(root?.querySelectorAll?.("table") || []);
  tables.forEach((table, index) => {
    if (table.closest(".markdown-table-wrap")) return;

    table.classList.add("markdown-table");
    markNumericTableColumns(table);

    const headings = Array.from(table.querySelectorAll("thead th"))
      .map(cell => cell.textContent.trim())
      .filter(Boolean)
      .slice(0, 3);
    const wrapper = document.createElement("div");
    wrapper.className = "markdown-table-wrap";
    wrapper.setAttribute("role", "region");
    wrapper.setAttribute(
      "aria-label",
      headings.length ? `Table: ${headings.join(", ")}` : `Table ${index + 1}`
    );
    wrapper.tabIndex = 0;

    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });
}

// Utils: Markdown → HTML (sanitised) + deine Addons
function injectMarkdown(el, md, evidenceSources = window.currentEvidenceSources) {
  el.replaceChildren(renderMarkdownFragment(md));

  enhanceMarkdownTables(el);

  if (window.addCopyButtons) window.addCopyButtons(el);
  if (window.addNewTabToLinks) window.addNewTabToLinks(el);

  const linked = Array.isArray(evidenceSources) && evidenceSources.length && window.linkifySourceTags;
  if (linked) window.linkifySourceTags(el, evidenceSources);

  if (window.ConsensusMath) window.ConsensusMath.render(el);
  noteMarkdownWrite(el, linked ? null : md);
}

// Every write of rendered Markdown into `el` counts up `el._markdownWrites`:
// renderers that decorate the text (claim marks) tell from it whether their
// decoration is still there. A morphed render keeps the first node, so the
// node itself no longer says that the text was written again.
function noteMarkdownWrite(el, plainMd) {
  el._markdownWrites = (el._markdownWrites || 0) + 1;
  // What a plain render of `md` left in `el`: the review renderer can mark
  // it as it is instead of rendering the same text again (isPlainMarkdown).
  el._plainMarkdown = typeof plainMd === "string"
    ? { md: plainMd, writes: el._markdownWrites, first: el.firstChild, last: el.lastChild, count: el.childNodes.length }
    : null;
}

// True while `el` still holds exactly what injectMarkdown(el, md, []) wrote:
// no other write since and nothing marked or turned into pills.
function isPlainMarkdown(el, md) {
  const plain = el?._plainMarkdown;
  return Boolean(plain) && plain.md === md && plain.writes === el._markdownWrites
    && el.firstChild === plain.first && el.lastChild === plain.last
    && el.childNodes.length === plain.count && !el.querySelector(".cx-claim, .claim-badge, .src-ref");
}

// --- Morphing a shown answer into its next render -----------------------
// Replacing the nodes of an answer the reader is in dropped their selection,
// the link under their finger and the hover of a source pill. A morph keeps
// every node whose kind did not change: text that only grows is appended to
// (a selection inside it stays), elements keep their identity and take the
// new render's attributes. Nodes of another kind are taken from the new
// render as they are, so the result equals it node for node.
const CARRIED_PROPERTIES = ["sourceData", "sourceGroup"];
// Claim marks carry their own listeners and state: they never become another
// element, the new render's node takes their place.
const MARK_NODES = ".cx-claim, .cx-spot, .claim-badge";

function sameNodeKind(live, next) {
  if (live.nodeType !== next.nodeType) return false;
  if (live.nodeType !== Node.ELEMENT_NODE) return true;
  return live.tagName === next.tagName && live.namespaceURI === next.namespaceURI
    && !live.matches(MARK_NODES) && !next.matches(MARK_NODES);
}

function morphNode(live, next) {
  if (live.nodeType !== Node.ELEMENT_NODE) {
    const before = live.nodeValue || "";
    const after = next.nodeValue || "";
    if (before === after) return;
    if (live.nodeType === Node.TEXT_NODE && after.startsWith(before)) live.appendData(after.slice(before.length));
    else live.nodeValue = after;
    return;
  }
  for (const attribute of Array.from(live.attributes)) {
    if (!next.hasAttribute(attribute.name)) live.removeAttribute(attribute.name);
  }
  for (const attribute of Array.from(next.attributes)) {
    if (live.getAttribute(attribute.name) !== attribute.value) live.setAttribute(attribute.name, attribute.value);
  }
  for (const key of CARRIED_PROPERTIES) {
    if (key in next || key in live) live[key] = next[key];
  }
  morphNodes(live, Array.from(live.childNodes), Array.from(next.childNodes));
}

// Turns the run of `current` nodes in `parent` into `wanted` and returns the
// nodes that stand there afterwards.
function morphNodes(parent, current, wanted) {
  const end = current.length ? current[current.length - 1].nextSibling : null;
  const result = [];
  let index = 0;
  for (const next of wanted) {
    const live = current[index];
    if (live && sameNodeKind(live, next)) {
      morphNode(live, next);
      result.push(live);
      index += 1;
    } else {
      parent.insertBefore(next, live || end);
      result.push(next);
    }
  }
  for (; index < current.length; index += 1) current[index].remove();
  return result;
}

// Renders `md` in full like injectMarkdown(el, md, []), but into the nodes
// `el` already shows. `decorate` gives the render its final inline form
// before it is compared (source pills), as for streamed blocks.
function morphMarkdown(el, md, { decorate } = {}) {
  const next = document.createElement("div");
  injectMarkdown(next, md, []);
  decorate?.(next);
  morphNodes(el, Array.from(el.childNodes), Array.from(next.childNodes));
  delete el._markdownStream;
  noteMarkdownWrite(el, decorate ? null : md);
}

// --- A selection that outlives a re-render ------------------------------
// The reader's selection inside `root`, kept across `change` as positions in
// its prose. Claim badges and source pills are drawn on top of the text and
// may come and go with the change, so their text does not count.
const SELECTION_SKIP = ".claim-badge, .src-ref, .src-ref-sep";

function proseNodes(root) {
  const nodes = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.parentElement?.closest(SELECTION_SKIP)) nodes.push(node);
  }
  return nodes;
}

function proseOffset(root, container, offset) {
  const range = document.createRange();
  range.setStart(root, 0);
  range.setEnd(container, offset);
  let total = 0;
  for (const node of proseNodes(root)) {
    if (!range.intersectsNode(node)) continue;
    total += node === range.endContainer ? range.endOffset : node.length;
  }
  return total;
}

function prosePoint(offset, nodes) {
  let total = 0;
  for (const node of nodes) {
    if (offset <= total + node.length) return [node, Math.max(0, offset - total)];
    total += node.length;
  }
  const last = nodes[nodes.length - 1];
  return last ? [last, last.length] : null;
}

function keepTextSelection(root, change) {
  // Nothing in it, nothing selected in it: asking the selection forced a
  // style pass inside the click on Send for the new, empty answer (D3).
  if (!root?.firstChild) return change();
  const selection = typeof window.getSelection === "function" ? window.getSelection() : null;
  const inside = node => Boolean(node) && root.contains(node);
  if (!root || !selection || !selection.rangeCount || selection.isCollapsed
      || !inside(selection.anchorNode) || !inside(selection.focusNode)) return change();
  const anchor = proseOffset(root, selection.anchorNode, selection.anchorOffset);
  const focus = proseOffset(root, selection.focusNode, selection.focusOffset);
  const result = change();
  try {
    const kept = inside(selection.anchorNode) && inside(selection.focusNode)
      && proseOffset(root, selection.anchorNode, selection.anchorOffset) === anchor
      && proseOffset(root, selection.focusNode, selection.focusOffset) === focus;
    if (!kept) {
      const nodes = proseNodes(root);
      const from = prosePoint(anchor, nodes);
      const to = prosePoint(focus, nodes);
      if (from && to) selection.setBaseAndExtent(from[0], from[1], to[0], to[1]);
    }
  } catch (_) { /* A selection the browser refuses stays as it is. */ }
  return result;
}

window.injectMarkdown = injectMarkdown;
window.isPlainMarkdown = isPlainMarkdown;
window.morphMarkdown = morphMarkdown;
window.keepTextSelection = keepTextSelection;

// --- Incremental Markdown for a growing answer -------------------------
// Re-parsing the whole answer on every streamed chunk makes the total work
// quadratic in its length. A streamed answer only ever grows at its end, so
// the text is cut into top-level blocks at blank lines outside code fences
// and display math. Finished blocks are parsed exactly once; only the last,
// still growing block is rendered again, and morphed into the nodes shown
// for it: a link in the paragraph that is being written stays clickable and
// a selection in it stays. A block boundary is committed only once the line
// after the blank line is complete, so a list or paragraph that continues
// across a blank line is never split early. Loose lists and indented
// continuations stay in one block. The caller renders the complete text once
// (morphMarkdown) when it is fixed, so constructs that span blocks
// (reference links, footnotes) are exact in the final answer.
const LIST_OR_INDENT = /^(?:\s|[-*+]\s|\d{1,9}[.)]\s|>)/;
const FENCE_LINE = /^\s{0,3}(```|~~~)/;

function nextStreamBlockEnd(text, from) {
  let fence = "";
  let math = false;
  let position = from;
  let sawContent = false;
  while (position < text.length) {
    const newline = text.indexOf("\n", position);
    if (newline === -1) return -1;
    const line = text.slice(position, newline);
    const fenceMatch = line.match(FENCE_LINE);
    if (fence) {
      if (fenceMatch && fenceMatch[1] === fence) fence = "";
    } else if (math) {
      if (line.trim().endsWith("$$")) math = false;
    } else if (fenceMatch) {
      fence = fenceMatch[1];
    } else if (line.trim().startsWith("$$") && !(line.trim().length > 2 && line.trim().endsWith("$$"))) {
      math = true;
    } else if (!line.trim() && sawContent) {
      // Blank line: a boundary only when the next line is complete and starts
      // a new top-level block rather than continuing a list or quote.
      let next = newline + 1;
      while (next < text.length && text[next] === "\n") next += 1;
      const nextEnd = text.indexOf("\n", next);
      if (nextEnd === -1) return -1;
      if (!LIST_OR_INDENT.test(text.slice(next, nextEnd))) return next;
    }
    if (line.trim()) sawContent = true;
    position = newline + 1;
  }
  return -1;
}

// `decorate` gives a block its final inline form before it is shown (for
// example source pills): changing it afterwards re-wrapped lines under the eye.
function renderStreamFragment(md, decorate) {
  const holder = document.createElement("div");
  holder.append(renderMarkdownFragment(md));
  enhanceMarkdownTables(holder);
  if (window.ConsensusMath) window.ConsensusMath.render(holder);
  decorate?.(holder);
  return Array.from(holder.childNodes);
}

// A bold span the stream has opened but not closed yet would show its raw
// asterisks until the closing pair arrives. The unfinished tail is rendered
// as if it were closed; the final render shows the real text.
function closeOpenStrong(text) {
  if (/(^|\n)\s{0,3}(```|~~~)/.test(text)) return text;
  const marks = (text.replace(/`[^`\n]*`/g, "").match(/\*\*/g) || []).length;
  if (marks % 2 === 0) return text;
  const trimmed = text.replace(/\s+$/, "");
  if (trimmed.endsWith("**")) return trimmed.slice(0, -2);
  return `${trimmed}**${text.slice(trimmed.length)}`;
}

// A table that is still streaming stands as quiet rows in its place until it
// is complete, then appears at once. Each new row changed the automatic
// column widths, so the header the reader was on slid sideways, by up to 4 cm
// for the first data row (Apple audit A5).
const TABLE_ROW = /^\s{0,3}\|/;
const TABLE_RULE = /^\s{0,3}\|?\s*:?-+:?\s*(?:\|\s*:?-*:?\s*)*\|?\s*$/;

function pendingTableStart(text) {
  let fence = "";
  let position = 0;
  while (position < text.length) {
    const newline = text.indexOf("\n", position);
    const line = text.slice(position, newline === -1 ? text.length : newline);
    const fenceMatch = line.match(FENCE_LINE);
    if (fence) {
      if (fenceMatch && fenceMatch[1] === fence) fence = "";
    } else if (fenceMatch) {
      fence = fenceMatch[1];
    } else if (TABLE_ROW.test(line)) {
      return position;
    }
    if (newline === -1) break;
    position = newline + 1;
  }
  return -1;
}

function pendingTable(rows) {
  const box = document.createElement("div");
  box.className = "stream-table-pending";
  box.setAttribute("aria-hidden", "true");
  for (let row = 0; row < Math.max(1, rows); row += 1) {
    const bar = document.createElement("span");
    bar.className = "skeleton";
    box.append(bar);
  }
  return box;
}

function renderStreamTail(text, decorate) {
  const table = pendingTableStart(text);
  if (table === -1) return renderStreamFragment(closeOpenStrong(text), decorate);
  const before = text.slice(0, table);
  const nodes = before.trim() ? renderStreamFragment(closeOpenStrong(before), decorate) : [];
  const rows = text.slice(table).split("\n").filter(line => TABLE_ROW.test(line) && !TABLE_RULE.test(line)).length;
  nodes.push(pendingTable(rows));
  return nodes;
}

// Renders `md` into `el`, reusing the blocks of the previous call when `md`
// only grew. Returns the number of characters that were parsed.
function renderMarkdownStream(el, md, { decorate } = {}) {
  md = String(md || "");
  let state = el._markdownStream;
  // Anyone else writing into the element (a full render, a review re-render)
  // invalidates the reuse; so does text that did not only grow.
  if (!state || !md.startsWith(state.committedText) || el.childNodes.length !== state.nodeCount) {
    el.replaceChildren();
    state = el._markdownStream = { committedText: "", committed: 0, tail: [], tailText: "", nodeCount: 0 };
  }
  let parsed = 0;
  let end;
  while ((end = nextStreamBlockEnd(md, state.committed)) !== -1) {
    const block = md.slice(state.committed, end);
    // The block the reader saw growing becomes final in its own nodes.
    morphNodes(el, state.tail, renderStreamFragment(block, decorate));
    state.tail = [];
    parsed += block.length;
    state.committed = end;
    state.committedText = md.slice(0, end);
  }
  const tailText = md.slice(state.committed);
  if (tailText !== state.tailText) {
    state.tail = morphNodes(el, state.tail, tailText.trim() ? renderStreamTail(tailText, decorate) : []);
    state.tailText = tailText;
    parsed += tailText.length;
  }
  if (parsed) {
    el._markdownWrites = (el._markdownWrites || 0) + 1;
    el._plainMarkdown = null;
  }
  state.nodeCount = el.childNodes.length;
  return parsed;
}

// Drop the incremental state so the next render starts from scratch.
function resetMarkdownStream(el) {
  if (!el) return;
  delete el._markdownStream;
}

window.renderMarkdownStream = renderMarkdownStream;
window.resetMarkdownStream = resetMarkdownStream;

// === Streaming (SSE) Helpers ===
function coerceStreamText(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(coerceStreamText).join("");
  if (value && typeof value === "object") {
    for (const key of ["text", "output_text", "content", "delta"]) {
      const text = coerceStreamText(value[key]);
      if (text) return text;
    }
  }
  return "";
}

// Rendert eintreffende Text-Deltas gedrosselt als Markdown in ein Element.
function createStreamRenderer(outputEl, isActiveFn) {
  const RENDER_INTERVAL_MS = 120;
  let text = "";
  let renderTimer = null;
  let lastRenderAt = 0;
  let started = false;

  function render() {
    renderTimer = null;
    if (isActiveFn && !isActiveFn()) return;
    lastRenderAt = Date.now();
    outputEl.replaceChildren(renderMarkdownFragment(text));
    enhanceMarkdownTables(outputEl);
    if (window.ConsensusMath) window.ConsensusMath.render(outputEl);
  }

  return {
    append(chunk) {
      chunk = coerceStreamText(chunk);
      if (!chunk) return;
      if (isActiveFn && !isActiveFn()) return;
      if (!started) {
        started = true;
        outputEl.classList.add("is-streaming");
      }
      text += chunk;
      const elapsed = Date.now() - lastRenderAt;
      if (elapsed >= RENDER_INTERVAL_MS) {
        if (renderTimer) clearTimeout(renderTimer);
        render();
      } else if (!renderTimer) {
        renderTimer = setTimeout(render, RENDER_INTERVAL_MS - elapsed);
      }
    },
    // Reasoning-Modelle: solange noch kein Antworttext eintrifft, den
    // "Typing"-Indikator auf "Reasoning" umstellen, damit sichtbar ist,
    // dass das Modell arbeitet (statt scheinbar zu haengen).
    markReasoning() {
      if (started) return;
      if (isActiveFn && !isActiveFn()) return;
      const label = outputEl.querySelector(".thinking.typing-indicator");
      if (!label || label.dataset.text === "Reasoning") return;
      label.dataset.text = "Reasoning";
      label.setAttribute("aria-label", "Reasoning");
      if (label.firstChild && label.firstChild.nodeType === Node.TEXT_NODE) {
        label.firstChild.nodeValue = "Reasoning";
      }
    },
    stop() {
      if (renderTimer) {
        clearTimeout(renderTimer);
        renderTimer = null;
      }
      outputEl.classList.remove("is-streaming");
    }
  };
}
window.createStreamRenderer = createStreamRenderer;

async function readSSEStream(response, onEvent, onProgress) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let skipLF = false;

  // SSE permits LF, CRLF and CR, including CRLF split across byte chunks.
  function normalizeLines(text) {
    let normalized = "";
    for (const char of text) {
      if (skipLF && char === "\n") { skipLF = false; continue; }
      skipLF = char === "\r";
      normalized += skipLF ? "\n" : char;
    }
    return normalized;
  }

  // Comment frames (": keepalive", the server's 2 KiB padding) carry no
  // data and are dropped here. `id:` (the Agent's per-run sequence number)
  // is passed on as the third argument.
  function dispatch(rawEvent) {
    let eventName = "message";
    let eventId;
    const dataLines = [];
    rawEvent.split("\n").forEach(line => {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("id:")) {
        eventId = line.slice(3).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^\s/, ""));
      }
    });
    if (!dataLines.length) return;
    let parsed;
    try {
      parsed = JSON.parse(dataLines.join("\n"));
    } catch (_) {
      return;
    }
    return onEvent(eventName, parsed, eventId);
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      onProgress?.();
      buffer += normalizeLines(decoder.decode(value, { stream: true }));
      let separatorIndex;
      while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, separatorIndex);
        buffer = buffer.slice(separatorIndex + 2);
        // The application final/error frame is authoritative. Waiting for EOF
        // can turn an already completed response into a later network failure.
        if (dispatch(rawEvent) === true) return;
      }
    }
    buffer += normalizeLines(decoder.decode());
    if (buffer.trim()) dispatch(buffer);
  } finally {
    // Do not let a stalled/rejected transport cleanup replace the result.
    try { Promise.resolve(reader.cancel?.()).catch(() => {}); } catch (_) {}
    try { reader.releaseLock?.(); } catch (_) {}
  }
}

// Führt einen POST-Request aus, der wahlweise als SSE-Stream (stream:true)
// oder als normales JSON beantwortet wird (z. B. Fehler/Limits vor Streamstart).
// deltaRenderers: { eventName: streamRenderer } für die Live-Anzeige.
// Rückgabe: { ok, status, data, streamed } – data hat dieselbe Struktur wie
// die bisherige JSON-Antwort (final-Event des Streams bzw. JSON-Body).
async function streamSSERequest(url, payload, signal, deltaRenderers, requestOptions = {}) {
  const renderers = deltaRenderers || {};
  let failureKind = "request_failed";
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...requestOptions.headers },
      body: JSON.stringify({ ...payload, stream: true }),
      signal
    });

    failureKind = "stream_read_failed";
    const contentType = (response.headers.get("content-type") || "").toLowerCase();
    if (!contentType.includes("text/event-stream") || !response.body) {
      const rawBody = await response.text();
      let data;
      try {
        data = rawBody ? JSON.parse(rawBody) : {};
      } catch (_) {
        data = {
          error: rawBody.trim() || `Request failed with HTTP ${response.status}.`,
          error_code: "http_error"
        };
      }
      if (!response.ok && !data.error && !data.detail) {
        data.error = `Request failed with HTTP ${response.status}.`;
      }
      return { ok: response.ok, status: response.status, data, streamed: false };
    }

    let finalData = null;
    await readSSEStream(response, (eventName, data, eventId) => {
      if (eventName === "final" || eventName === "error") {
        finalData = data;
        return true;
      }
      failureKind = "stream_handler_failed";
      try {
        if (eventName === "reasoning") {
          Object.values(renderers).forEach(renderer => renderer && renderer.markReasoning && renderer.markReasoning());
          return;
        }
        const renderer = renderers[eventName];
        if (!renderer || !data) return;
        // Only the Agent stream numbers its frames (`id:`, agent-chat.js dedupe).
        if (renderer.receive) { eventId === undefined ? renderer.receive(data) : renderer.receive(data, eventId); return; }
        const deltaText = coerceStreamText(data.text);
        if (deltaText) {
          renderer.append(deltaText);
        } else if (data.reasoning && renderer.markReasoning) {
          // Reasoning-Marker auf einem benannten Event (z. B. consensus.delta):
          // nur den zugehörigen Renderer markieren, nicht alle.
          renderer.markReasoning();
        }
      } catch (error) {
        // Keep handler failures distinct from failures of reader.read().
        throw Object.assign(new Error(error?.message || "Stream rendering failed."), {
          name: error?.name || "Error", streamFailureKind: "stream_handler_failed"
        });
      } finally {
        failureKind = "stream_read_failed";
      }
    }, requestOptions.onProgress);

    if (!finalData) {
      throw Object.assign(new Error("Connection lost before the response was completed."), {
        streamFailureKind: "stream_incomplete"
      });
    }
    return { ok: true, status: response.status, data: finalData, streamed: true };
  } catch (error) {
    throw Object.assign(new Error(error?.message || "The request failed."), {
      name: error?.name || "Error", streamFailureKind: error?.streamFailureKind || failureKind
    });
  } finally {
    Object.values(renderers).forEach(renderer => renderer?.stop?.());
  }
}
window.streamSSERequest = streamSSERequest;
