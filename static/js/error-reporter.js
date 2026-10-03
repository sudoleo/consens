// Critical browser failures only. Expected API errors and deliberate
// AbortController cancellations are reported by neither this module nor the
// global console; run modules opt in when a complete user flow has failed.
(function () {
  "use strict";

  window.App = window.App || {};

  const recentReports = new Map();
  const DEDUPE_MS = 5 * 60 * 1000;
  const MAX_RECENT = 40;
  const STATIC_ASSETS = new Set([
    "js/analytics-opt-out.js",
    "vendor/marked/12.0.2/marked.min.js",
    "vendor/dompurify/3.4.16/dist/purify.min.js",
    "vendor/katex/0.17.0/dist/katex.min.js",
    "vendor/katex/0.17.0/dist/katex.min.css",
    "vendor/katex/0.17.0/dist/contrib/auto-render.min.js"
  ]);

  function criticalAssetName(target) {
    try {
      const url = new URL(target?.src || target?.href || "", window.location.href);
      if (url.origin !== window.location.origin) return "";
      const relative = url.pathname.replace(/^\/static\//, "");
      if (STATIC_ASSETS.has(relative)) return relative;
      if (/^dist\/(?:(?:head|auth|firebase|demo|app)\.[a-f0-9]{12}\.js|app\.[a-f0-9]{12}\.css)$/.test(relative)) return relative;
    } catch (_) { /* Unknown resources retain only their coarse class. */ }
    return "";
  }
  const ERROR_NAMES = new Set([
    "Error", "TypeError", "ReferenceError", "RangeError", "SyntaxError",
    "URIError", "EvalError", "AggregateError", "SecurityError", "InvalidStateError",
    "IndexSizeError", "QuotaExceededError", "NetworkError", "NotSupportedError"
  ]);

  const BUNDLE_PATH = /^\/static\/dist\/((?:head|auth|firebase|demo|app)\.[a-f0-9]{12}\.js)$/;
  const MAX_FRAMES = 5;

  function validCoordinate(number) {
    return Number.isInteger(number) && number > 0 && number <= 10000000;
  }

  // Same-origin app bundle name for a script URL, or "" for anything else.
  function bundleName(filename) {
    if (!filename) return "";
    try {
      const url = new URL(filename, window.location.href);
      const match = url.pathname.match(BUNDLE_PATH);
      return url.origin === window.location.origin && match ? match[1] : "";
    } catch (_) { return ""; }
  }

  // The app bundle this page runs; its content hash identifies the deploy.
  function currentBundle() {
    try {
      for (const script of document.querySelectorAll("script[src]")) {
        const name = bundleName(script.getAttribute("src"));
        if (name && name.startsWith("app.")) return name;
      }
    } catch (_) { /* No bundle in source mode. */ }
    return "";
  }

  function runtimeContext(value) {
    const context = {};
    const error = value.error || value.reason;
    if (ERROR_NAMES.has(error?.name)) context.error_name = error.name;
    // Frames are (bundle, line, column) tuples only: never stack text, URLs
    // or function names. The server maps them through the bundle source maps.
    const frames = [];
    const stack = String(value.stack || error?.stack || "").slice(0, 4000);
    for (const match of stack.matchAll(/(https?:\/\/[^\s()]+):(\d+):(\d+)/g)) {
      const script = bundleName(match[1]);
      const line = Number(match[2]);
      const column = Number(match[3]);
      if (!script || !validCoordinate(line) || !validCoordinate(column)) continue;
      frames.push([script, line, column]);
      if (frames.length >= MAX_FRAMES) break;
    }
    const filename = bundleName(value.filename);
    if (filename) {
      context.script = filename;
      if (validCoordinate(value.line)) context.line = value.line;
      if (validCoordinate(value.column)) context.column = value.column;
    } else if (frames.length) {
      [context.script, context.line, context.column] = frames[0];
    }
    if (frames.length) context.frames = frames;
    return context;
  }

  function isExpectedAbort(value) {
    if (!value) return false;
    if (value.name === "AbortError") return true;
    return value instanceof DOMException && value.name === "AbortError";
  }

  function asText(value, fallback) {
    if (typeof value === "string") return value;
    if (value && typeof value.message === "string") return value.message;
    try {
      return JSON.stringify(value) || fallback;
    } catch (_) {
      return fallback;
    }
  }

  function compactDetails(value) {
    if (!value) return "";
    if (typeof value === "string") return value;
    try {
      return JSON.stringify(value);
    } catch (_) {
      return String(value);
    }
  }

  function shouldSend(report) {
    const now = Date.now();
    const key = [
      report.type,
      report.phase,
      report.resource_class,
      report.asset,
      report.failure_kind,
      report.error_name,
      report.script,
      report.line,
      report.column,
      report.message,
      report.path
    ].join("|");
    const previous = recentReports.get(key) || 0;
    if (previous && now - previous < DEDUPE_MS) return false;
    recentReports.set(key, now);
    if (recentReports.size > MAX_RECENT) {
      for (const [storedKey, storedAt] of recentReports) {
        if (now - storedAt >= DEDUPE_MS || recentReports.size > MAX_RECENT) {
          recentReports.delete(storedKey);
        }
      }
    }
    return true;
  }

  function reportCriticalError(input) {
    // This runs from global error handlers: even a patched fetch or an
    // unusual error object must never create a second uncaught exception.
    try {
      sendCriticalError(input);
    } catch (_) { /* Reporting is best effort. */ }
  }

  function sendCriticalError(input) {
    const value = input || {};
    if (isExpectedAbort(value.error || value.reason)) return;
    const report = {
      type: String(value.type || "unhandled_error").slice(0, 80),
      phase: String(value.phase || "browser").slice(0, 80),
      message: asText(value.message || value.error || value.reason, "Unknown browser error").trim().slice(0, 700) || "Unknown browser error",
      path: window.location.pathname.slice(0, 300)
    };
    const bundle = currentBundle();
    if (bundle) report.bundle = bundle;
    const resourceClass = String(value.resource_class || "").slice(0, 80);
    if (report.type === "unhandled_error" || report.type === "unhandled_rejection") {
      Object.assign(report, runtimeContext(value));
    }
    if (value.failure_kind) report.failure_kind = String(value.failure_kind).slice(0, 80);
    const details = compactDetails(value.details).slice(0, 1500);
    const stack = String(value.stack || value.error?.stack || value.reason?.stack || "").slice(0, 4000);
    if (resourceClass) report.resource_class = resourceClass;
    if (value.asset) report.asset = String(value.asset).slice(0, 150);
    if (details) report.details = details;
    if (stack) report.stack = stack;
    if (!shouldSend(report)) return;
    fetch("/api/client-errors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(report),
      credentials: "same-origin",
      keepalive: true
    }).catch(function () {
      // Reporting must never create another unhandled rejection.
    });
  }

  function criticalResourceClass(target) {
    const tag = String(target?.tagName || "").toUpperCase();
    const rel = String(target?.rel || "").toLowerCase().split(/\s+/);
    const explicitlyCritical = target?.dataset?.criticalResource === "true";
    const isRequiredScript = tag === "SCRIPT";
    const isRequiredStylesheet = tag === "LINK" && rel.includes("stylesheet");

    // Images, favicons, media and preloads are optional decoration unless a
    // future caller marks one explicitly. Their own components own fallbacks.
    if (!explicitlyCritical && !isRequiredScript && !isRequiredStylesheet) return "";

    const raw = target?.src || target?.href || "";
    if (!raw) return "unknown_resource";
    try {
      const url = new URL(raw, window.location.href);
      if (url.host === window.location.host) {
        if (url.pathname.startsWith("/static/dist/")) return "app_bundle";
        if (url.pathname.startsWith("/static/")) return "static_asset";
        return "same_origin_resource";
      }
      if (url.host === "cdn.jsdelivr.net") return "jsdelivr_dependency";
      if (url.host === "www.gstatic.com") return "firebase_dependency";
      return "";
    } catch (_) {
      return "unknown_resource";
    }
  }

  window.addEventListener("error", function (event) {
    if (event.target && event.target !== window) {
      const resourceClass = criticalResourceClass(event.target);
      if (!resourceClass) return;
      reportCriticalError({
        type: "resource_load_failed",
        phase: "asset_load",
        message: `Failed to load ${event.target.tagName || "resource"}`,
        resource_class: resourceClass,
        asset: criticalAssetName(event.target)
      });
      return;
    }
    reportCriticalError({
      type: "unhandled_error",
      phase: "browser_runtime",
      message: event.message || "Unhandled browser error",
      error: event.error,
      filename: event.filename,
      line: event.lineno,
      column: event.colno,
      stack: event.error?.stack || "",
      details: event.filename
        ? `${event.filename.split("?")[0]}:${event.lineno || 0}:${event.colno || 0}`
        : ""
    });
  }, true);

  window.addEventListener("unhandledrejection", function (event) {
    if (isExpectedAbort(event.reason)) return;
    reportCriticalError({
      type: "unhandled_rejection",
      phase: "browser_promise",
      message: asText(event.reason, "Unhandled promise rejection"),
      reason: event.reason,
      stack: event.reason?.stack || ""
    });
  });

  window.App.reportCriticalError = reportCriticalError;
})();
