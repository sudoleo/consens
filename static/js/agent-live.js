// Live progress for an Agent run on networks that buffer event streams.
//
// Some company proxies and virus scanners hold a whole SSE response back
// until it ends: without this the browser shows "Thinking…" for minutes and
// then the full answer at once. Normally the server's 2 KiB padding arrives
// right after sending; when no byte at all has arrived after SILENCE_MS, this
// module polls GET /agent/chats/{chat}/live (the server's in-memory replay of
// the same frames) and hands every frame to the run's own stream dispatcher.
// Each frame carries the run's sequence number (SSE `id:`), so a later flush
// of the buffered stream cannot apply a frame twice: `sequence()` is the one
// guard both paths pass through (agent-chat.js `deliver`).
//
// Contract (App.agentLive):
//   sequence() -> { accept(seq) -> boolean, last }
//   watch({ chatId, requestId, headers, signal, deliver(type, data, seq),
//           cursor() -> number, recover() -> Promise<result|null>, onEngage() })
//     -> { bytes(), stop(), finished: Promise<result> }
// `finished` resolves only when polling ended the run first: with the
// terminal frame (same shape as streamSSERequest's result) or, when the run
// is done without one, with recover()'s saved answer. It never rejects.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const SILENCE_MS = 5000;
  const POLL_MS = 1500;
  const BUSY_POLL_MS = 5000;
  // Another worker, a restart or an expired buffer: give up after this many
  // consecutive "unknown" answers and keep the ordinary stream behaviour.
  const MAX_UNKNOWN = 4;

  function sequence() {
    let applied = 0;
    return {
      accept(seq) {
        const value = Number(seq);
        // Frames without a number (an older server) are always new.
        if (!Number.isInteger(value) || value <= 0) return true;
        if (value <= applied) return false;
        applied = value;
        return true;
      },
      get last() { return applied; },
    };
  }

  function watch(options) {
    const { chatId, requestId, headers, signal, deliver, recover, onEngage } = options;
    const cursorOf = typeof options.cursor === 'function' ? options.cursor : () => 0;
    // Read at watch time, so tests can shorten them on App.agentLive.
    const silenceMs = api.SILENCE_MS, pollMs = api.POLL_MS;
    let resolveFinished;
    const finished = new Promise(resolve => { resolveFinished = resolve; });
    let stopped = false, polling = false, engaged = false, bytesSeen = false;
    let silenceTimer = null, pollTimer = null, controller = null;
    let unknown = 0, cursor = 0, inFlight = false;

    function clearTimers() {
      clearTimeout(silenceTimer); silenceTimer = null;
      clearTimeout(pollTimer); pollTimer = null;
    }
    function stop() {
      if (stopped) return;
      stopped = true; polling = false;
      clearTimers();
      try { controller?.abort(); } catch (_) { /* already closed */ }
      signal?.removeEventListener?.('abort', stop);
    }
    function finish(result) {
      stop();
      resolveFinished(result);
    }
    function armSilence() {
      clearTimeout(silenceTimer);
      silenceTimer = setTimeout(() => {
        silenceTimer = null;
        if (stopped) return;
        polling = true;
        poll();
      }, silenceMs);
    }
    function schedule(ms = pollMs) {
      clearTimeout(pollTimer);
      pollTimer = setTimeout(() => { pollTimer = null; poll(); }, ms);
    }
    async function poll() {
      if (stopped || !polling || inFlight) return;
      inFlight = true;
      let data = null, busy = false;
      try {
        controller = new AbortController();
        cursor = Math.max(cursor, Number(cursorOf()) || 0);
        const url = `/agent/chats/${encodeURIComponent(chatId)}/live?request_id=${encodeURIComponent(requestId)}&after=${cursor}`;
        const response = await fetch(url, { headers, signal: controller.signal, cache: 'no-store' });
        busy = response.status === 429;
        data = response.ok ? await response.json() : null;
      } catch (_) { data = null; } finally { inFlight = false; controller = null; }
      if (stopped || !polling) return;
      if (busy) { schedule(BUSY_POLL_MS); return; }
      if (!data || data.known !== true) {
        if (++unknown >= MAX_UNKNOWN) { stop(); return; }
        schedule();
        return;
      }
      unknown = 0;
      if (!engaged && !bytesSeen) {
        engaged = true;
        try { onEngage?.(); } catch (_) { /* analytics never breaks a run */ }
      }
      for (const event of Array.isArray(data.events) ? data.events : []) {
        if (stopped || !polling) return;
        const seq = Number(event?.seq);
        if (Number.isInteger(seq)) cursor = Math.max(cursor, seq);
        if (event?.type === 'final' || event?.type === 'error') {
          // The same terminal frame the stream would deliver, so the run
          // ends exactly as it would have with a working stream.
          finish({ ok: true, status: 200, data: event.data || {}, streamed: true });
          return;
        }
        deliver(event?.type, event?.data, event?.seq);
      }
      cursor = Math.max(cursor, Number(data.last_seq) || 0);
      if (data.more) { schedule(0); return; }
      if (data.done) {
        // Ended without a terminal frame in the buffer: ask for the saved
        // answer instead of waiting for the proxy to release the stream.
        stop();
        let saved = null;
        try { saved = await recover?.(); } catch (_) { saved = null; }
        if (saved) resolveFinished(saved);
        return;
      }
      schedule();
    }

    if (signal?.aborted) stop();
    else {
      signal?.addEventListener?.('abort', stop, { once: true });
      armSilence();
    }
    return {
      finished,
      stop,
      // Stream bytes arrived: the stream is live (again), polling pauses. On
      // a network that has buffered once, renewed silence resumes it.
      bytes() {
        bytesSeen = true;
        if (stopped) return;
        polling = false;
        clearTimers();
        if (engaged) armSilence();
      },
      get engaged() { return engaged; },
      get polling() { return polling; },
    };
  }

  const api = App.agentLive = { sequence, watch, SILENCE_MS, POLL_MS };
})();
