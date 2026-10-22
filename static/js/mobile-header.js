// The mobile header owns the same action nodes as the desktop footer. Keeping
// the nodes preserves their handlers, Watch state and the Cite menu's anchor.
// Load after consensus-actions.js and watch.js have created the controls.
(function () {
  const header = document.getElementById('mobileConversationActions');
  const sidebarViews = document.getElementById('mobileSidebarViews');
  const actions = document.getElementById('consensusFooterActions');
  const views = document.getElementById('viewSwitch');
  if (!header || !sidebarViews || !actions || !views) return;

  const media = window.matchMedia('(max-width: 1099px)');
  const footer = document.getElementById('runProvenance');
  const output = document.getElementById('consensusOutput');
  const watch = document.getElementById('watchDashboard');
  const homes = new Map();
  [actions, views].forEach(node => {
    const marker = document.createComment(`desktop:${node.id}`);
    node.before(marker);
    homes.set(node, marker);
  });

  function place(node, parent) {
    if (node.parentElement === parent) return false;
    if (parent === homes.get(node).parentElement) homes.get(node).after(node);
    else parent.append(node);
    return true;
  }

  function sync() {
    const mobile = media.matches;
    const focused = document.activeElement;
    const focusedView = views.contains(focused);
    const focusedAction = actions.contains(focused);
    // Only show controls for the visible, finished answer. The footer remains
    // the source of readiness while the buttons are temporarily outside it.
    actions.hidden = mobile && (document.body.classList.contains('is-hero')
      || !footer || footer.hidden || !output || output.hidden
      || output.classList.contains('is-hidden') || (watch && !watch.hidden)
      || !document.getElementById('consensusAnswerBody')?.textContent.trim());
    const movedActions = place(actions, mobile ? header : homes.get(actions).parentElement);
    // In the island the toggle draws three dots and its menu also shares;
    // in the footer it is the "Cite" button beside its own Share.
    const toggle = actions.querySelector('.consensus-actions-toggle');
    if (toggle) {
      const label = mobile ? 'Share, copy and cite' : 'Citation and copy options';
      toggle.setAttribute('aria-label', label);
      toggle.title = label;
    }
    const movedViews = place(views, mobile ? sidebarViews : homes.get(views).parentElement);
    if (movedViews && focusedView && mobile) document.getElementById('toggleSidebarButton')?.focus({preventScroll:true});
    else if ((movedActions && focusedAction && !actions.hidden) || (movedViews && focusedView)) focused.focus({preventScroll:true});
    syncAgent();
    scheduleEdge();
  }

  // Agent: the bar carries Watch and Share of the answer on screen, the way
  // Consensus carries its Watch (2026-10-22); under the answer the two pills
  // are hidden at this width (components-watch.css). The glyphs press those
  // pills, so watch.js and share-dialog.js keep the question, the "Watching"
  // state and the dialogs; `_actionTrigger` hands them the glyph to return
  // focus to. Turns further up keep their own pills.
  const agentAnswer = document.getElementById('agentAnswer');
  const agentWatch = document.getElementById('mobileAgentWatch');
  const agentShare = document.getElementById('mobileAgentShare');
  // Looked up inside the answer: the ID #agentAnswerWatchButton moves
  // between turns, and its removal from a turn above is not seen here.
  const livePills = () => ({
    watch: agentAnswer?.querySelector('.agent-watch-pill') || null,
    share: agentAnswer?.querySelector('.agent-share-pill') || null,
  });
  function syncAgent() {
    if (!agentWatch || !agentShare) return;
    const { watch: watchPill, share: sharePill } = livePills();
    const shown = media.matches && document.body.classList.contains('single-agent-active')
      && !document.body.classList.contains('is-hero') && !(watch && !watch.hidden)
      && Boolean(agentAnswer && !agentAnswer.hidden);
    agentWatch.hidden = !(shown && watchPill);
    agentShare.hidden = !(shown && sharePill);
    if (watchPill) {
      const label = watchPill.getAttribute('aria-label') || 'Watch this question for changes';
      if (agentWatch.getAttribute('aria-label') !== label) {
        agentWatch.setAttribute('aria-label', label);
        agentWatch.title = label;
      }
      agentWatch.classList.toggle('is-watching', watchPill.classList.contains('is-watching'));
    }
  }
  function press(pill, trigger) {
    if (!pill) return;
    pill._actionTrigger = trigger;
    try { pill.click(); } finally { pill._actionTrigger = null; }
  }
  agentWatch?.addEventListener('click', () => press(livePills().watch, agentWatch));
  agentShare?.addEventListener('click', () => press(livePills().share, agentShare));
  // The pills come and go with the answer and its run, and "Watching"
  // changes their class; once a frame is enough for that.
  let agentFrame = 0;
  if (agentAnswer && agentWatch) {
    new MutationObserver(() => {
      if (!agentFrame) agentFrame = requestAnimationFrame(() => { agentFrame = 0; syncAgent(); });
    }).observe(agentAnswer, {childList:true, subtree:true, attributes:true, attributeFilter:['class', 'aria-label', 'hidden']});
  }
  // Reading the scroll position right after a class change forced the new
  // layout in the middle of a send (Apple-Audit D3); in the frame it is free.
  let edgeFrame = 0;
  function scheduleEdge() {
    if (!edgeFrame) edgeFrame = requestAnimationFrame(() => { edgeFrame = 0; syncEdge(); });
  }

  document.getElementById('mobileNewRunButton')?.addEventListener('click', () => {
    document.getElementById('newRunButton')?.click();
  });
  views.addEventListener('click', event => {
    if (media.matches && event.target.closest('.view-switch-btn')
      && document.querySelector('.sidebar.active')) document.getElementById('sidebarToggleInner')?.click();
  });
  // The bar's edge shows only once the page (or the Watch page, which
  // scrolls on its own) has moved beneath it.
  const bar = header.closest('.app-mobile-header');
  function syncEdge() {
    const watchScrolled = watch && !watch.hidden && watch.scrollTop > 0;
    bar?.classList.toggle('is-scrolled', window.scrollY > 0 || Boolean(watchScrolled));
  }
  window.addEventListener('scroll', syncEdge, {passive:true});
  watch?.addEventListener('scroll', syncEdge, {passive:true});
  syncEdge();

  media.addEventListener('change', sync);
  const observer = new MutationObserver(sync);
  observer.observe(document.body, {attributes:true, attributeFilter:['class']});
  if (footer) observer.observe(footer, {attributes:true, attributeFilter:['hidden']});
  if (output) observer.observe(output, {attributes:true, attributeFilter:['hidden','class']});
  if (watch) observer.observe(watch, {attributes:true, attributeFilter:['hidden']});
  sync();
})();
