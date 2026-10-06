// Bound short control requests, including authentication and body parsing.
// `onIdle` (optional) is asked before an idle request is given up: it returns
// undefined to keep waiting, a value to finish with instead, or throws.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  App.withRequestDeadline = async function (operation, { signal, timeoutMs = 15000, onIdle } = {}) {
    const controller = new AbortController();
    let timer, onAbort, touch, closed = false;
    const interrupted = new Promise((resolve, reject) => {
      onAbort = () => {
        controller.abort();
        reject(new DOMException('Request cancelled', 'AbortError'));
      };
      if (signal?.aborted) { onAbort(); return; }
      signal?.addEventListener('abort', onAbort, { once: true });
      touch = () => {
        if (closed || controller.signal.aborted) return;
        clearTimeout(timer);
        timer = setTimeout(async () => {
          if (onIdle) {
            let outcome;
            try { outcome = await onIdle(); } catch (error) {
              if (closed) return;
              controller.abort();
              reject(error);
              return;
            }
            if (closed || controller.signal.aborted) return;
            if (outcome === undefined) { touch(); return; }
            controller.abort();
            resolve(outcome);
            return;
          }
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
