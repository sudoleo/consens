// =====================================================================
// chat-projects.js
// App.chatProjects: the account's projects, named groups of chats in the
// sidebar (app/services/chat_projects.py). A project chat stands under its
// project and nowhere else; chat-list.js puts every row in its place, this
// module keeps the projects, draws their rows and does what is done with
// them: open and close, make (the "+" on the heading, or "New project" in a
// chat's "Move to project"), rename, delete with Undo, move a chat in or
// out, and start a new chat in a project (agent-chat.js sends the armed
// project with the chat's first message; the server files the chat).
//
// A deleted project takes none of its chats along: they go back under
// their dates. Nothing here counts or labels: a closed project is one row.
//
// Exports: window.App.chatProjects
//   adopt(list)          the first page's projects (firebase.js); resolves
//                        once the open projects' chats are in, or soon after
//   ordered()            the projects newest first, as chat-list.js places them
//   known(id), nameOf(id), isOpen(id)
//   rowFor(project), emptyRowFor(project), heading(), syncToggle(node, state)
//   showPicker({menu, button, row, meta, keyboard, close})
//                        the chat menu's "Move to project" (firebase.js)
//   move(bookmarkId, projectId, {keyboard})   in (an id) or out (null), with Undo
//   armed(), arm(id), disarm()   the project a new chat starts in
//   reset()              logout
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};

  const OPEN_KEY = "projects_open";
  const UNDO_MS = 5000;
  // An open project is whole when the list first shows: its chats are asked
  // for with the first page, and the list waits for them this long at most.
  const FIRST_PAINT_WAIT_MS = 600;
  const FIRST_PAINT_PROJECTS = 3;
  // Rows that open or close with their project move softly; past these the
  // rest just appear, a long project would otherwise slide for a while.
  const SOFT_ROWS = 16;
  const NAME_CHARS = 80;
  const DRAFT = "__draft";

  const FOLDER = "M3.5 7.5a2 2 0 0 1 2-2h3.7a2 2 0 0 1 1.6.8l.9 1.2H18.5a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z";
  const FOLDER_OPEN = "M3.5 16.5v-9a2 2 0 0 1 2-2h3.7a2 2 0 0 1 1.6.8l.9 1.2h5.8a2 2 0 0 1 2 2v1M3.5 16.5l2.3-4.9a2 2 0 0 1 1.8-1.1h12.3a1.4 1.4 0 0 1 1.3 2l-2.2 4.9a2 2 0 0 1-1.8 1.1H5.5a2 2 0 0 1-2-2Z";
  const ICONS = Object.freeze({
    move: FOLDER,
    add: FOLDER + "M12 10.5v5M9.5 13h5",
    remove: FOLDER + "M9.5 13h5",
    check: "M5 12.5l4.5 4.5L19 7.5",
    newChat: "M12 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6M17.4 3.6a1.8 1.8 0 0 1 2.6 2.6L11.6 14.6 8 16l1.4-3.6Z",
    rename: "M4 20h4L19 9l-4-4L4 16v4ZM14 6l4 4",
    delete: "M5 7h14M10 7V5h4v2m-6 0 1 12h6l1-12",
  });
  const MENU_ICON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><circle cx="5.5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18.5" cy="12" r="1.6"/></svg>';

  let projects = [];               // as the server keeps them: oldest first
  let open = readOpen();           // ids of the open projects (this browser)
  const loaded = new Set();        // projects whose chats came this list load
  const loading = new Map();       // id -> promise of its chats
  const pendingDeletes = new Map(); // id -> {project, notice, members}
  const rows = new Map();          // id -> .chat-project
  const empties = new Map();       // id -> .chat-project-empty
  let headingNode = null;
  let draft = null;                // {node, input} while "+" names a new project
  let armedId = null;
  let quietNewChat = false;
  let openMenu = null;

  // ---- State ---------------------------------------------------------------

  function readOpen() {
    try {
      const ids = JSON.parse(window.localStorage.getItem(OPEN_KEY) || "[]");
      return new Set(Array.isArray(ids) ? ids.filter(id => typeof id === "string") : []);
    } catch (_) {
      return new Set();
    }
  }
  function saveOpen() {
    try {
      window.localStorage.setItem(OPEN_KEY, JSON.stringify([...open]));
    } catch (_) { /* this page keeps it */ }
  }

  function clean(list) {
    const seen = new Set();
    return (Array.isArray(list) ? list : []).filter(project => project && typeof project.id === "string"
      && typeof project.name === "string" && project.name && !seen.has(project.id) && seen.add(project.id))
      .map(project => ({ id: project.id, name: project.name, created_at: project.created_at || "" }));
  }

  function find(id) {
    return projects.find(project => project.id === id) || null;
  }
  function known(id) {
    return Boolean(id) && Boolean(find(id)) && !pendingDeletes.has(id);
  }
  function nameOf(id) {
    return find(id)?.name || "";
  }
  function isOpen(id) {
    return open.has(id);
  }
  function ordered() {
    const list = projects.filter(project => !pendingDeletes.has(project.id)).reverse();
    return draft ? [{ id: DRAFT, name: draft.input.value, draft: true }, ...list] : list;
  }
  function metaOf(bookmarkId) {
    return (window.bookmarksData || []).find(item => item?.id === bookmarkId) || null;
  }
  function membersOf(id) {
    return (window.bookmarksData || []).filter(item => item?.project_id === id);
  }
  function sync() {
    App.chatList?.sync?.();
  }
  function cssValue(value) {
    return window.CSS?.escape ? window.CSS.escape(String(value)) : String(value).replace(/["\\]/g, "\\$&");
  }

  // ---- Requests ------------------------------------------------------------

  function stale(user, generation) {
    return window.auth?.currentUser !== user || App.authState?.generation !== generation;
  }

  async function call(method, path, body) {
    const user = window.auth?.currentUser;
    if (!user) throw Object.assign(new Error("Authentication required"), { stale: true });
    const generation = App.authState?.generation;
    const token = await user.getIdToken(false);
    if (stale(user, generation)) throw Object.assign(new Error("Account changed"), { stale: true });
    const response = await fetch(path, {
      method,
      headers: { Authorization: "Bearer " + token, ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const data = await response.json().catch(() => ({}));
    if (stale(user, generation)) throw Object.assign(new Error("Account changed"), { stale: true });
    if (!response.ok) {
      throw Object.assign(new Error(data.detail || `Request failed (${response.status})`),
        { status: response.status, detail: data.detail || "" });
    }
    return data;
  }

  function popup(text) {
    App.showPopup?.(text);
  }

  // The server no longer has it (another tab deleted it): it goes here too.
  function forget(id) {
    projects = projects.filter(project => project.id !== id);
    open.delete(id);
    saveOpen();
    if (armedId === id) disarm();
    sync();
  }
  function gone(error) {
    return error?.status === 404 && error.detail === "Project not found";
  }

  // ---- Rows (chat-list.js places them) ---------------------------------------

  function glyph() {
    return `<svg class="chat-project-glyph" viewBox="0 0 24 24" aria-hidden="true"><path class="when-closed" d="${FOLDER}"/><path class="when-open" d="${FOLDER_OPEN}"/></svg>`;
  }

  function heading() {
    if (headingNode) return headingNode;
    headingNode = document.createElement("div");
    headingNode.className = "chat-list-heading chat-projects-heading";
    headingNode.dataset.group = "projects";
    const title = document.createElement("h3");
    title.textContent = "Projects";
    const add = document.createElement("button");
    add.type = "button";
    add.className = "chat-projects-add";
    add.setAttribute("aria-label", "New project");
    add.setAttribute("data-tooltip", "New project");
    add.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5.5v13M5.5 12h13"/></svg>';
    headingNode.append(title, add);
    return headingNode;
  }

  function rowFor(project) {
    if (project.draft) return draft.node;
    let node = rows.get(project.id);
    if (!node) {
      node = document.createElement("div");
      node.className = "chat-project";
      node.dataset.projectId = project.id;
      node.innerHTML = glyph();
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "chat-project-toggle";
      toggle.setAttribute("aria-expanded", "false");
      const name = document.createElement("span");
      name.className = "chat-project-name";
      // A name is the person's word: a project called "Settings" stays so.
      name.setAttribute("data-i18n-skip", "");
      name.setAttribute("data-tooltip-overflow", "");
      toggle.append(name);
      const more = document.createElement("button");
      more.type = "button";
      more.className = "bookmark-menu-button";
      more.innerHTML = MENU_ICON;
      more.setAttribute("aria-haspopup", "menu");
      more.setAttribute("aria-expanded", "false");
      more.title = "More";
      node.append(toggle, more);
      rows.set(project.id, node);
    }
    const name = node.querySelector(".chat-project-name");
    if (name.textContent !== project.name) {
      name.textContent = project.name;
      node.querySelector(".bookmark-menu-button")
        .setAttribute("aria-label", App.t("Project options: {name}", { name: project.name }));
    }
    return node;
  }

  function syncToggle(node, { open: isOpenNow, searching }) {
    const toggle = node.querySelector(":scope > .chat-project-toggle");
    if (!toggle) return;
    const expanded = String(Boolean(isOpenNow));
    if (toggle.getAttribute("aria-expanded") !== expanded) toggle.setAttribute("aria-expanded", expanded);
    // While a search shows every project open, a toggle would change nothing.
    if (searching !== toggle.hasAttribute("aria-disabled")) {
      if (searching) toggle.setAttribute("aria-disabled", "true");
      else toggle.removeAttribute("aria-disabled");
    }
  }

  function emptyRowFor(project) {
    let node = empties.get(project.id);
    if (!node) {
      node = document.createElement("button");
      node.type = "button";
      node.className = "chat-project-empty";
      node.dataset.projectId = project.id;
      node.textContent = "New chat";
      empties.set(project.id, node);
    }
    const label = App.t("New chat in {name}", { name: project.name });
    if (node.getAttribute("aria-label") !== label) node.setAttribute("aria-label", label);
    return node;
  }

  // ---- Motion --------------------------------------------------------------

  function quiet() {
    return Boolean(App.motion?.reduced?.()) || !Element.prototype.animate;
  }
  function softly(nodes) {
    if (quiet()) return;
    nodes.filter(node => node.isConnected && node.getClientRects().length).slice(0, SOFT_ROWS)
      .forEach(node => App.bookmarkUi?.insertSoftly?.(node));
  }
  // Rows fold to nothing, then `done` takes them out of the list.
  function fold(nodes, done) {
    const shown = nodes.filter(node => node.isConnected && node.getClientRects().length).slice(0, SOFT_ROWS);
    if (quiet() || !shown.length) { done(); return; }
    const animations = shown.map(node => {
      const style = getComputedStyle(node);
      node.style.overflow = "hidden";
      return node.animate([
        { height: `${node.getBoundingClientRect().height}px`, opacity: 1, paddingTop: style.paddingTop,
          paddingBottom: style.paddingBottom, marginBottom: style.marginBottom },
        { height: "0px", opacity: 0, paddingTop: "0px", paddingBottom: "0px", marginBottom: "0px" },
      ], { duration: App.motion?.ms?.("state") ?? 200, easing: App.motion?.ease?.("out") ?? "ease-out" });
    });
    Promise.all(animations.map(animation => animation.finished.catch(() => {}))).then(() => {
      done();
      shown.forEach(node => node.style.removeProperty("overflow"));
      animations.forEach(animation => animation.cancel());
    });
  }
  // Safari has no scroll anchoring: a group growing above the visible rows
  // would push them down. Elsewhere the browser keeps them in place itself.
  function keepScroll(change) {
    const scroller = document.querySelector(".sidebar-content");
    if (!scroller || window.CSS?.supports?.("overflow-anchor", "auto")) { change(); return; }
    const top = scroller.getBoundingClientRect().top;
    const anchor = [...document.querySelectorAll("#bookmarksContainer > *")]
      .find(node => node.getClientRects().length && node.getBoundingClientRect().bottom > top);
    const before = anchor?.getBoundingClientRect().top;
    change();
    if (anchor?.isConnected && anchor.getClientRects().length) {
      const delta = anchor.getBoundingClientRect().top - before;
      if (delta) scroller.scrollTop += delta;
    }
  }

  function chatRows(id) {
    return [...document.querySelectorAll("#bookmarksContainer .bookmark")]
      .filter(row => App.chatList?.projectOf?.(row) === id);
  }

  // ---- Chats of a project --------------------------------------------------

  function fetchChats(id, { quietly = false } = {}) {
    if (loaded.has(id)) return Promise.resolve();
    if (loading.has(id)) return loading.get(id);
    const request = call("GET", `/projects/${encodeURIComponent(id)}/bookmarks`).then(data => {
      loaded.add(id);
      App.bookmarkUi?.addListRows?.(data.bookmarks || []);
    }).catch(error => {
      if (error.stale) return;
      if (gone(error)) { forget(id); if (!quietly) popup("That project no longer exists."); return; }
      console.warn("Project chats failed:", error);
      if (!quietly) popup("This project’s chats couldn’t be loaded. Try again.");
    }).finally(() => loading.delete(id));
    loading.set(id, request);
    return request;
  }

  // The first page brings the projects; the open ones bring their chats
  // before the list fades in (firebase.js waits on this), so an open project
  // never fills up under the reader's eyes.
  function adopt(list) {
    projects = clean(list);
    loaded.clear();
    const wanted = ordered().filter(project => !project.draft && open.has(project.id));
    const first = wanted.slice(0, FIRST_PAINT_PROJECTS).map(project => fetchChats(project.id, { quietly: true }));
    wanted.slice(FIRST_PAINT_PROJECTS).forEach(project => fetchChats(project.id, { quietly: true }));
    if (!first.length) return Promise.resolve();
    return Promise.race([
      Promise.allSettled(first),
      new Promise(resolve => window.setTimeout(resolve, FIRST_PAINT_WAIT_MS)),
    ]);
  }

  function toggle(id) {
    if (!known(id)) return;
    if (open.has(id)) {
      const nodes = [...chatRows(id), empties.get(id)].filter(Boolean);
      fold(nodes, () => {
        open.delete(id);
        saveOpen();
        sync();
      });
      return;
    }
    open.add(id);
    saveOpen();
    sync();
    const empty = empties.get(id);
    softly([...chatRows(id), ...(empty?.isConnected ? [empty] : [])]);
    fetchChats(id);
  }

  // ---- Moving a chat ---------------------------------------------------------

  async function move(bookmarkId, projectId, { keyboard = false, undo = true } = {}) {
    const entry = metaOf(bookmarkId);
    if (!entry || !window.auth?.currentUser) return false;
    const before = known(entry.project_id) ? entry.project_id : null;
    if (before === projectId) return true;
    const apply = value => keepScroll(() => {
      entry.project_id = value;
      sync();
    });
    apply(projectId);
    const row = document.querySelector(`#bookmarksContainer .bookmark:not(.run-entry)[data-id="${cssValue(bookmarkId)}"]`);
    if (row && !row.classList.contains("is-folded")) softly([row]);
    try {
      const data = await call("PATCH", `/bookmarks/${encodeURIComponent(bookmarkId)}/project`, { project_id: projectId });
      if (data.bookmark && "project_id" in data.bookmark) entry.project_id = data.bookmark.project_id ?? null;
    } catch (error) {
      if (error.stale) return false;
      apply(before);
      if (projectId && gone(error)) { forget(projectId); popup("That project no longer exists."); }
      else popup("This chat couldn’t be moved. Try again.");
      return false;
    }
    if (!undo || !App.undoNotice?.show) return true;
    const text = projectId ? App.t("Moved to {name}", { name: nameOf(projectId) })
      : App.t("Removed from {name}", { name: nameOf(before) });
    const notice = App.undoNotice.show({
      text,
      actionLabel: "Undo",
      duration: UNDO_MS,
      onAction() {
        move(bookmarkId, before, { undo: false });
        if (keyboard) {
          document.querySelector(`#bookmarksContainer .bookmark[data-id="${cssValue(bookmarkId)}"] .bookmark-menu-button`)
            ?.focus({ preventScroll: true });
        }
      },
    });
    if (keyboard) notice?.focusAction?.();
    return true;
  }

  async function create(name) {
    const data = await call("POST", "/projects", { name });
    const project = clean([data.project])[0];
    if (!project) throw new Error("No project came back");
    projects.push(project);
    // A new project holds only what moves into it here: nothing to fetch.
    loaded.add(project.id);
    open.add(project.id);
    saveOpen();
    return project;
  }
  function createFailed(error) {
    if (error.stale) return;
    console.warn("Project create failed:", error);
    popup(error.status === 409 && error.detail ? error.detail : "The project couldn’t be created. Try again.");
  }

  // ---- The picker in the chat menu ---------------------------------------------
  // Not a submenu: one popover is open at a time and a phone has no hover.
  // "Move to project" fills the same menu with the projects instead.

  function menuItem(icon, label, { role = "menuitem", checked = null, content = false } = {}) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "bookmark-menu-item";
    item.setAttribute("role", role);
    item.tabIndex = -1;
    item.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${icon}"/></svg>`;
    const text = document.createElement("span");
    text.textContent = label;
    if (content) text.setAttribute("data-i18n-skip", "");
    item.append(text);
    if (checked !== null) {
      item.setAttribute("aria-checked", String(checked));
      item.insertAdjacentHTML("beforeend",
        `<svg class="bookmark-menu-check" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS.check}"/></svg>`);
    }
    return item;
  }

  function place(menu, button) {
    const bounds = button.getBoundingClientRect();
    const width = menu.offsetWidth, height = menu.offsetHeight;
    const below = bounds.bottom + 4 + height <= window.innerHeight - 8;
    menu.style.left = `${Math.max(8, Math.min(bounds.right - width, window.innerWidth - width - 8))}px`;
    menu.style.top = `${below ? bounds.bottom + 4 : Math.max(8, bounds.top - 4 - height)}px`;
    menu.classList.toggle("opens-up", !below);
  }

  function showPicker({ menu, button, row, meta, keyboard = false, close }) {
    if (!menu || !meta?.id) return;
    const current = known(meta.project_id) ? meta.project_id : null;
    const choices = ordered().filter(project => !project.draft);
    menu.classList.add("is-project-picker");
    menu.setAttribute("aria-label", "Move to project");
    const parts = [];
    if (choices.length) {
      const list = document.createElement("div");
      list.className = "bookmark-menu-list";
      for (const project of choices) {
        const item = menuItem(ICONS.move, project.name, { role: "menuitemradio", checked: project.id === current, content: true });
        item.addEventListener("click", event => {
          event.stopPropagation();
          close({ focus: true });
          if (project.id !== current) move(meta.id, project.id, { keyboard: keyboard || event.detail === 0 });
        });
        list.append(item);
      }
      const divider = document.createElement("div");
      divider.className = "bookmark-menu-divider";
      divider.setAttribute("role", "separator");
      parts.push(list, divider);
    }
    const fresh = menuItem(ICONS.add, "New project");
    fresh.addEventListener("click", event => {
      event.stopPropagation();
      nameInMenu();
    });
    parts.push(fresh);
    menu.replaceChildren(...parts);

    // "New project" becomes a field in its place: Enter makes the project
    // and moves the chat into it, Escape gives the item back.
    function nameInMenu() {
      const field = document.createElement("div");
      field.className = "bookmark-menu-field";
      field.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS.add}"/></svg>`;
      const input = document.createElement("input");
      input.type = "text";
      input.maxLength = NAME_CHARS;
      input.placeholder = "Project name";
      input.setAttribute("aria-label", "Project name");
      input.setAttribute("enterkeyhint", "done");
      input.autocomplete = "off";
      input.spellcheck = false;
      field.append(input);
      fresh.replaceWith(field);
      place(menu, button);
      input.focus({ preventScroll: true });
      input.addEventListener("keydown", event => {
        if (["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) { event.stopPropagation(); return; }
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          if (!choices.length) { close({ focus: true }); return; }
          field.replaceWith(fresh);
          place(menu, button);
          fresh.focus({ preventScroll: true });
          return;
        }
        if (event.key !== "Enter" || event.isComposing || event.keyCode === 229) return;
        event.preventDefault();
        event.stopPropagation();
        const name = input.value.replace(/\s+/g, " ").trim();
        if (!name) return;
        close({ focus: true });
        const chatRow = row?.isConnected ? row : null;
        chatRow?.classList.add("is-loading");
        create(name).then(project => move(meta.id, project.id, { keyboard })).catch(createFailed)
          .finally(() => chatRow?.classList.remove("is-loading"));
      });
    }

    place(menu, button);
    if (!choices.length) { nameInMenu(); return; }
    const items = [...menu.querySelectorAll(".bookmark-menu-item")];
    (items.find(item => item.getAttribute("aria-checked") === "true") || items[0])?.focus({ preventScroll: true });
  }

  // ---- A project's own menu ------------------------------------------------------

  function closeMenu({ focus = false } = {}) {
    if (!openMenu) return;
    const { menu, button, node } = openMenu;
    openMenu = null;
    if (App.popover) {
      App.popover.leave(menu, () => {
        App.popover.unregister(menu);
        menu.remove();
      });
    } else menu.remove();
    button.setAttribute("aria-expanded", "false");
    node.classList.remove("has-menu");
    if (focus && button.isConnected) button.focus({ preventScroll: true });
  }

  function showMenu(button, { keyboard = false } = {}) {
    closeMenu();
    const node = button.closest(".chat-project");
    const id = node?.dataset.projectId;
    if (!known(id)) return;
    const menu = document.createElement("div");
    menu.className = "bookmark-menu";
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", App.t("Project options: {name}", { name: nameOf(id) }));
    const entries = [["new", ICONS.newChat, "New chat"], ["rename", ICONS.rename, "Rename"], ["delete", ICONS.delete, "Delete project"]];
    for (const [action, icon, label] of entries) {
      const item = menuItem(icon, label);
      item.dataset.action = action;
      if (action === "delete") item.classList.add("is-destructive");
      menu.append(item);
    }
    App.popover?.register(menu, { close: () => closeMenu() });
    App.popover?.opened(menu, { trigger: button });
    App.popover?.menuKeys?.(menu, { close: options => closeMenu(options), opener: button });
    document.body.append(menu);
    place(menu, button);
    button.setAttribute("aria-expanded", "true");
    node.classList.add("has-menu");
    openMenu = { menu, button, node };
    menu.addEventListener("click", event => {
      const item = event.target.closest(".bookmark-menu-item");
      if (!item) return;
      event.stopPropagation();
      const fromKeys = keyboard || event.detail === 0;
      closeMenu({ focus: item.dataset.action === "new" ? false : item.dataset.action !== "rename" && item.dataset.action !== "delete" });
      if (item.dataset.action === "new") newChatIn(id);
      else if (item.dataset.action === "rename") startRename(id);
      else if (item.dataset.action === "delete") remove(id, { keyboard: fromKeys });
    });
    menu.tabIndex = -1;
    const items = [...menu.querySelectorAll(".bookmark-menu-item")];
    if (keyboard) items[0]?.focus({ preventScroll: true });
    else menu.focus({ preventScroll: true });
  }

  document.addEventListener("pointerdown", event => {
    if (openMenu && !openMenu.menu.contains(event.target) && !openMenu.button.contains(event.target)) closeMenu();
  }, true);
  window.addEventListener("resize", () => closeMenu(), { passive: true });
  document.addEventListener("scroll", event => {
    if (openMenu && event.target instanceof Element && event.target.contains(openMenu.node)) closeMenu();
  }, { passive: true, capture: true });

  // ---- Naming: rename in place, and "+" ------------------------------------------

  function nameField(value) {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "bookmark-rename-input";
    input.value = value;
    input.maxLength = NAME_CHARS;
    input.placeholder = "Project name";
    input.setAttribute("aria-label", "Project name");
    input.setAttribute("enterkeyhint", "done");
    input.autocomplete = "off";
    input.spellcheck = false;
    return input;
  }

  // Enter or leaving it ends the field (save), Escape keeps what was there.
  function onFinish(input, finish) {
    let finished = false;
    const end = save => {
      if (finished) return;
      finished = true;
      finish(save, input.value.replace(/\s+/g, " ").trim());
    };
    input.addEventListener("keydown", event => {
      event.stopPropagation();
      if (event.key === "Enter" && !(event.isComposing || event.keyCode === 229)) { event.preventDefault(); end(true); }
      else if (event.key === "Escape") { event.preventDefault(); end(false); }
    });
    input.addEventListener("blur", () => end(true));
  }

  function startRename(id) {
    const node = rows.get(id);
    const project = find(id);
    if (!node || !project || node.classList.contains("is-renaming")) return;
    const toggleButton = node.querySelector(".chat-project-toggle");
    const input = nameField(project.name);
    node.classList.add("is-renaming");
    toggleButton.after(input);
    input.focus({ preventScroll: true });
    input.select();
    onFinish(input, async (save, name) => {
      input.remove();
      node.classList.remove("is-renaming");
      if (document.activeElement === document.body || !document.activeElement) toggleButton.focus({ preventScroll: true });
      if (!save || !name || name === project.name) return;
      const previous = project.name;
      project.name = name;
      rowFor(project);
      syncHero();
      try {
        const data = await call("PATCH", `/projects/${encodeURIComponent(id)}`, { name });
        if (data.project?.name) project.name = data.project.name;
      } catch (error) {
        if (error.stale) return;
        if (gone(error)) { forget(id); popup("That project no longer exists."); return; }
        project.name = previous;
        popup("This project couldn’t be renamed. Try again.");
      }
      rowFor(project);
      syncHero();
    });
  }

  function startDraft() {
    if (draft) { draft.input.focus({ preventScroll: true }); return; }
    const node = document.createElement("div");
    node.className = "chat-project is-open is-renaming is-draft";
    node.innerHTML = glyph();
    const input = nameField("");
    node.append(input);
    draft = { node, input };
    keepScroll(sync);
    softly([node]);
    input.focus({ preventScroll: true });
    onFinish(input, (save, name) => {
      if (!save || !name) {
        draft = null;
        sync();
        heading().querySelector(".chat-projects-add")?.focus({ preventScroll: true });
        return;
      }
      input.disabled = true;
      node.classList.add("is-loading");
      create(name).then(project => {
        draft = null;
        sync();
        rows.get(project.id)?.querySelector(".chat-project-toggle")?.focus({ preventScroll: true });
      }).catch(error => {
        draft = null;
        sync();
        createFailed(error);
      });
    });
  }

  // ---- Deleting, with Undo -----------------------------------------------------------

  function remove(id, { keyboard = false } = {}) {
    const project = find(id);
    if (!project || pendingDeletes.has(id)) return;
    if (armedId === id) disarm();
    const empty = loaded.has(id) && !membersOf(id).length;
    const node = rows.get(id);
    fold([node, empties.get(id)].filter(Boolean), () => {
      const entry = { project, promise: null };
      pendingDeletes.set(id, entry);
      keepScroll(sync);
      softly(chatRows(null).filter(row => membersOf(id).some(meta => meta.id === row.dataset.id)));
      if (!App.undoNotice?.show) { entry.promise = send(id, entry); return; }
      entry.notice = App.undoNotice.show({
        text: empty ? "Project deleted" : "Project deleted. Its chats stay.",
        actionLabel: "Undo",
        duration: UNDO_MS,
        onAction() {
          pendingDeletes.delete(id);
          keepScroll(sync);
          softly([rows.get(id), ...chatRows(id)].filter(Boolean));
          if (keyboard) rows.get(id)?.querySelector(".chat-project-toggle")?.focus({ preventScroll: true });
        },
        onExpire() {
          entry.promise = send(id, entry);
        },
      });
      if (keyboard) entry.notice?.focusAction?.();
    });
  }

  async function send(id, entry) {
    const members = membersOf(id);
    // Its chats stay where Undo left them: under their dates.
    members.forEach(meta => { meta.project_id = null; });
    projects = projects.filter(project => project.id !== id);
    pendingDeletes.delete(id);
    open.delete(id);
    saveOpen();
    rows.delete(id);
    empties.delete(id);
    sync();
    try {
      await call("DELETE", `/projects/${encodeURIComponent(id)}`);
    } catch (error) {
      if (error.stale || gone(error)) return;
      console.warn("Project delete failed:", error);
      projects.push(entry.project);
      members.forEach(meta => { meta.project_id = id; });
      sync();
      popup("This project couldn’t be deleted. Try again.");
    }
  }

  function settleDeletes() {
    const entries = [...pendingDeletes.values()];
    entries.forEach(entry => entry.notice?.settle?.());
    return Promise.allSettled(entries.map(entry => entry.promise).filter(Boolean));
  }
  window.addEventListener("consensio:run-registry-change", event => {
    if (event.detail?.type === "created" && pendingDeletes.size) settleDeletes();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && pendingDeletes.size) settleDeletes();
  });

  // ---- A new chat in a project ---------------------------------------------------
  // "New chat" of a project starts a new chat as the sidebar's own button
  // does and remembers the project: the chat's first message carries it
  // (agent-chat.js), so the chat is filed there even if this tab closes.

  function syncHero() {
    const name = document.getElementById("heroProjectName");
    const text = armedId ? nameOf(armedId) : "";
    if (name && name.textContent !== text) name.textContent = text;
  }

  function arm(id) {
    if (!known(id)) return;
    armedId = id;
    if (App.temporaryChat?.armed?.()) App.temporaryChat.arm?.(false);
    if (!open.has(id)) {
      open.add(id);
      saveOpen();
      fetchChats(id);
    }
    document.body.classList.add("project-armed");
    syncHero();
    sync();
  }

  function disarm() {
    if (!armedId) return;
    armedId = null;
    document.body.classList.remove("project-armed");
    syncHero();
    sync();
  }

  function newChatIn(id) {
    if (!known(id)) return;
    quietNewChat = true;
    try {
      document.getElementById("newRunButton")?.click();
    } finally {
      quietNewChat = false;
    }
    arm(id);
  }

  // The sidebar's plain "New chat" is a chat in no project.
  document.addEventListener("click", event => {
    if (!quietNewChat && event.target.closest?.("#newRunButton")) disarm();
  }, true);
  // Opening another chat leaves the new one; a temporary chat is in no project.
  window.addEventListener("consensio:run-registry-change", event => {
    if (["visible", "saved-view"].includes(event.detail?.type)) disarm();
  });
  window.addEventListener("consensio:temporary-chat", event => {
    if (event.detail?.armed) disarm();
  });

  // ---- The list's own clicks -----------------------------------------------------------

  document.addEventListener("click", event => {
    const container = document.getElementById("bookmarksContainer");
    if (!container?.contains(event.target)) return;
    if (event.target.closest(".chat-projects-add")) { event.stopPropagation(); startDraft(); return; }
    const empty = event.target.closest(".chat-project-empty");
    if (empty) { newChatIn(empty.dataset.projectId); return; }
    const node = event.target.closest(".chat-project");
    if (!node || node.classList.contains("is-draft") || node.classList.contains("is-renaming")) return;
    const more = event.target.closest(".bookmark-menu-button");
    if (more) {
      event.stopPropagation();
      if (openMenu?.button === more) closeMenu();
      else showMenu(more, { keyboard: event.detail === 0 });
      return;
    }
    const toggleButton = node.querySelector(".chat-project-toggle");
    if (toggleButton?.getAttribute("aria-disabled") === "true") return;
    toggle(node.dataset.projectId);
  });

  function reset() {
    settleDeletes();
    closeMenu();
    projects = [];
    loaded.clear();
    loading.clear();
    pendingDeletes.clear();
    rows.clear();
    empties.clear();
    draft = null;
    disarm();
  }

  App.chatProjects = Object.freeze({
    adopt, ordered, known, nameOf, isOpen, rowFor, emptyRowFor, heading, syncToggle,
    showPicker, move, armed: () => armedId, arm, disarm, reset, icons: ICONS,
  });
})();
