// =====================================================================
// app-text.js
// How the app writes what it says, in one place (Apple-Audit H1, H8, H9):
//
//   App.format     dates, times, numbers and spans of time in ONE locale,
//                  the language of the page (en-US, or de-DE when i18n.js
//                  made the page German, App.lang), never the browser's: an
//                  English page in a German browser read "19. Okt. 2026" and
//                  "48.213 tokens" next to "Oct 19" and "8,000 characters".
//   App.t          a sentence in the page's language (i18n.js on a German
//                  page); here, on an English page, the sentence itself
//                  with its {placeholders} filled.
//   App.userError  every failure as a sentence with a next step: offline,
//                  an unreachable server, a body that is not JSON (a
//                  company proxy's HTML page), status codes and the
//                  server's {error, code} JSON. The engine's own words
//                  ("Failed to fetch", "Load failed", "The string did not
//                  match the expected pattern.") never reach the reader.
//   App.readJson / App.httpError
//                  read a response without ever throwing the engine's JSON
//                  error, and turn a refusal into an Error that carries its
//                  status, code and the server's sentence.
//   App.errorFields  a refusal's fields in one flat object, whether the
//                  server sent {error: "<sentence>", code, retry_after} or
//                  {error: {error, error_code, …}} / {detail: {…}}.
//   App.words      the glossary: one word per state of a run and of the
//                  answer check, the same everywhere.
//
// Head group (bundles.json): pure functions without DOM work, so every
// module can use them at any time, the Firebase module and the head
// group's token-budget.js included.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};

  // ------------------------------------------------------------------
  // App.format
  // ------------------------------------------------------------------
  const GERMAN = App.lang === "de";
  const LOCALE = GERMAN ? "de-DE" : "en-US";
  // The words App.format writes around its numbers. German is written here,
  // not looked up: the numbers sit inside the words (scripts/i18n.py skips
  // these lines).
  const SAY = GERMAN
    ? { today: "heute", tomorrow: "morgen", justNow: "gerade eben", minutesAgo: n => "vor " + n + " Min.", // i18n-ignore
        hoursAgo: n => "vor " + n + " Std.", yesterday: "gestern", daysAgo: n => "vor " + n + " Tagen", // i18n-ignore
        on: day => "am " + day, h: " Std.", m: " Min.", s: " Sek." } // i18n-ignore
    : { today: "today", tomorrow: "tomorrow", justNow: "just now", minutesAgo: n => n + "m ago",
        hoursAgo: n => n + "h ago", yesterday: "yesterday", daysAgo: n => n + " days ago",
        on: day => "on " + day, h: "h", m: "m", s: "s" };

  if (typeof App.t !== "function") {
    App.lang = "en";
    App.t = function (text, params) {
      if (!params) return String(text);
      return String(text).replace(/\{([A-Za-z_]\w*|\d+)\}/g, (match, name) => (Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match));
    };
  }
  const SECOND = 1000;
  const MINUTE = 60 * SECOND;
  const HOUR = 60 * MINUTE;
  const DAY = 24 * HOUR;
  const formatters = new Map();

  function formatter(kind, options) {
    const key = kind + JSON.stringify(options);
    let cached = formatters.get(key);
    if (!cached) {
      try {
        cached = kind === "number" ? new Intl.NumberFormat(LOCALE, options) : new Intl.DateTimeFormat(LOCALE, options);
      } catch (_) {
        cached = null;
      }
      formatters.set(key, cached);
    }
    return cached;
  }

  function toDate(value) {
    if (value === null || value === undefined || value === "") return null;
    const date = value instanceof Date ? value : new Date(typeof value === "number" ? value : String(value));
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  // "48,213". `digits` caps the fraction ("1.5"), default whole numbers.
  function number(value, { digits = 0 } = {}) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "";
    const intl = formatter("number", { maximumFractionDigits: digits });
    return intl ? intl.format(numeric) : String(Math.round(numeric));
  }

  // The 24-hour clock of the run times, never "02:00 AM": "14:03".
  // `timeZone` writes the clock of another place (a calendar event's).
  function time(value, { timeZone } = {}) {
    const date = toDate(value);
    if (!date) return "";
    if (timeZone) {
      const intl = formatter("date", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone });
      if (intl) return intl.format(date);
    }
    return pad(date.getHours()) + ":" + pad(date.getMinutes());
  }

  // "October": the month alone, as a heading over a month's chats.
  function month(value) {
    const day = toDate(value);
    if (!day) return "";
    const intl = formatter("date", { month: "long" });
    return intl ? intl.format(day) : String(day.getMonth() + 1);
  }

  // "Oct 19"; another year adds it ("Oct 19, 2025"); `year: true` always.
  // `weekday: true` leads with the day ("Tue, Oct 21").
  function date(value, { year = "auto", weekday = false, timeZone, now = Date.now() } = {}) {
    const day = toDate(value);
    if (!day) return "";
    const withYear = year === true || (year === "auto" && day.getFullYear() !== new Date(now).getFullYear());
    const intl = formatter("date", {
      month: "short", day: "numeric",
      ...(withYear ? { year: "numeric" } : {}),
      ...(weekday ? { weekday: "short" } : {}),
      ...(timeZone ? { timeZone } : {})
    });
    return intl ? intl.format(day) : day.toDateString();
  }

  // "Oct 19, 14:03", "Tue, Oct 21, 09:00", "Oct 19, 2025, 14:03".
  function dateTime(value, options = {}) {
    const day = toDate(value);
    return day ? date(day, options) + ", " + time(day, options) : "";
  }

  function startOfDay(day) {
    return new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime();
  }

  // A time ahead, as a person says it: "today, 14:30", "tomorrow, 09:00",
  // "Monday, 09:00", "Oct 30, 09:00".
  function upcoming(value, now = Date.now()) {
    const day = toDate(value);
    if (!day) return "";
    const days = Math.round((startOfDay(day) - startOfDay(new Date(now))) / DAY);
    const clock = time(day);
    if (days === 0) return SAY.today + ", " + clock;
    if (days === 1) return SAY.tomorrow + ", " + clock;
    if (days > 1 && days < 7) {
      const intl = formatter("date", { weekday: "long" });
      if (intl) return intl.format(day) + ", " + clock;
    }
    return date(day, { now }) + ", " + clock;
  }

  // A span of time, the one way the app writes it: "23s", "3m 7s",
  // "1h 2m 5s". `minutes: true` drops the seconds and rounds up to at
  // least a minute ("5h 12m", "1m") for what lies ahead (a reset).
  function duration(ms, { minutes: minutePrecision = false } = {}) {
    const value = Number(ms);
    if (!Number.isFinite(value)) return "";
    if (minutePrecision) {
      const total = Math.max(1, Math.ceil(Math.max(0, value) / MINUTE));
      const hours = Math.floor(total / 60);
      const rest = total % 60;
      if (!hours) return rest + SAY.m;
      return rest ? hours + SAY.h + " " + rest + SAY.m : hours + SAY.h;
    }
    const seconds = Math.floor(Math.max(0, value) / SECOND);
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor(seconds / 60) % 60;
    return (hours ? hours + SAY.h + " " : "") + (mins || hours ? mins + SAY.m + " " : "") + (seconds % 60) + SAY.s;
  }

  // A time behind, in the same units: "just now", "12m ago", "3h ago",
  // "yesterday", "4 days ago", then the date ("on Oct 3").
  function relative(value, now = Date.now()) {
    const day = toDate(value);
    if (!day) return "";
    const minutes = Math.max(0, Math.round((now - day.getTime()) / MINUTE));
    if (minutes < 1) return SAY.justNow;
    if (minutes < 60) return SAY.minutesAgo(minutes);
    const hours = Math.round(minutes / 60);
    const days = Math.round((startOfDay(new Date(now)) - startOfDay(day)) / DAY);
    // Earlier the same day stays in hours, even 23h40m ago (never "yesterday").
    if (hours < 24 || days < 1) return SAY.hoursAgo(Math.min(hours, 23));
    if (days === 1) return SAY.yesterday;
    if (days < 7) return SAY.daysAgo(days);
    return SAY.on(date(day, { now }));
  }

  // "1 source", "3 sources".
  function count(value, singular, plural = singular + "s") {
    const numeric = Number(value) || 0;
    return number(numeric) + " " + (numeric === 1 ? singular : plural);
  }

  App.format = Object.freeze({ LOCALE, number, time, date, month, dateTime, upcoming, duration, relative, count, toDate });

  // ------------------------------------------------------------------
  // App.words -- the glossary (Apple-Audit H9). One word per state.
  // ------------------------------------------------------------------
  App.words = Object.freeze({
    // The check of an answer against the independent model answers.
    check: "Answer check",
    checking: "Checking the answer…",
    checked: "Checked",
    partlyChecked: "Partly checked",
    checkOff: "Answer check off",
    // The run of a message.
    working: "Working",
    failed: "Failed",
    stopped: "Stopped",
    // What is used up by a message.
    allowance: "allowance",
    // The Agent chip says what the comparison models do, not their names:
    // "Claude Sonnet 5.5 +6" meant nothing to a reader new to AI models.
    // One is enough in audit mode, where they review (agent-preferences.js).
    crossCheck: (count, minimum = 2) => count < minimum ? "No cross-check"
      : count === 1 ? "1 AI cross-checks" : `${count} AIs cross-check`
  });

  // ------------------------------------------------------------------
  // App.readJson / App.httpError
  // ------------------------------------------------------------------

  // The body of a response as JSON, never the engine's parse error. An
  // empty body is {}. A body that is not JSON (a proxy's or a captive
  // portal's HTML) is {} on a refusal (the status then speaks) and an
  // error of kind "unreadable" on a 2xx, which App.userError words as
  // "can't be reached".
  async function readJson(response) {
    if (!response) return {};
    const unreadable = () => {
      if (response.ok) {
        throw Object.assign(new Error("The response could not be read."), {
          name: "UnreadableResponse", status: response.status, unreadable: true
        });
      }
      return {};
    };
    // A response-like object that only parses (a polyfill, a test double).
    if (typeof response.text !== "function") {
      if (typeof response.json !== "function") return {};
      try {
        const data = await response.json();
        return data === undefined || data === null ? {} : data;
      } catch (error) {
        if (error?.name === "SyntaxError") return unreadable();
        throw error;
      }
    }
    const text = await response.text();
    if (!text || !text.trim()) return {};
    try {
      return JSON.parse(text);
    } catch (_) {
      return unreadable();
    }
  }

  function plainText(value) {
    return typeof value === "string" && value.trim() ? value.trim() : "";
  }

  const isRecord = value => Boolean(value) && typeof value === "object" && !Array.isArray(value);

  // The sentence a refusal carries: {error}, {detail} (FastAPI), {message},
  // nested {detail: {error|message}} or {error: {error|message}} (main.py
  // wraps a route's detail object that way, review 2026-10-21). A list of
  // validation errors is no sentence for a reader.
  function serverSentence(data) {
    if (!data || typeof data !== "object") return plainText(data);
    const detail = data.detail;
    const error = isRecord(data.error) ? data.error : null;
    return plainText(data.error)
      || (error ? plainText(error.error) || plainText(error.message) : "")
      || plainText(detail)
      || (isRecord(detail) ? plainText(detail.error) || plainText(detail.message) : "")
      || plainText(data.message);
  }

  // A refusal's fields in one flat object, whichever form the server used:
  // {error: "<sentence>", code, retry_after, …} (the agreed form),
  // {error: {error, error_code, …}} (a route's detail object, wrapped by
  // main.py) or {detail: {…}} (FastAPI). `error` is the sentence ("" when
  // there is none); top-level fields win over nested ones.
  function errorFields(data) {
    if (!isRecord(data)) return {};
    const nested = [data.detail, data.error].filter(isRecord);
    const flat = Object.assign({}, ...nested, data);
    flat.error = serverSentence(data);
    if (isRecord(flat.detail) || Array.isArray(flat.detail)) delete flat.detail;
    return flat;
  }

  function codeOf(data) {
    const fields = errorFields(data);
    return String(fields.code || fields.error_code || "");
  }

  function retryAfterOf(response, data) {
    const fromBody = Number(errorFields(data).retry_after);
    if (Number.isFinite(fromBody) && fromBody > 0) return fromBody;
    const header = Number(response?.headers?.get?.("Retry-After"));
    return Number.isFinite(header) && header > 0 ? header : 0;
  }

  // A refused response as an Error: `status`, `code`, `retryAfter`, the
  // whole `data`, and `serverMessage` (the server's own sentence, if any).
  function httpError(response, data = {}, fallback = "") {
    const status = Number(response?.status) || 0;
    const serverMessage = serverSentence(data);
    const error = new Error(serverMessage || fallback || "Request failed (" + status + ").");
    error.name = "HttpError";
    return Object.assign(error, {
      status, code: codeOf(data), retryAfter: retryAfterOf(response, data), data, serverMessage,
      // A body that was no JSON (streamSSERequest marks it) stays unreadable.
      unreadable: data?.unreadable === true
    });
  }

  // ------------------------------------------------------------------
  // App.userError
  // ------------------------------------------------------------------

  // The engine's words for a request that never got an answer: Chrome,
  // Safari (also iOS), Firefox, Firebase Auth, React Native-style fetch.
  const NETWORK = /failed to fetch|load failed|networkerror|network ?error|network request failed|network connection was lost|internet connection appears to be offline|auth\/network-request-failed|err_internet_disconnected|net::err_|fetch failed|could not connect to the server/i;
  // ... for a body that was not the JSON it should have been.
  const UNREADABLE = /did not match the expected pattern|unexpected token|json\.parse|not valid json|unexpected end of (?:json|input|data)|json parse error|unexpected character|unexpected identifier|<!doctype|<html|<\/?body/i;
  // ... for a bug in the page, never a sentence for a reader.
  const ENGINE = /cannot read propert|is not a function|is not defined|undefined is not an object|null is not an object|is not iterable|cannot set propert|maximum call stack|^script error|out of memory|quotaexceeded|the operation was aborted|the user aborted|signal is aborted|^firebase: |\(auth\/[a-z-]+\)|traceback|exception:|internal server error|^not found$|^method not allowed$|^request failed \(\d+\)\.?$|\bhttp ?\d{3}\b|request failed with http/i;
  // ... and how a sentence ends: a full stop, a question, an ellipsis.
  const SENTENCE_END = /[.!?…]["’”)]?$/;
  const ENGINE_NAMES = new Set(["TypeError", "SyntaxError", "ReferenceError", "RangeError", "EvalError", "URIError", "InternalError"]);

  const OFFLINE = "You’re offline.";
  const UNREACHABLE = "consens.io can’t be reached right now.";
  const TRY_AGAIN = "Check your connection and try again.";
  const LATER = "Try again in a moment.";
  const TIMEOUT = "The connection is taking too long.";
  // `context` names what was being done; it decides the next step a
  // sentence ends with and the words for a failure without any.
  const CONTEXTS = {
    // The message went back into the composer (agent-chat.js
    // restoreUnsentDraft, query-send.js): the reader only sends again.
    send: { next: "Your message is back in the box.", fallback: "Your message wasn’t sent. Try again." },
    load: { fallback: "This couldn’t be loaded. Try again." },
    save: { fallback: "This couldn’t be saved. Try again." },
    upload: { fallback: "This file couldn’t be uploaded. Try again." },
    delete: { fallback: "This couldn’t be deleted. Try again." }
  };
  const GENERIC = "Something went wrong. Try again.";

  function waitWords(seconds) {
    if (!(seconds > 0) || seconds <= 90) return "Wait a moment and try again.";
    if (seconds <= 90 * 60) return "Try again in " + Math.max(2, Math.round(seconds / 60)) + " minutes.";
    return "Try again later.";
  }

  const STATUS_WORDS = {
    401: "Your session has ended. Log in again.",
    403: "You don’t have access to this.",
    404: "This is no longer available.",
    408: "The connection is taking too long. Try again.",
    413: "This is too large to send.",
    500: "Something went wrong on our side. " + LATER
  };

  function asError(error) {
    if (error instanceof Error) return error;
    if (typeof error === "string") return { message: error };
    if (error && typeof error === "object") {
      // A raw server body ({error, code, retry_after}) or an object with a message.
      if ("message" in error && !("error" in error) && !("detail" in error)) return error;
      return {
        name: "HttpError", message: serverSentence(error), serverMessage: serverSentence(error),
        code: codeOf(error), retryAfter: retryAfterOf(null, error), status: Number(error.status) || 0, data: error
      };
    }
    return { message: "" };
  }

  function offlineNow() {
    try {
      return typeof navigator !== "undefined" && navigator.onLine === false;
    } catch (_) {
      return false;
    }
  }

  // A status only written into a message ("Consensus HTTP 503").
  function statusOf(error) {
    return Number(error.status) || Number(String(error.message || "").match(/\bHTTP ?(\d{3})\b/i)?.[1]) || 0;
  }

  // What kind of failure this is: "aborted", "offline", "unreachable",
  // "timeout", "rate_limited", "session", "server", "status", "message" (a
  // sentence of ours or the server's that can be shown as it is) or "unknown".
  function kind(input) {
    if (input === null || input === undefined || input === "") return "unknown";
    const error = asError(input);
    const name = String(error.name || "");
    const message = String(error.message || "");
    const status = statusOf(error);
    const code = String(error.code || error.error_code || "");
    if (name === "AbortError") return "aborted";
    if (code === "rate_limited" || status === 429) return "rate_limited";
    if (name === "TimeoutError" || code === "timeout" || status === 408) return "timeout";
    const network = NETWORK.test(message) || code === "auth/network-request-failed";
    const unreadable = error.unreadable === true || name === "UnreadableResponse" || (!error.serverMessage && UNREADABLE.test(message));
    if (network || unreadable) return offlineNow() ? "offline" : "unreachable";
    // A gateway's bare refusal; our own server's 503 carries its sentence.
    if ((status === 502 || status === 503 || status === 504) && !error.serverMessage) return offlineNow() ? "offline" : "unreachable";
    if (status === 401) return "session";
    // A 5xx says the server's words only when they are meant for a reader:
    // a refusal with a code, or a sentence. "Error updating watch" or
    // "Chat storage error" are labels for the log (review 2026-10-21).
    if (status >= 500 && error.serverMessage && !code && !SENTENCE_END.test(error.serverMessage.trim())) return "server";
    if (error.serverMessage && !ENGINE.test(error.serverMessage)) return "message";
    if (status >= 500) return "server";
    if (status >= 400) return STATUS_WORDS[status] ? "status" : "unknown";
    if (ENGINE_NAMES.has(name) || name === "DOMException" || ENGINE.test(message)) return "unknown";
    return message.trim() ? "message" : "unknown";
  }

  // The sentence for a failure. `context`: "send" | "load" | "save" |
  // "upload" | "delete" (CONTEXTS); `fallback` replaces the words for a
  // failure that brings no sentence of its own. An AbortError has none ("").
  function userError(input, { context, fallback } = {}) {
    const words = CONTEXTS[context] || {};
    const otherwise = fallback || words.fallback || GENERIC;
    const error = asError(input);
    const status = statusOf(error);
    const serverMessage = plainText(error.serverMessage);
    switch (kind(input)) {
      case "aborted":
        return "";
      case "offline":
        return OFFLINE + " " + (words.next || TRY_AGAIN);
      case "unreachable":
        return UNREACHABLE + " " + (words.next || LATER);
      case "timeout":
        return serverMessage && !ENGINE.test(serverMessage) ? serverMessage
          : TIMEOUT + " " + (words.next || "Try again.");
      case "rate_limited":
        // The server words its own wait (rate_limit_message); without it the
        // same rule from `retry_after`.
        return serverMessage && !ENGINE.test(serverMessage) ? serverMessage
          : "Too many requests in a short time. " + waitWords(Number(error.retryAfter) || 0);
      case "session":
        return serverMessage && !ENGINE.test(serverMessage) ? serverMessage : STATUS_WORDS[401];
      case "message":
        return serverMessage || String(error.message).trim();
      case "server":
        return STATUS_WORDS[500];
      case "status":
        return STATUS_WORDS[status] || otherwise;
      default:
        return otherwise;
    }
  }
  userError.kind = kind;

  // A new chat the server would not save, for a reason no retry fixes: the
  // user has to tidy up, start over or wait. The server sends error_code and
  // its own text; everything else stays with the generic sentence. Read from
  // FastAPI's {"detail": {...}} and from main.py's {"error": {...}}, since
  // production wraps the detail.
  const CHAT_PERSISTENCE_MESSAGES = {
    chat_limit_reached:
      "You’ve reached the maximum number of saved chats. Delete an old chat to start a new one.",
    turn_limit_reached:
      "This chat has reached its maximum length. Start a new chat to continue.",
    chat_rate_limited:
      "Too many new chats in a short time. Wait a moment and try again."
  };

  function chatPersistenceErrorMessage(data) {
    for (const candidate of [data?.detail, data?.error, data]) {
      if (!isRecord(candidate)) continue;
      const code = typeof candidate.error_code === "string" ? candidate.error_code.trim() : "";
      if (code && Object.prototype.hasOwnProperty.call(CHAT_PERSISTENCE_MESSAGES, code)) {
        return CHAT_PERSISTENCE_MESSAGES[code];
      }
    }
    return "";
  }

  App.userError = userError;
  App.readJson = readJson;
  App.httpError = httpError;
  App.errorFields = errorFields;
  // agent-chat.js, when /chats refuses a new chat (moved here from the
  // Consensus chat session, chat-session.js, on 2026-10-25).
  App.chatPersistenceErrorMessage = chatPersistenceErrorMessage;
})();
