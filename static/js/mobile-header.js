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
    const movedViews = place(views, mobile ? sidebarViews : homes.get(views).parentElement);
    if (movedViews && focusedView && mobile) document.getElementById('toggleSidebarButton')?.focus({preventScroll:true});
    else if ((movedActions && focusedAction && !actions.hidden) || (movedViews && focusedView)) focused.focus({preventScroll:true});
  }

  document.getElementById('mobileNewRunButton')?.addEventListener('click', () => {
    document.getElementById('newRunButton')?.click();
  });
  views.addEventListener('click', event => {
    if (media.matches && event.target.closest('.view-switch-btn')
      && document.querySelector('.sidebar.active')) document.getElementById('sidebarToggleInner')?.click();
  });
  media.addEventListener('change', sync);
  const observer = new MutationObserver(sync);
  observer.observe(document.body, {attributes:true, attributeFilter:['class']});
  if (footer) observer.observe(footer, {attributes:true, attributeFilter:['hidden']});
  if (output) observer.observe(output, {attributes:true, attributeFilter:['hidden','class']});
  if (watch) observer.observe(watch, {attributes:true, attributeFilter:['hidden']});
  sync();
})();
