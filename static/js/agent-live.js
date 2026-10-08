// Following a running Agent turn without (or beside) its event stream.
//
// The server runs a turn independently of the connection that started it
// and keeps its frames in memory (GET /agent/chats/{chat}/live, the same
// frames as the POST stream). This module reads them in two situations:
//
// - Buffering networks: some company proxies and virus scanners hold a whole
//   SSE response back until it ends. When no byte at all has arrived after
//   SILENCE_MS, polling starts and hands every frame to the run's dispatcher.
// - Reconnect (`reconnect()`): the stream broke (network drop, a phone that
//   put the tab to sleep, a server restart) or the page was reloaded while
//   the turn ran. Polling then continues until the turn ends: network errors
//   only slow it down, `online` and a visible tab poll at once, and a server
//   that does not know the turn (another instance after a deploy, an expired
//   buffer) is asked for the saved turn instead.
//
// Each frame carries the run's sequence number (SSE `id:`), so a late flush
// of a buffered stream cannot apply a frame twice: `sequence()` is the one
// guard both paths pass through (agent-chat.js `deliver`). A reader that fell
// behind the server's window first receives `reset` with the answer text so far.
//
// Contract (App.agentLive):
//   sequence() -> { accept(seq) -> boolean, last }
//   watch({ chatId, requestId, headers (object | async () => object), signal,
//           deliver(type, data, seq), cursor() -> number,
//           recover() -> Promise<result with data.turn | 'running' | 'offline' | null>,
//           onEngage(), onState({ reconnecting, offline }) })
//     -> { bytes(), stop(), reconnect(), finished: Promise<result|null> }
// `finished` resolves when polling ended the run: with the terminal frame
// (same shape as streamSSERequest's result) or recover()'s saved answer. After
// reconnect() it also resolves with null when the turn is gone for good (or
// the watch was stopped), so the caller can fall back. It never rejects.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const SILENCE_MS = 5000;
  const POLL_MS = 1500;
  const BUSY_POLL_MS = 5000;
  // A turn this server does not hold but that is still running elsewhere
  // (the previous instance during a deploy): check its saved state slowly.
  const RUNNING_ELSEWHERE_MS = 5000;
  const REQUEST_TIMEOUT_MS = 10000;
  // Network errors back off up to this delay; `online` polls at once.
  const MAX_BACKOFF_MS = 10000;
  // Another worker, a restart or an expired buffer: give up after this many
  // consecutive "unknown" answers and keep the ordinary stream behaviour.
  const MAX_UNKNOWN = 4;
  // After reconnect(): how often "no turn, no saved answer" ends the wait.
  const MAX_GONE = 2;

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
    const { chatId, requestId, signal, deliver, recover, onEngage, onState } = options;
    const headersOf = typeof options.headers === 'function' ? options.headers : async () => options.headers || {};
    const cursorOf = typeof options.cursor === 'function' ? options.cursor : () => 0;
    // Read at watch time, so tests can shorten them on App.agentLive.
    const silenceMs = api.SILENCE_MS, pollMs = api.POLL_MS, elsewhereMs = api.RUNNING_ELSEWHERE_MS;
    let resolveFinished;
    const finished = new Promise(resolve => { resolveFinished = resolve; });
    let stopped = false, polling = false, engaged = false, bytesSeen = false, persistent = false;
    let silenceTimer = null, pollTimer = null, controller = null;
    let unknown = 0, gone = 0, failures = 0, cursor = 0, inFlight = false, offline = false;

    function clearTimers() {
      clearTimeout(silenceTimer); silenceTimer = null;
      clearTimeout(pollTimer); pollTimer = null;
    }
    function setOffline(value) {
      if (offline === value) return;
      offline = value;
      if (persistent) report();
    }
    function report() {
      try { onState?.({ reconnecting: persistent && !stopped, offline }); } catch (_) { /* display only */ }
    }
    function stop() {
      if (stopped) return;
      stopped = true; polling = false;
      clearTimers();
      try { controller?.abort(); } catch (_) { /* already closed */ }
      signal?.removeEventListener?.('abort', stop);
      window.removeEventListener('online', wake);
      document.removeEventListener('visibilitychange', wake);
      if (persistent) { report(); resolveFinished(null); }
    }
    function finish(result) {
      if (stopped) return;
      resolveFinished(result);
      stop();
    }
    function wake() {
      if (stopped || !polling || inFlight || document.visibilityState === 'hidden') return;
      clearTimeout(pollTimer); pollTimer = null;
      poll();
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
    function backoff() {
      return Math.min(MAX_BACKOFF_MS, pollMs * 2 ** Math.min(failures - 1, 6));
    }
    async function savedState() {
      // The saved turn decides once this server holds no frames for it.
      let outcome = null;
      try { outcome = await recover?.(); } catch (_) { outcome = 'offline'; }
      return outcome;
    }
    async function poll() {
      if (stopped || !polling || inFlight) return;
      // One poll at a time, including its saved-state check: `online` and a
      // visible tab must not start a second one beside it.
      inFlight = true;
      try { await pollOnce(); } finally { inFlight = false; }
    }
    async function pollOnce() {
      let data = null, busy = false, network = false;
      try {
        controller = new AbortController();
        const timer = setTimeout(() => controller?.abort(), REQUEST_TIMEOUT_MS);
        try {
          cursor = Math.max(cursor, Number(cursorOf()) || 0);
          const headers = await headersOf();
          const url = `/agent/chats/${encodeURIComponent(chatId)}/live?request_id=${encodeURIComponent(requestId)}&after=${cursor}`;
          const response = await fetch(url, { headers, signal: controller.signal, cache: 'no-store' });
          busy = response.status === 429;
          data = response.ok ? await response.json() : null;
        } finally { clearTimeout(timer); }
      } catch (_) { data = null; network = true; } finally { controller = null; }
      if (stopped || !polling) return;
      if (network) {
        // Offline, asleep or a broken connection: no verdict on the turn.
        failures += 1;
        setOffline(true);
        schedule(backoff());
        return;
      }
      failures = 0;
      setOffline(false);
      if (busy) { schedule(BUSY_POLL_MS); return; }
      if (!data || data.known !== true) {
        if (persistent) {
          const outcome = await savedState();
          if (stopped || !polling) return;
          if (outcome?.data?.turn) { finish(outcome); return; }
          if (outcome === 'offline') { failures += 1; setOffline(true); schedule(backoff()); return; }
          if (outcome === 'running') { gone = 0; schedule(elsewhereMs); return; }
          if (++gone >= MAX_GONE) { stop(); return; }
          schedule();
          return;
        }
        if (++unknown >= MAX_UNKNOWN) { stop(); return; }
        schedule();
        return;
      }
      unknown = 0; gone = 0;
      if (!engaged && !bytesSeen && !persistent) {
        engaged = true;
        try { onEngage?.(); } catch (_) { /* analytics never breaks a run */ }
      }
      const reset = data.reset;
      if (reset && Number.isInteger(Number(reset.seq))) {
        cursor = Math.max(cursor, Number(reset.seq));
        deliver('reset', { text: typeof reset.text === 'string' ? reset.text : '' }, reset.seq);
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
        const outcome = await savedState();
        if (stopped) return;
        if (outcome?.data?.turn) { finish(outcome); return; }
        if (persistent && outcome === 'offline') { failures += 1; setOffline(true); schedule(backoff()); return; }
        stop();
        return;
      }
      schedule();
    }

    if (signal?.aborted) stopped = true;
    else {
      signal?.addEventListener?.('abort', stop, { once: true });
      armSilence();
    }
    return {
      finished,
      stop,
      // The stream broke or never existed (a reload): follow the turn by
      // polling until it ends, whatever the network does meanwhile.
      reconnect() {
        if (stopped) { resolveFinished(null); return; }
        if (persistent) return;
        persistent = true;
        polling = true;
        unknown = 0;
        clearTimeout(silenceTimer); silenceTimer = null;
        window.addEventListener('online', wake);
        document.addEventListener('visibilitychange', wake);
        report();
        if (!inFlight) { clearTimeout(pollTimer); pollTimer = null; poll(); }
      },
      // Stream bytes arrived: the stream is live (again), polling pauses. On
      // a network that has buffered once, renewed silence resumes it.
      bytes() {
        bytesSeen = true;
        if (stopped || persistent) return;
        polling = false;
        clearTimers();
        if (engaged) armSilence();
      },
      get engaged() { return engaged; },
      get polling() { return polling; },
      get reconnecting() { return persistent && !stopped; },
    };
  }

  const api = App.agentLive = { sequence, watch, SILENCE_MS, POLL_MS, RUNNING_ELSEWHERE_MS };
})();
