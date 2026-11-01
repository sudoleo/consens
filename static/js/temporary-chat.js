// =====================================================================
// temporary-chat.js
// Temporary chats (since 2026-11-01): an Agent chat that is not in the
// user's chats, uses and changes no memory, has no workspace and cannot be
// shared. The server knows it by its chat (POST /chats with temporary:
// true, chat_store.create_chat) and leaves out bookmark, memory, workspace,
// Watch and chat search for it (routers/agent.py). This module is the
// browser's half: the switch in the (+) menu of a new Agent chat, the
// words that say a chat is temporary, and its end.
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

  function arm(on) {
    const next = Boolean(on) && !session;
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

  // The switch in the (+) menu: on a new Agent chat it chooses, in a
  // temporary chat it says so; elsewhere it is not there. The words: a
  // greeting on the start screen, a line under the field in the chat.
  function sync() {
    // Before agent-chat.js is there, nothing is known yet: the switch stays.
    if (!App.agentChat) return;
    const agent = App.agentChat.isSelected?.() === true;
    if (armed && (!agent || !newChatShown())) { armed = false; keepArmed(); }
    const fresh = agent && newChatShown();
    const row = document.getElementById("temporaryChatOption");
    const toggle = document.getElementById("temporaryChatToggle");
    const hint = document.getElementById("temporaryChatHint");
    if (row) row.hidden = !(session || fresh);
    if (toggle) {
      toggle.checked = Boolean(session) || armed;
      toggle.disabled = Boolean(session);
    }
    if (hint) {
      const text = session ? "Ends when you leave this chat" : "Not saved, no memory";
      if (hint.textContent !== (App.t?.(text) ?? text)) hint.textContent = text;
    }
    document.body.classList.toggle("temporary-chat", shown());
    const note = document.getElementById("temporaryChatNote");
    if (note) note.hidden = !session;
  }

  document.getElementById("temporaryChatToggle")?.addEventListener("change", function () {
    arm(this.checked);
    document.getElementById("questionInput")?.focus?.();
  });
  window.addEventListener("consensio:run-mode-change", sync);
  window.addEventListener("consensio:run-registry-change", sync);

  App.temporaryChat = {
    armed: () => armed && !session, arm, start, token, adopt, leave, sync, shown, unanswered,
    current: () => (session ? { token: session.token, chatId: session.chatId } : null),
  };
})();
