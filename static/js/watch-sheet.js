// The sheet that starts a Watch away from the Watches page
// (agent_watches.py; the same field as the page, watch-composer.js): the
// Watch pill under an answer starts one in
// that chat, its question already written. On the Watches page every start
// goes to the page's own field instead (watch.js startWatch). The Watch the
// Agent prepared itself has its card under the answer (agent-watch.js).
//
//   App.watchSheet.open({ chatId, task, trigger, source, onStarted })
(function () {
  'use strict';
  const App = window.App = window.App || {};
  let sheet = null;
  let current = null;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function build(chatId, source) {
    if (sheet?.dialog.isConnected && sheet.chatId === chatId && sheet.source === source) return sheet;
    sheet?.composer.destroy();
    sheet?.dialog.remove();
    const dialog = node('dialog', 'modal watch-sheet');
    dialog.setAttribute('aria-labelledby', 'watchSheetTitle');
    const content = node('div', 'modal-content watch-sheet-content');
    const close = node('button', 'close close-button watch-sheet-close');
    close.type = 'button';
    close.setAttribute('aria-label', App.t('Close'));
    close.innerHTML = App.closeIcon ? App.closeIcon() : '';
    const title = node('h2', 'watch-sheet-title', 'New Watch');
    title.id = 'watchSheetTitle';
    const lead = node('p', 'watch-sheet-lead', chatId
      ? 'The Agent looks again in this chat and tells you only when something changes.'
      : 'The Agent looks for you on a schedule and tells you only when something changes.');
    const composer = App.watchComposer.create({ mode: 'sheet', chatId, source, onStarted(watch) {
      const opened = current;
      closeSheet();
      opened?.onStarted?.(watch);
    } });
    content.append(close, title, lead, composer.element);
    dialog.append(content);
    document.body.append(dialog);
    // While it starts, the sheet stays: closed then, the Watch would start unseen.
    App.modalDialog?.bind(dialog, { onClose: () => { current = null; }, keepOpen: () => composer.isBusy() });
    dialog.addEventListener('cancel', event => { if (composer.isBusy()) event.preventDefault(); });
    close.addEventListener('click', () => { if (!composer.isBusy()) closeSheet(); });
    sheet = { dialog, composer, chatId, source };
    return sheet;
  }

  function closeSheet() {
    if (!sheet) return;
    if (App.modalDialog) App.modalDialog.close(sheet.dialog);
    else sheet.dialog.removeAttribute('open');
    current = null;
  }

  function open({ chatId = '', task = '', trigger = null, source = '', onStarted = null } = {}) {
    if (!window.auth?.currentUser) {
      App.watchUi?.requireAccount?.({ question: task }, trigger);
      return;
    }
    const chat = String(chatId || '');
    build(chat, source || (chat ? 'agent_answer' : 'sheet'));
    current = { chatId: chat, source, onStarted };
    sheet.composer.reset();
    sheet.composer.setTask(task);
    // The slots and intervals as they are now (a Watch ended since the last time).
    sheet.composer.load();
    if (App.modalDialog) App.modalDialog.open(sheet.dialog, { focus: sheet.dialog.querySelector('.wc-task'), opener: trigger });
    else sheet.dialog.setAttribute('open', '');
    sheet.composer.focus();
  }

  App.watchSheet = { open, close: closeSheet };
})();
