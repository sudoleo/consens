// =====================================================================
// chat-list.js
// App.chatList: the order of the chats in the sidebar. The account's
// projects come first under "Projects" (chat-projects.js), each with its
// chats below it, newest first; a project chat stands only there. Pinned
// chats follow under "Pinned"; the others newest first under quiet date
// headings: Today, Yesterday, Previous 7 days, Previous 30 days, then the
// month, then the year.
//
// firebase.js and run-view.js add, settle and remove rows wherever a chat
// appears; none of them knows about headings. This module watches the list
// and puts the headings, and the pinned rows, where they belong after every
// change, so a row that arrives any way is grouped the same way. A pass
// that finds everything in place writes nothing, which also ends the
// observer's echo of its own writes.
//
// A row keeps the time it had when it joined the list (data-list-time): a
// follow-up saves its chat with a new time, and the chat stays where the
// person found it until the list loads again. A run that has no saved chat
// yet is new, so it joins at the top.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};

  const HEADING = "chat-list-heading";
  const PINNED = Object.freeze({ key: "pinned", label: "Pinned", rank: 0 });
  const TODAY = Object.freeze({ key: "today", label: "Today", rank: 1 });
  const YESTERDAY = Object.freeze({ key: "yesterday", label: "Yesterday", rank: 2 });
  const WEEK = Object.freeze({ key: "week", label: "Previous 7 days", rank: 3 });
  const MONTH = Object.freeze({ key: "month", label: "Previous 30 days", rank: 4 });

  // A saved time as the list gets it: an ISO string from the server, a
  // number, a Date, or a Firestore timestamp that came through as its parts.
  function toTime(value) {
    if (value === null || value === undefined || value === "") return null;
    if (typeof value === "object" && !(value instanceof Date)) {
      const seconds = Number(value.seconds ?? value._seconds);
      return Number.isFinite(seconds) ? seconds * 1000 : null;
    }
    // A number this small is seconds, not milliseconds.
    if (typeof value === "number") return value < 1e11 ? value * 1000 : value;
    const time = new Date(String(value)).getTime();
    return Number.isNaN(time) ? null : time;
  }

  // Calendar days, so a summer-time change never moves a chat a day.
  function dayStart(now, daysBack = 0) {
    const day = new Date(now);
    return new Date(day.getFullYear(), day.getMonth(), day.getDate() - daysBack).getTime();
  }

  // The group of a chat saved at `value`, seen from `now`. Ranks grow with
  // age, so the list's order is the groups' order.
  function groupOf(value, now = Date.now()) {
    const time = toTime(value);
    if (time === null) return null;
    if (time >= dayStart(now)) return TODAY;
    if (time >= dayStart(now, 1)) return YESTERDAY;
    if (time >= dayStart(now, 7)) return WEEK;
    if (time >= dayStart(now, 30)) return MONTH;
    const day = new Date(time);
    const today = new Date(now);
    if (day.getFullYear() === today.getFullYear()) {
      return { key: `month-${day.getMonth()}`, label: App.format.month(day), rank: 10 + today.getMonth() - day.getMonth() };
    }
    const year = day.getFullYear();
    return { key: `year-${year}`, label: String(year), rank: 100 + today.getFullYear() - year };
  }

  function isRow(node) {
    return node.classList?.contains("bookmark");
  }

  function isShown(row) {
    return row.style.display !== "none" && !row.hidden && !row.classList.contains("is-undo-pending");
  }

  // Project rows, a project's "New chat" row and the Projects heading come
  // from chat-projects.js; this module only puts them in their place.
  function isProjectNode(node) {
    return node.classList?.contains("chat-project") || node.classList?.contains("chat-project-empty");
  }

  // Writes a class or attribute only where it changes: every write on a row
  // comes back to sync() through the observer.
  function setClass(node, name, on) {
    if (node.classList.contains(name) !== on) node.classList.toggle(name, on);
  }
  function setHidden(node, hidden) {
    if (node.hidden !== hidden) node.hidden = hidden;
  }

  // The project a row stands in: its saved chat's, else the one its run was
  // started in (run-view.js, data-project-id); an id the account has no
  // project for is no project.
  function projectOf(row, meta, known) {
    const id = meta && meta.project_id !== undefined ? meta.project_id : row.dataset.projectId;
    return id && known.has(id) ? id : null;
  }

  function createHeading(group) {
    const heading = document.createElement("h3");
    heading.className = HEADING;
    heading.dataset.group = group.key;
    heading.textContent = group.label;
    return heading;
  }

  function sync() {
    // A closed window (a test's) still delivers its last observations.
    const container = window.document?.getElementById("bookmarksContainer");
    if (!container) return;
    const now = Date.now();
    const metas = new Map((window.bookmarksData || []).map(meta => [meta?.id, meta]));
    const children = [...container.children];
    const rows = children.filter(isRow);

    // The time a row joined the list, kept on the row.
    let previous = now;
    for (const row of rows) {
      if (!row.dataset.listTime) {
        const meta = metas.get(row.dataset.id);
        const time = meta ? toTime(meta.timestamp) : now;
        row.dataset.listTime = String(time ?? previous);
      }
      previous = Number(row.dataset.listTime) || previous;
    }

    const projects = App.chatProjects?.ordered?.() || [];
    const known = new Set(projects.map(project => project.id));
    const projectChats = new Map(projects.map(project => [project.id, []]));
    const byTime = (a, b) => Number(b.dataset.listTime) - Number(a.dataset.listTime);
    const free = [];
    for (const row of rows) {
      const project = projectOf(row, metas.get(row.dataset.id), known);
      if (project) projectChats.get(project).push(row);
      else free.push(row);
    }

    const pinnedAt = row => toTime(metas.get(row.dataset.id)?.pinned_at) ?? 0;
    const pinned = free.filter(row => metas.get(row.dataset.id)?.pinned === true)
      .sort((a, b) => pinnedAt(b) - pinnedAt(a));
    const others = free.filter(row => !pinned.includes(row)).sort(byTime);

    // While the search field has words every project is open, and a project
    // shows where its name or one of its chats matches (filterBookmarks
    // shows and hides the chats).
    const term = String(document.getElementById("chatSearch")?.value || "").trim().toLowerCase();
    const openRow = rows.find(row => row.classList.contains("is-active"));
    const activeProject = openRow ? projectOf(openRow, metas.get(openRow.dataset.id), known) : null;
    const armed = App.chatProjects?.armed?.() || null;
    const projectNodes = [];
    for (const project of projects) {
      const chats = projectChats.get(project.id).sort(byTime);
      const open = Boolean(term) || App.chatProjects.isOpen(project.id);
      const node = App.chatProjects.rowFor(project);
      for (const row of chats) {
        setClass(row, "in-project", true);
        setClass(row, "is-folded", !open);
      }
      setClass(node, "is-open", open);
      setClass(node, "is-current", armed === project.id || (!open && activeProject === project.id));
      const matches = !term || project.name.toLowerCase().includes(term) || chats.some(isShown);
      setHidden(node, !matches);
      App.chatProjects.syncToggle?.(node, { open, searching: Boolean(term) });
      projectNodes.push(node, ...chats);
      // An open project without a chat offers one; an Undo still pending
      // counts as a chat, so the row does not flicker for its few seconds.
      if (open && !term && !chats.length) projectNodes.push(App.chatProjects.emptyRowFor(project));
    }
    for (const row of free) {
      setClass(row, "in-project", false);
      setClass(row, "is-folded", false);
    }

    const sections = [];
    if (pinned.length) sections.push({ group: PINNED, rows: pinned });
    for (const row of others) {
      const group = groupOf(Number(row.dataset.listTime), now) || TODAY;
      const last = sections[sections.length - 1];
      if (last && last.group.key === group.key) last.rows.push(row);
      else sections.push({ group, rows: [row] });
    }

    // Loading, an empty search and a load error stay above the list;
    // "Load more" stays below it.
    const headings = new Map();
    const leading = [];
    const trailing = [];
    const staleProjects = [];
    for (const node of children) {
      if (isRow(node)) continue;
      if (isProjectNode(node)) {
        if (!projectNodes.includes(node)) staleProjects.push(node);
        continue;
      }
      if (node.classList.contains(HEADING)) {
        if (headings.has(node.dataset.group)) node.remove();
        else headings.set(node.dataset.group, node);
      } else if (node.id === "bookmarksLoadMore") trailing.push(node);
      else leading.push(node);
    }

    const desired = [...leading];
    if (projects.length) {
      const heading = App.chatProjects.heading();
      headings.delete("projects");
      setHidden(heading, !projectNodes.some(node => node.classList.contains("chat-project") && !node.hidden));
      desired.push(heading, ...projectNodes);
    }
    staleProjects.forEach(node => node.remove());
    for (const { group, rows: members } of sections) {
      const heading = headings.get(group.key) || createHeading(group);
      headings.delete(group.key);
      if (heading.textContent !== window.App.t(group.label)) heading.textContent = group.label;
      // A group whose chats a search or an Undo hides says nothing.
      const hidden = !members.some(isShown);
      if (heading.hidden !== hidden) heading.hidden = hidden;
      desired.push(heading, ...members);
    }
    desired.push(...trailing);
    headings.forEach(node => node.remove());

    // Only what is out of place moves. Moving a node takes focus from it,
    // so the focused row (its "…" after Pin) gets it back.
    const active = document.activeElement;
    let moved = false;
    desired.forEach((node, index) => {
      const current = container.children[index] || null;
      if (current === node) return;
      container.insertBefore(node, current);
      moved = true;
    });
    if (moved && active && active !== document.activeElement && active.isConnected && container.contains(active)) {
      active.focus({ preventScroll: true });
    }
  }

  let observer = null;
  function watch() {
    const container = document.getElementById("bookmarksContainer");
    if (!container || observer) return;
    // Rows coming and going, and a row hidden or shown (search, Undo); not
    // what happens inside a row (a run's status words, a title settling).
    observer = new MutationObserver(records => {
      if (records.some(record => record.target === container || record.target.parentElement === container)) sync();
    });
    observer.observe(container, { childList: true, subtree: true, attributes: true, attributeFilter: ["class", "style", "hidden"] });
    sync();
  }

  // "Today" turns into "Yesterday" at midnight, also in a window left open.
  function scheduleMidnight() {
    const now = new Date();
    const next = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 5).getTime();
    window.setTimeout(() => {
      sync();
      scheduleMidnight();
    }, next - now.getTime());
  }
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) sync();
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch, { once: true });
  else watch();
  scheduleMidnight();

  // The project a chat row stands in (filterBookmarks searches its name).
  function projectOfRow(row) {
    const known = new Set((App.chatProjects?.ordered?.() || []).map(project => project.id));
    const meta = (window.bookmarksData || []).find(item => item?.id === row?.dataset?.id);
    return row ? projectOf(row, meta, known) : null;
  }

  App.chatList = Object.freeze({ sync, groupOf, toTime, projectOf: projectOfRow });
})();
