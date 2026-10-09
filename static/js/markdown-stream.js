// =====================================================================
// markdown-stream.js
// Markdown-Rendering (sanitised) + SSE-Streaming-Helfer.
// Extrahiert aus templates/index.html (initApp-Closure).
// Exporte: window.injectMarkdown, window.createStreamRenderer,
// window.streamSSERequest. (readSSEStream bleibt modul-privat.)
// Call-time-Abhaengigkeiten: DOMPurify, marked (CDN), window.ConsensusMath,
// window.addCopyButtons, window.addNewTabToLinks, window.linkifySourceTags,
// window.currentEvidenceSources.
// =====================================================================

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value || "";
  return node.innerHTML;
}

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

function neutralizeRemoteMedia(html) {
  if (typeof document === "undefined") return html;
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.querySelectorAll("img").forEach(img => {
    const src = (img.getAttribute("src") || "").trim();
    if (isInlineImageSource(src)) return;
    const note = document.createElement("span");
    note.className = "blocked-remote-image";
    const alt = (img.getAttribute("alt") || "").trim();
    note.textContent = alt ? `[Image not loaded: ${alt}]` : "[External image not loaded]";
    img.replaceWith(note);
  });
  template.content.querySelectorAll("[style]").forEach(el => {
    if (/[()\\]|url|image|@import|expression/i.test(el.getAttribute("style") || "")) {
      el.removeAttribute("style");
    }
  });
  return template.innerHTML;
}

function renderMarkdownHtml(md) {
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
    return escapeHtml(prepared);
  }
  try {
    return neutralizeRemoteMedia(window.DOMPurify.sanitize(window.marked.parse(prepared), MODEL_HTML_CONFIG));
  } catch (error) {
    reportMarkdownFallback("render error");
    return escapeHtml(prepared);
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
  el.innerHTML = renderMarkdownHtml(md);

  enhanceMarkdownTables(el);

  if (window.addCopyButtons) window.addCopyButtons(el);
  if (window.addNewTabToLinks) window.addNewTabToLinks(el);

  if (Array.isArray(evidenceSources) && evidenceSources.length && window.linkifySourceTags) {
    window.linkifySourceTags(el, evidenceSources);
  }

  if (window.ConsensusMath) window.ConsensusMath.render(el);
}

window.injectMarkdown = injectMarkdown;

// --- Incremental Markdown for a growing answer -------------------------
// Re-parsing the whole answer on every streamed chunk makes the total work
// quadratic in its length. A streamed answer only ever grows at its end, so
// the text is cut into top-level blocks at blank lines outside code fences
// and display math. Finished blocks are parsed exactly once; only the last,
// still growing block is rendered again. A block boundary is committed only
// once the line after the blank line is complete, so a list or paragraph that
// continues across a blank line is never split early. Loose lists and
// indented continuations stay in one block. The caller renders the complete
// text once with injectMarkdown() when the stream ends, so constructs that
// span blocks (reference links, footnotes) are exact in the final answer.
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
  const template = document.createElement("template");
  template.innerHTML = renderMarkdownHtml(md);
  const holder = document.createElement("div");
  holder.append(template.content);
  enhanceMarkdownTables(holder);
  if (window.ConsensusMath) window.ConsensusMath.render(holder);
  decorate?.(holder);
  return Array.from(holder.childNodes);
}

// A bold span the stream has opened but not closed yet would show its raw
// asterisks until the closing pair arrives. The unfinished tail is rendered
// as if it were closed; the final injectMarkdown() renders the real text.
function closeOpenStrong(text) {
  if (/(^|\n)\s{0,3}(```|~~~)/.test(text)) return text;
  const marks = (text.replace(/`[^`\n]*`/g, "").match(/\*\*/g) || []).length;
  if (marks % 2 === 0) return text;
  const trimmed = text.replace(/\s+$/, "");
  if (trimmed.endsWith("**")) return trimmed.slice(0, -2);
  return `${trimmed}**${text.slice(trimmed.length)}`;
}

// Renders `md` into `el`, reusing the blocks of the previous call when `md`
// only grew. Returns the number of characters that were parsed.
function renderMarkdownStream(el, md, { decorate } = {}) {
  md = String(md || "");
  let state = el._markdownStream;
  // Anyone else writing into the element (a full injectMarkdown, a review
  // re-render) invalidates the reuse; so does text that did not only grow.
  if (!state || !md.startsWith(state.committedText) || el.childNodes.length !== state.nodeCount) {
    el.replaceChildren();
    state = el._markdownStream = { committedText: "", committed: 0, tail: [], tailText: "", nodeCount: 0 };
  }
  let parsed = 0;
  let end;
  while ((end = nextStreamBlockEnd(md, state.committed)) !== -1) {
    const block = md.slice(state.committed, end);
    state.tail.forEach(node => node.remove());
    state.tail = [];
    el.append(...renderStreamFragment(block, decorate));
    parsed += block.length;
    state.committed = end;
    state.committedText = md.slice(0, end);
  }
  const tailText = md.slice(state.committed);
  if (tailText !== state.tailText) {
    state.tail.forEach(node => node.remove());
    state.tail = tailText.trim() ? renderStreamFragment(closeOpenStrong(tailText), decorate) : [];
    el.append(...state.tail);
    state.tailText = tailText;
    parsed += tailText.length;
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
    outputEl.innerHTML = renderMarkdownHtml(text);
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
