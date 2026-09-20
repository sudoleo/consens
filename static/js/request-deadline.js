// Bound short control requests, including authentication and body parsing.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  App.withRequestDeadline = async function (operation, { signal, timeoutMs = 15000 } = {}) {
    const controller = new AbortController();
    let timer, onAbort, touch, closed = false;
    const interrupted = new Promise((_, reject) => {
      onAbort = () => {
        controller.abort();
        reject(new DOMException('Request cancelled', 'AbortError'));
      };
      if (signal?.aborted) { onAbort(); return; }
      signal?.addEventListener('abort', onAbort, { once: true });
      touch = () => {
        if (closed || controller.signal.aborted) return;
        clearTimeout(timer);
        timer = setTimeout(() => {
          controller.abort();
          reject(new Error('The connection is taking too long. Please try again.'));
        }, timeoutMs);
      };
      touch();
    });
    try {
      return await Promise.race([interrupted, Promise.resolve().then(() => {
        if (controller.signal.aborted) throw new DOMException('Request cancelled', 'AbortError');
        return operation(controller.signal, touch);
      })]);
    } finally {
      closed = true;
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
    }
  };
})();
