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
    return window.DOMPurify.sanitize(window.marked.parse(prepared));
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

  function dispatch(rawEvent) {
    let eventName = "message";
    const dataLines = [];
    rawEvent.split("\n").forEach(line => {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
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
    return onEvent(eventName, parsed);
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
    await readSSEStream(response, (eventName, data) => {
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
        if (renderer.receive) { renderer.receive(data); return; }
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
