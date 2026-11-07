// =====================================================================
// temporary-chat.js
// Temporary chats: an Agent chat that is not in the user's chats and is not
// kept. It does what the account's other chats do (workspace, Watch, chat
// search, memory read),
// but saves nothing to memory and cannot be shared. The server knows it by
// its chat (POST /chats with temporary: true, chat_store.create_chat) and
// writes no bookmark and no memory for it (routers/agent.py). This module is the
// browser's half: the switch at the top right of a new Agent chat, the
// words and the dashed field that say a chat is temporary, and its end.
//
// A temporary chat lives in its tab. It ends when the user leaves it (New
// chat, another chat, logout: whatever takes it off the screen in the run
// registry) or reloads the page: the server deletes it (DELETE /chats/{id},
// keepalive). A tab closed without either leaves it to the server's
// deadline (chat_store.TEMPORARY_CHAT_TTL after its last message). Its id
// stays in this tab's sessionStorage only so that a reload can delete it.
//
// Exports: window.App.temporaryChat
//   armed()        whether the next new Agent chat is temporary (the switch)
//   arm(on)        sets the switch (a new chat only)
//   start()        a new temporary chat begins: its token (agent-chat.js send)
//   token(chatId)  the token of the temporary chat ``chatId``, or ""
//   adopt(token, chatId)  the server created it; false when it was left meanwhile
//   current()      {token, chatId} of the temporary chat of this tab, or null
//   shown()        a temporary chat (or the armed switch) is on screen
//   leave(reason)  ends it: its runs stop, the server deletes it (a promise)
//   sync()         redraws the switch and the words (agent-mode.js)
// Event: "consensio:temporary-chat" on window, detail {armed, chatId}
// =====================================================================

(function () {
  "use strict";
  const App = window.App = window.App || {};
  const KEY = "consens.temporaryChat.v1";
  // The switch, for this tab: a guest's sign-in reloads the page before the
  // waiting question goes out (composer-invite.js), and it must go out
  // temporary as chosen.
  const ARMED_KEY = "consens.temporaryChat.armed.v1";
  // The run registry's changes after which the screen may show another chat.
  const VIEW_CHANGES = new Set(["created", "visible", "saved-view", "visible-cleared", "cleared"]);
  // How long a page that loads with a chat id waits for another tab to say
  // it still has that chat open (a duplicated tab), before deleting it.
  const PEER_WAIT_MS = 400;
  // The DELETE of a chat left behind: at once, then twice more after these
  // pauses (an outage, a busy server). Its run stops once the chat is gone
  // (the run's watcher); what never arrives, the deadline deletes.
  const DELETE_RETRIES_MS = [0, 2000, 8000];
  let armed = (() => {
    try { return window.sessionStorage.getItem(ARMED_KEY) === "1"; } catch (_) { return false; }
  })();
  function keepArmed() {
    try {
      if (armed) window.sessionStorage.setItem(ARMED_KEY, "1");
      else window.sessionStorage.removeItem(ARMED_KEY);
    } catch (_) { /* this page keeps it */ }
  }
  // The temporary chat of this tab: a token from its first message on, its
  // id once the server created it, the account it belongs to.
  let session = null;

  function stored() {
    try { return JSON.parse(window.sessionStorage.getItem(KEY) || "null"); } catch (_) { return null; }
  }
  function store(value) {
    try {
      if (value) window.sessionStorage.setItem(KEY, JSON.stringify(value));
      else window.sessionStorage.removeItem(KEY);
    } catch (_) { /* the server's deadline deletes it */ }
  }
  function randomToken() {
    const uuid = window.crypto?.randomUUID?.();
    return uuid ? uuid.replace(/-/g, "") : `${Date.now().toString(36)}${Math.random().toString(16).slice(2)}`;
  }

  // The server deletes the chat (chat_history.delete_chat): its turns, files,
  // work logs and the texts of its receipts. Only with its own account's
  // token; another account signed in meanwhile leaves it to the deadline.
  async function remove(chatId, uid) {
    for (const pause of DELETE_RETRIES_MS) {
      const user = window.auth?.currentUser;
      if (!chatId || !user || (uid && user.uid !== uid)) return false;
      if (pause) await new Promise(resolve => setTimeout(resolve, pause));
      try {
        const token = await user.getIdToken();
        const response = await fetch(`/chats/${encodeURIComponent(chatId)}`, {
          method: "DELETE", keepalive: true, headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok || response.status === 404) return true;
        // A refusal for good (not the owner): no further attempt helps.
        if (response.status < 500 && response.status !== 429 && response.status !== 408) return false;
      } catch (_) { /* offline for a moment: the next attempt */ }
    }
    return false;
  }

  function emit() {
    window.dispatchEvent(new CustomEvent("consensio:temporary-chat",
      { detail: { armed, chatId: session?.chatId || "" } }));
    sync();
    // The field's words ("Ask in a temporary chat", agent-chat.js).
    App.agentChat?.syncComposer?.();
  }

  function registry() { return App.runRegistry || null; }

  // A new chat on screen: nothing visible, no chat chosen.
  function newChatShown() {
    const runs = registry();
    return Boolean(runs && !runs.visible() && !runs.getSelectedConversationIdentity());
  }

  // Known to be signed out: a guest has no switch (it comes with the
  // account), so a tab that loses its account (a logout in another tab, an
  // expired session) does not stay armed without a way to turn it off.
  function guest() {
    const state = window.__consensioAuthState;
    return Boolean(state?.known && !state.uid);
  }

  function arm(on) {
    const next = Boolean(on) && !session && !guest();
    if (next === armed) return;
    armed = next;
    keepArmed();
    App.trackAppEvent?.("app_temporary_chat", { on: armed });
    emit();
  }

  function start() {
    if (session) leave("new_temporary");
    session = { token: randomToken(), chatId: "", uid: window.auth?.currentUser?.uid || "" };
    armed = false;
    keepArmed();
    emit();
    return session.token;
  }

  // The temporary chat is on screen with a run of its own, but without an
  // answer to go on from: its first message failed, was stopped or was not
  // sent. The next message is its first again (send() starts it anew).
  function unanswered() {
    return Boolean(session) && registry()?.visible?.()?.metadata?.temporaryToken === session.token;
  }

  function token(chatId) {
    return session && chatId && session.chatId === chatId ? session.token : "";
  }

  function adopt(own, chatId) {
    if (!session || session.token !== own) {
      // Left while the server created it: it goes at once.
      remove(chatId, window.auth?.currentUser?.uid || "");
      return false;
    }
    // A retry of a first message that failed after its chat was created
    // creates another: the one it replaces goes.
    if (session.chatId && session.chatId !== chatId) remove(session.chatId, session.uid);
    session.chatId = chatId;
    session.uid = window.auth?.currentUser?.uid || session.uid;
    store({ chatId, uid: session.uid });
    emit();
    return true;
  }

  function leave(reason = "left") {
    const ended = session;
    session = null;
    armed = false;
    keepArmed();
    if (!ended) { emit(); return Promise.resolve(false); }
    store(null);
    // Its runs stop here; the server stops them too once the chat is gone
    // (the run's watcher, agent_sessions.check_delegation).
    for (const run of registry()?.list?.() || []) {
      if (run.metadata?.temporaryToken === ended.token) registry().cancel(run.runId, "temporary");
    }
    App.trackAppEvent?.("app_temporary_chat_left", { reason });
    emit();
    return remove(ended.chatId, ended.uid);
  }

  // Whatever takes the temporary chat off the screen ends it: New chat
  // (clearVisible), a saved chat (showSavedView), another run, logout.
  window.addEventListener("consensio:run-registry-change", event => {
    if (!session || !VIEW_CHANGES.has(event.detail?.type)) return;
    const visible = registry()?.visible?.();
    if (visible?.metadata?.temporaryToken === session.token) return;
    leave(event.detail.type === "cleared" ? "logout" : "left");
  });

  // Tabs ask each other before a chat is deleted on load: a duplicated tab
  // copies sessionStorage, and with it the id of a chat its original still
  // has open. That tab answers; a reloaded page is gone and answers nothing.
  const peers = typeof window.BroadcastChannel === "function" ? new window.BroadcastChannel(KEY) : null;
  peers?.addEventListener("message", event => {
    const ask = event.data || {};
    if (ask.type === "who" && session?.chatId && session.chatId === ask.chatId) {
      peers.postMessage({ type: "mine", chatId: ask.chatId });
    }
  });
  function openElsewhere(chatId) {
    if (!peers) return Promise.resolve(false);
    return new Promise(resolve => {
      const answer = event => {
        if (event.data?.type !== "mine" || event.data.chatId !== chatId) return;
        peers.removeEventListener("message", answer);
        clearTimeout(timer);
        resolve(true);
      };
      const timer = setTimeout(() => { peers.removeEventListener("message", answer); resolve(false); }, PEER_WAIT_MS);
      peers.addEventListener("message", answer);
      peers.postMessage({ type: "who", chatId });
    });
  }

  // A reload ends the temporary chat this tab had: once its account is
  // known, the server deletes it, unless another tab still has it open.
  const previous = stored();
  if (previous?.chatId) {
    store(null);
    const onAuth = async event => {
      const state = event.detail || window.__consensioAuthState;
      if (!state?.known) return;
      window.removeEventListener("consensio:auth-state", onAuth);
      if (await openElsewhere(previous.chatId)) return;
      remove(previous.chatId, previous.uid);
    };
    window.addEventListener("consensio:auth-state", onAuth);
    const catchUp = () => { if (window.__consensioAuthState?.known) onAuth({ detail: window.__consensioAuthState }); };
    if (document.readyState === "complete") setTimeout(catchUp, 0);
    else window.addEventListener("load", () => setTimeout(catchUp, 0), { once: true });
  }

  function shown() {
    return Boolean(session) || (armed && newChatShown());
  }

  // The field's dashed rim (shell.css, .composer-dashed-edge): one SVG line
  // just inside the field's edge, in its radius, over a solid one in the
  // page's ground. The dashes are fitted to the line's length so the
  // pattern closes on itself, with the seam in the middle of a gap: no stub
  // where it starts, wherever the field's size. Refitted while it changes
  // size (a second line, a phone's collapse) or radius (one line is a pill).
  const DASH = 4.5;
  const GAP = 3.5;
  const edge = document.querySelector(".composer-dashed-edge");
  const edgeLines = [...(edge?.querySelectorAll("rect") || [])];
  const edgeLine = edgeLines[edgeLines.length - 1];
  const field = edge?.parentElement;
  let edgeWatch = null;
  let edgeBox = null;
  let radiusFrame = 0;
  function fitEdge() {
    if (!edgeLine || typeof edgeLine.getTotalLength !== "function") return;
    const style = window.getComputedStyle(field);
    const border = parseFloat(style.borderTopWidth) || 0;
    // The observer's border box keeps its fractions (clientWidth rounds
    // them, leaving the right or bottom line half outside or short of it).
    const width = (edgeBox ? edgeBox.width - 2 * border : field.clientWidth) - 1;
    const height = (edgeBox ? edgeBox.height - 2 * border : field.clientHeight) - 1;
    if (width <= 0 || height <= 0) return;
    const inner = (parseFloat(style.borderTopLeftRadius) || 0) - border;
    const rx = String(Math.max(0, Math.min(inner - 0.5, width / 2, height / 2)));
    for (const line of edgeLines) {
      line.setAttribute("x", "0.5");
      line.setAttribute("y", "0.5");
      line.setAttribute("width", String(width));
      line.setAttribute("height", String(height));
      line.setAttribute("rx", rx);
    }
    const length = edgeLine.getTotalLength();
    const scale = length / Math.max(1, Math.round(length / (DASH + GAP))) / (DASH + GAP);
    edgeLine.style.strokeDasharray = `${DASH * scale} ${GAP * scale}`;
    edgeLine.style.strokeDashoffset = String((DASH + GAP / 2) * scale);
  }
  // Once shown, it keeps following the field: leaving a temporary chat
  // (New chat) grows the pill into the start screen's box while the rim
  // fades out, and the rim goes with it. The observer only works when the
  // field changes size.
  function watchEdge(on) {
    if (!field || !on || edgeWatch) return;
    if (typeof window.ResizeObserver !== "function") { fitEdge(); return; }
    // Padding moves with the phone's collapse: the border box is the size.
    edgeWatch = new window.ResizeObserver(entries => {
      const box = entries[entries.length - 1]?.borderBoxSize?.[0];
      if (box) edgeBox = { width: box.inlineSize, height: box.blockSize };
      fitEdge();
    });
    edgeWatch.observe(field, { box: "border-box" });
  }
  function followRadius() {
    fitEdge();
    radiusFrame = window.requestAnimationFrame(followRadius);
  }
  field?.addEventListener("transitionrun", event => {
    if (event.target === field && event.propertyName.includes("radius") && edgeWatch && !radiusFrame) followRadius();
  });
  for (const type of ["transitionend", "transitioncancel"]) {
    field?.addEventListener(type, event => {
      if (event.target !== field || !event.propertyName.includes("radius") || !radiusFrame) return;
      window.cancelAnimationFrame(radiusFrame);
      radiusFrame = 0;
      fitEdge();
    });
  }

  // The switch at the top right: on a new Agent chat it chooses, in a
  // temporary chat it stays pressed and says so (turning it off there would
  // read as "keep this chat", which leaving it never does); elsewhere it is
  // not there. The words: a greeting on the start screen, a line under the
  // field in the chat. The field's dashed edge in both (body.temporary-chat).
  function sync() {
    // Before agent-chat.js is there, nothing is known yet: the switch stays.
    if (!App.agentChat) return;
    const agent = App.agentChat.isSelected?.() === true;
    if (armed && (!agent || !newChatShown() || guest())) { armed = false; keepArmed(); }
    const fresh = agent && newChatShown() && !guest();
    const button = document.getElementById("temporaryChatButton");
    if (button) {
      button.hidden = !(session || fresh);
      button.setAttribute("aria-pressed", String(Boolean(session) || armed));
      // The tooltip says it whole; a screen reader hears the name, then only
      // what it adds.
      const title = session ? "Temporary chat. Gone when you leave it." : "Temporary chat";
      if (button.title !== (App.t?.(title) ?? title)) button.title = title;
      if (session) {
        button.setAttribute("aria-disabled", "true");
        const more = "Gone when you leave it.";
        if (button.getAttribute("aria-description") !== (App.t?.(more) ?? more)) button.setAttribute("aria-description", more);
      } else {
        button.removeAttribute("aria-disabled");
        button.removeAttribute("aria-description");
      }
    }
    document.body.classList.toggle("temporary-chat", shown());
    watchEdge(shown());
    const note = document.getElementById("temporaryChatNote");
    if (note) note.hidden = !session;
  }

  document.getElementById("temporaryChatButton")?.addEventListener("click", function (event) {
    // In the chat a tap turns nothing off; it says why (a finger gets no
    // hover tooltip, tooltip.js).
    if (session) { App.tooltip?.show?.(this); return; }
    arm(!armed);
    // Chosen with the mouse, the next keystroke is the question; the
    // keyboard stays on the switch, a phone keeps its keyboard closed.
    if (event.detail > 0 && window.matchMedia?.("(hover: hover) and (pointer: fine)")?.matches) {
      document.getElementById("questionInput")?.focus?.();
    }
  });
  window.addEventListener("consensio:run-mode-change", sync);
  window.addEventListener("consensio:run-registry-change", sync);
  window.addEventListener("consensio:auth-state", sync);

  App.temporaryChat = {
    armed: () => armed && !session, arm, start, token, adopt, leave, sync, shown, unanswered,
    current: () => (session ? { token: session.token, chatId: session.chatId } : null),
  };
})();
