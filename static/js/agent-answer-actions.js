// Small, stable actions for live, recovered and archived Agent answers.
(function () {
  'use strict';
  const App = window.App = window.App || {};
  const views = new WeakMap();

  // Icon-only: the row under an answer leads with the agreement score; Copy
  // is the quiet last control in it (name and tooltip carry the label).
  function button(label, path) {
    const control = document.createElement('button');
    control.type = 'button';
    control.setAttribute('aria-label', label);
    control.title = label;
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.setAttribute('aria-hidden', 'true');
    const shape = document.createElementNS(icon.namespaceURI, 'path');
    shape.setAttribute('d', path);
    icon.append(shape);
    control.append(icon);
    return control;
  }

  async function writeClipboard(text) {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
    const previous = document.activeElement;
    const input = document.createElement('textarea');
    input.value = text;
    input.className = 'agent-copy-buffer';
    document.body.append(input);
    try {
      input.select();
      if (!document.execCommand('copy')) throw new Error('Copy unavailable');
    } finally {
      input.remove();
      previous?.focus({ preventScroll: true });
    }
  }

  function render(body, { key = '', text = '', running = false } = {}) {
    if (!body) return;
    let view = views.get(body);
    if (!view) {
      const bar = document.createElement('div');
      bar.className = 'agent-answer-actions';
      const copy = button('Copy answer', 'M9 9h11v11H9zM15 5V3H3v12h2');
      const status = document.createElement('span');
      status.className = 'agent-copy-status';
      status.setAttribute('role', 'status');
      bar.append(copy, status);
      view = { bar, copy, status, revision: 0 };
      views.set(body, view);
      copy.addEventListener('click', async () => {
        if (view.copying || bar.hidden) return;
        const revision = view.revision;
        clearTimeout(view.timer);
        view.copying = true;
        copy.setAttribute('aria-disabled', 'true');
        status.textContent = '';
        try {
          // Copy the answer itself, never review badges, progress or UI controls.
          await writeClipboard(view.text);
          if (revision !== view.revision || !bar.isConnected) return;
          status.textContent = 'Copied';
          view.timer = setTimeout(() => { status.textContent = ''; }, 2500);
        } catch (_) {
          if (revision === view.revision && bar.isConnected) status.textContent = 'Could not copy. Select the answer to copy it.';
        } finally {
          if (revision === view.revision) { view.copying = false; copy.removeAttribute('aria-disabled'); }
        }
      });
    }
    const hidden = running || !text.trim();
    if (view.key !== key || view.text !== text || view.bar.hidden !== hidden) {
      view.revision++;
      clearTimeout(view.timer);
      view.status.textContent = '';
      view.copying = false;
      view.copy.removeAttribute('aria-disabled');
    }
    view.key = key;
    view.text = text;
    view.bar.hidden = hidden;
    // Inside the evidence row when there is one, so Copy and the evidence
    // links read as one line; otherwise directly under the answer.
    // History turns are built detached, so "same parent" rather than isConnected.
    const review = body._agentReview?.parentNode && body._agentReview.parentNode === body.parentNode ? body._agentReview : null;
    if (review) { if (view.bar.parentElement !== review) review.append(view.bar); }
    else if (body.nextElementSibling !== view.bar) body.after(view.bar);
  }

  App.agentAnswerActions = { render };
})();
