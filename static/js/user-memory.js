/**
 * Das nutzereigene Gedaechtnis in den Einstellungen.
 *
 * Der Server ist die einzige Quelle: das Profil liegt am Konto, nicht im
 * Browser. Deshalb gibt es hier bewusst KEINEN localStorage-Spiegel -- ein
 * zweiter Stand, der nach einem Geraetewechsel still danebenliegt, waere genau
 * die Verwirrung, die dieses Feature aufloesen soll.
 *
 * Der Schalter speichert immer den zuletzt GESPEICHERTEN Textstand, nie den
 * Entwurf in den Feldern: sonst committet ein Klick auf "Use my memory"
 * nebenbei einen halb getippten Satz.
 */
(function () {
  "use strict";

  const FIELDS = ["role", "focus", "style", "constraints", "notes"];
  const FIELD_INPUT_IDS = {
    role: "memoryRoleInput",
    focus: "memoryFocusInput",
    style: "memoryStyleInput",
    constraints: "memoryConstraintsInput",
    notes: "memoryNotesInput"
  };

  const state = {
    saved: null,      // letzter vom Server bestaetigter Stand
    revision: null,   // Revision von `saved`; Basis fuer Compare-and-swap
    loaded: false,
    loading: false,
    saving: false,
    uid: null,
    items: [],          // gespeicherte Einzel-Erinnerungen (Agent oder Nutzer)
    itemsRevision: null,
    itemsBusy: false,
    editingId: null,
    confirmClear: false,
    maxItems: 100
  };

  function emptyProfile() {
    const profile = { enabled: true, auto_memory: false };
    FIELDS.forEach(field => { profile[field] = ""; });
    return profile;
  }

  function els() {
    const inputs = {};
    FIELDS.forEach(field => {
      inputs[field] = document.getElementById(FIELD_INPUT_IDS[field]);
    });
    return {
      section: document.getElementById("memorySettingsSection"),
      enabled: document.getElementById("memoryEnabledSwitch"),
      auto: document.getElementById("memoryAutoSwitch"),
      itemsList: document.getElementById("memoryItemsList"),
      itemsEmpty: document.getElementById("memoryItemsEmpty"),
      itemForm: document.getElementById("memoryItemAddForm"),
      itemInput: document.getElementById("memoryItemInput"),
      itemAdd: document.getElementById("memoryItemAddBtn"),
      itemsCount: document.getElementById("memoryItemsCount"),
      itemsClear: document.getElementById("clearMemoryItemsBtn"),
      itemsStatus: document.getElementById("memoryItemsStatus"),
      saveBtn: document.getElementById("saveMemoryBtn"),
      clearBtn: document.getElementById("clearMemoryBtn"),
      status: document.getElementById("memoryStatus"),
      inputs
    };
  }

  function currentUser() {
    const user = window.auth?.currentUser;
    return user && user.uid ? user : null;
  }

  function setStatus(message, tone) {
    const { status } = els();
    if (!status) return;
    status.textContent = message || "";
    status.dataset.tone = tone || "";
  }

  // Ein veralteter Save verliert nie den Entwurf. Der Nutzer entscheidet:
  // neueren Stand laden (Entwurf verwerfen) oder den Entwurf bewusst ueber den
  // neueren Stand speichern.
  function showConflict(error) {
    const { status } = els();
    if (!status) return;
    const uid = state.uid;
    const latest = error.revision;
    status.textContent = (error.message || "Memory changed elsewhere.") + " ";
    status.dataset.tone = "error";
    const reload = document.createElement("button");
    reload.type = "button";
    reload.className = "settings-inline-btn";
    reload.dataset.memoryConflict = "reload";
    reload.textContent = "Load latest";
    reload.addEventListener("click", () => load(true));
    status.append(reload);
    if (latest !== null) {
      const keep = document.createElement("button");
      keep.type = "button";
      keep.className = "settings-inline-btn";
      keep.dataset.memoryConflict = "keep";
      keep.textContent = "Keep my draft";
      keep.addEventListener("click", () => {
        if (state.uid !== uid || currentUser()?.uid !== uid) return;
        state.revision = latest;
        setStatus("Your draft will replace the newer Memory when you press Save.", "muted");
        syncControls();
      });
      status.append(" ", keep);
    }
  }

  async function api(method, body, path) {
    const user = currentUser();
    if (!user) throw new Error("Please log in first.");
    const uid = user.uid;
    const token = await user.getIdToken();
    if (window.auth?.currentUser?.uid !== uid) throw new Error("Authentication changed.");
    const response = await fetch(path || "/api/my/memory", {
      method,
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
      body: body ? JSON.stringify(body) : undefined
    });
    let data = {};
    try { data = await response.json(); } catch (_) { /* empty body */ }
    if (window.auth?.currentUser?.uid !== uid) throw new Error("Authentication changed.");
    if (!response.ok) {
      // FastAPI meldet Schema-Fehler als Liste von Objekten. Als Fehlertext
      // stand dort sonst "[object Object]" im Statusstreifen.
      // main.py wraps HTTPException.detail as {"error": ...}; plain FastAPI
      // uses {"detail": ...}. Accept both so conflicts work in production.
      const isObject = value => value && typeof value === "object" && !Array.isArray(value);
      const structured = isObject(data.detail) ? data.detail : (isObject(data.error) ? data.error : null);
      const detail = [data.detail, structured?.message, data.error]
        .find(value => typeof value === "string" && value.trim());
      const error = new Error(detail || ("HTTP " + response.status));
      error.status = response.status;
      error.code = structured?.error_code || "";
      error.revision = Number.isInteger(structured?.revision) ? structured.revision : null;
      throw error;
    }
    return data;
  }

  function revisionOf(result) {
    return Number.isInteger(result?.revision) ? result.revision : null;
  }

  function applyLimits(limits) {
    const notes = document.getElementById("memoryNotesInput");
    const max = Number(limits?.notes_chars);
    if (notes && Number.isFinite(max) && max > 0) notes.maxLength = max;
    updateCounts();
  }

  // Der Server antwortet mit dem GESPEICHERTEN Profil, und das traegt neben den
  // Feldern auch seine `schema_version`. Die PUT-Schnittstelle verbietet
  // unbekannte Felder (extra="forbid"), also darf eine Serverantwort nie
  // ungefiltert zurueckgeschickt werden -- genau das liess den Schalter mit 422
  // scheitern und die Checkbox zurueckspringen.
  function requestBody(profile) {
    const body = { enabled: profile?.enabled !== false, auto_memory: profile?.auto_memory === true };
    FIELDS.forEach(field => {
      body[field] = typeof profile?.[field] === "string" ? profile[field] : "";
    });
    // Compare-and-swap: der Server speichert nur, wenn seit dem Laden nichts
    // anderes (zweiter Tab, Remember/Correct, Undo) geschrieben hat.
    body.expected_revision = state.revision;
    return body;
  }

  function readForm() {
    const { enabled, inputs } = els();
    // Der Agent-Schalter speichert sofort; das Formular traegt nur den
    // gespeicherten Stand weiter, nie einen halben Klick.
    const profile = { enabled: enabled ? !!enabled.checked : true, auto_memory: state.saved?.auto_memory === true };
    FIELDS.forEach(field => {
      profile[field] = (inputs[field]?.value || "").trim();
    });
    return profile;
  }

  function writeForm(profile) {
    const { enabled, auto, inputs } = els();
    if (enabled) enabled.checked = profile.enabled !== false;
    if (auto) auto.checked = profile.auto_memory === true;
    FIELDS.forEach(field => {
      if (inputs[field]) inputs[field].value = profile[field] || "";
    });
    updateCounts();
  }

  // Die kurzen Felder zeigen den Zaehler erst nahe ihrer Grenze. Bei der grossen
  // Notebox ist die Kapazitaet selbst relevante Information und bleibt sichtbar.
  const COUNT_VISIBLE_RATIO = 0.8;

  function updateCounts() {
    document.querySelectorAll("[data-memory-count-for]").forEach(node => {
      const input = document.getElementById(node.dataset.memoryCountFor);
      if (!input) return;
      const max = Number(input.getAttribute("maxlength")) || 0;
      const used = (input.value || "").length;
      const always = node.dataset.alwaysVisible === "true";
      const near = always || (max > 0 && used >= max * COUNT_VISIBLE_RATIO);
      node.textContent = near ? `${used.toLocaleString()}/${max.toLocaleString()}` : "";
      node.dataset.near = near ? "true" : "";
      node.dataset.full = max && used >= max ? "true" : "";
    });
  }

  function isDirty() {
    if (!state.saved) return false;
    const form = readForm();
    return FIELDS.some(field => (form[field] || "") !== (state.saved[field] || ""));
  }

  function syncControls() {
    const { section, enabled, saveBtn, clearBtn, inputs } = els();
    if (!section) return;
    const signedIn = !!currentUser();
    section.dataset.signedIn = signedIn ? "true" : "false";

    const disabled = !signedIn || state.loading || state.saving;
    if (enabled) enabled.disabled = disabled;
    const { auto } = els();
    // Ohne gelesenes Memory kann der Agent nichts abgleichen: der Schalter
    // gilt nur, solange "Use my memory" an ist.
    if (auto) auto.disabled = disabled || state.saved?.enabled === false;
    syncItemControls();
    FIELDS.forEach(field => {
      if (inputs[field]) inputs[field].disabled = disabled;
    });
    if (clearBtn) clearBtn.disabled = disabled;
    if (saveBtn) {
      saveBtn.disabled = disabled || (state.loaded && !isDirty());
      saveBtn.textContent = state.saving ? "Saving…" : "Save memory";
    }
  }

  async function load(force, options) {
    const user = currentUser();
    if (!user) {
      state.loaded = false;
      state.saved = null;
      state.uid = null;
      writeForm(emptyProfile());
      setStatus("Log in to set up your memory — it lives on your account, not in this browser.", "muted");
      syncControls();
      return;
    }
    if (state.loaded && state.uid === user.uid && !force) {
      syncControls();
      return;
    }
    // Remember/Correct/Undo laden nach. Ein ungespeicherter Entwurf bleibt
    // dabei stehen und behaelt seine alte Revision: der naechste Save endet
    // dann ehrlich im Konflikt, statt den KI-Stand still zu ueberschreiben.
    if (options?.keepDraft && state.loaded && state.uid === user.uid && isDirty()) {
      setStatus("Memory was updated elsewhere. Save to review the conflict, or load the latest version.", "muted");
      syncControls();
      return;
    }

    state.loading = true;
    setStatus("Loading…", "muted");
    syncControls();
    try {
      const result = await api("GET");
      const profile = result.memory || emptyProfile();
      applyLimits(result.limits);
      state.saved = profile;
      state.revision = revisionOf(result);
      state.uid = user.uid;
      state.loaded = true;
      writeForm(profile);
      receiveItems(result);
      setStatus("", "");
    } catch (error) {
      setStatus(error.message || "Memory could not be loaded.", "error");
    } finally {
      state.loading = false;
      syncControls();
    }
  }

  async function persist(profile, successMessage, options) {
    const rewriteFields = options?.rewriteFields !== false;
    state.saving = true;
    syncControls();
    try {
      const result = await api("PUT", requestBody(profile));
      const saved = result.memory || emptyProfile();
      applyLimits(result.limits);
      state.saved = saved;
      state.revision = revisionOf(result);
      state.loaded = true;
      if (rewriteFields) {
        // Der Server normalisiert (Whitespace, Laenge, Rahmenmarken). Zurueck-
        // schreiben, damit das Feld zeigt, was tatsaechlich gespeichert ist.
        writeForm(saved);
      } else {
        // Nur der Schalter wurde geschrieben. Die Textfelder bleiben, wie der
        // Nutzer sie gerade hat -- ein Klick auf "Use my memory" darf einen
        // halb getippten Satz weder speichern noch wegwerfen.
        const { enabled, auto } = els();
        if (enabled) enabled.checked = saved.enabled !== false;
        if (auto) auto.checked = saved.auto_memory === true;
      }
      setStatus(successMessage, "ok");
      window.App?.trackAppEvent?.("app_memory_saved");
      return true;
    } catch (error) {
      if (error.status === 409 && error.code === "revision_conflict") {
        // Felder bleiben unveraendert: der Entwurf gehoert dem Nutzer.
        showConflict(error);
      } else {
        setStatus(error.message || "Memory could not be saved.", "error");
      }
      return false;
    } finally {
      state.saving = false;
      syncControls();
    }
  }

  async function save() {
    if (!currentUser()) {
      setStatus("Please log in first.", "error");
      return;
    }
    const profile = readForm();
    const empty = FIELDS.every(field => !profile[field]);
    await persist(profile, empty ? "Memory cleared." : "Saved. Your next run starts with this.");
  }

  async function toggleEnabled() {
    const { enabled } = els();
    if (!enabled) return;
    if (!currentUser()) {
      enabled.checked = !enabled.checked;
      setStatus("Please log in first.", "error");
      return;
    }
    // Der Schalter schreibt den gespeicherten Textstand mit. Ist der (noch)
    // nicht geladen, erst nachladen -- sonst wuerde ein Klick auf den Schalter
    // das vorhandene Profil mit lauter leeren Feldern ueberschreiben. load()
    // schreibt das Formular neu, deshalb steht der Wunsch des Nutzers vorher
    // fest und wird danach wieder gesetzt.
    const wanted = enabled.checked;
    if (!state.loaded) {
      await load();
      enabled.checked = wanted;
    }
    const next = { ...(state.saved || emptyProfile()), enabled: wanted };
    const ok = await persist(
      next,
      wanted ? "Memory is on again." : "Memory paused. Runs go out without it.",
      { rewriteFields: false }
    );
    if (!ok) enabled.checked = !wanted;
    else if (!wanted) window.App?.agentMemory?.dismissNudge?.();
  }

  async function toggleAuto() {
    const { auto } = els();
    if (!auto) return;
    if (!currentUser()) {
      auto.checked = !auto.checked;
      setStatus("Please log in first.", "error");
      return;
    }
    const wanted = auto.checked;
    if (!state.loaded) {
      await load();
      auto.checked = wanted;
    }
    const next = { ...(state.saved || emptyProfile()), auto_memory: wanted };
    const ok = await persist(
      next,
      wanted ? "Agent can now update your memory. Every change shows under its answer."
        : "Agent no longer changes your memory. Saved memories stay until you delete them.",
      { rewriteFields: false }
    );
    if (!ok) auto.checked = !wanted;
    else window.App?.trackAppEvent?.(wanted ? "app_auto_memory_on" : "app_auto_memory_off");
    // Settled in Settings either way: no more hint under answers.
    if (ok) window.App?.agentMemory?.dismissNudge?.();
  }

  // The hint under an Agent answer (agent-memory.js): "Use my memory" and
  // "Let Agent update memory" in one step, without touching the text fields.
  async function enableAgentMemory() {
    if (!currentUser()) return false;
    if (!state.loaded) await load();
    if (!state.loaded) return false;
    const next = { ...(state.saved || emptyProfile()), enabled: true, auto_memory: true };
    const ok = await persist(next, "Agent can now update your memory. Every change shows under its answer.",
      { rewriteFields: false });
    if (ok) window.App?.trackAppEvent?.("app_auto_memory_on", { source: "hint" });
    return ok;
  }

  // --- Gespeicherte Erinnerungen ---------------------------------------------
  // Jede Aenderung geht sofort an den Server (Compare-and-swap auf die
  // Listen-Revision). Hat ein Agent-Lauf dazwischen geschrieben, antwortet der
  // Server 409; die Liste wird neu geladen statt still ueberschrieben.

  function setItemsStatus(message, tone) {
    const { itemsStatus } = els();
    if (!itemsStatus) return;
    itemsStatus.textContent = message || "";
    itemsStatus.dataset.tone = tone || "";
  }

  function receiveItems(result) {
    if (!Array.isArray(result?.items)) return;
    state.items = result.items;
    if (Number.isInteger(result.items_revision)) state.itemsRevision = result.items_revision;
    if (Number.isInteger(result.limits?.items)) state.maxItems = result.limits.items;
    const { itemInput } = els();
    if (itemInput && Number.isInteger(result.limits?.item_chars)) itemInput.maxLength = result.limits.item_chars;
    if (state.editingId && !state.items.some(item => item.id === state.editingId)) state.editingId = null;
    renderItems();
  }

  function itemDate(item) {
    const stamp = Date.parse(item.updated_at || item.created_at || "");
    return Number.isFinite(stamp)
      ? new Date(stamp).toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" })
      : "";
  }

  function itemButton(label, handler, ariaLabel) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "settings-inline-btn";
    button.textContent = label;
    if (ariaLabel) button.setAttribute("aria-label", ariaLabel);
    button.addEventListener("click", handler);
    return button;
  }

  function renderItems() {
    const { itemsList, itemsEmpty, itemsCount, itemInput } = els();
    if (!itemsList) return;
    itemsList.replaceChildren(...state.items.map(item => {
      const row = document.createElement("li");
      row.className = "settings-memory-item";
      row.dataset.itemId = item.id;
      if (state.editingId === item.id) {
        row.classList.add("is-editing");
        const input = document.createElement("input");
        input.type = "text";
        input.value = item.text;
        input.maxLength = itemInput?.maxLength > 0 ? itemInput.maxLength : 300;
        input.setAttribute("aria-label", "Edit memory");
        input.addEventListener("keydown", event => {
          if (event.key === "Enter") { event.preventDefault(); saveEdit(item, input.value); }
          if (event.key === "Escape") { event.preventDefault(); state.editingId = null; renderItems(); }
        });
        row.append(input,
          itemButton("Save", () => saveEdit(item, input.value)),
          itemButton("Cancel", () => { state.editingId = null; renderItems(); }));
        requestAnimationFrame(() => input.focus());
        return row;
      }
      const body = document.createElement("div");
      body.className = "settings-memory-item-body";
      const text = document.createElement("span");
      text.className = "settings-memory-item-text";
      text.textContent = item.text;
      const meta = document.createElement("small");
      meta.className = "settings-memory-item-meta";
      meta.textContent = [item.origin === "agent" ? "Saved by Agent" : "Added by you", itemDate(item)]
        .filter(Boolean).join(" · ");
      body.append(text, meta);
      row.append(body,
        itemButton("Edit", () => { state.editingId = item.id; renderItems(); }, `Edit memory: ${item.text}`),
        itemButton("Delete", () => changeItems([{ op: "delete", id: item.id }], "Deleted."), `Delete memory: ${item.text}`));
      return row;
    }));
    if (itemsEmpty) itemsEmpty.hidden = state.items.length > 0;
    if (itemsCount) {
      const near = state.items.length >= state.maxItems * 0.8;
      itemsCount.textContent = state.items.length
        ? `${state.items.length}${near ? ` of ${state.maxItems}` : ""} saved`
        : "";
    }
    syncItemControls();
  }

  function syncItemControls() {
    const { itemsList, itemInput, itemAdd, itemsClear } = els();
    const disabled = !currentUser() || !state.loaded || state.itemsBusy;
    if (itemInput) itemInput.disabled = disabled;
    if (itemAdd) itemAdd.disabled = disabled;
    if (itemsClear) {
      itemsClear.hidden = !state.items.length;
      itemsClear.disabled = disabled;
      // Zwei Klicks statt eines Browser-Dialogs: der erste fragt, der zweite loescht.
      itemsClear.textContent = state.confirmClear ? "Delete all saved memories?" : "Delete all";
      itemsClear.dataset.confirm = state.confirmClear ? "true" : "";
    }
    itemsList?.querySelectorAll("button, input").forEach(control => { control.disabled = disabled; });
  }

  async function changeItems(changes, successMessage) {
    if (!currentUser() || state.itemsBusy) return false;
    state.itemsBusy = true;
    setItemsStatus("Saving…", "muted");
    syncItemControls();
    try {
      const result = await api("POST", { changes, expected_revision: state.itemsRevision ?? 0 }, "/api/my/memory/items");
      state.editingId = null;
      receiveItems(result);
      setItemsStatus(successMessage, "ok");
      return true;
    } catch (error) {
      if (error.status === 409 && error.code === "revision_conflict") {
        await reloadItems();
        setItemsStatus("Memory changed in the meantime. The list was reloaded; please try again.", "error");
      } else {
        setItemsStatus(error.message || "Memory could not be saved.", "error");
      }
      return false;
    } finally {
      state.itemsBusy = false;
      syncItemControls();
    }
  }

  function saveEdit(item, value) {
    const text = String(value || "").trim();
    if (!text) return changeItems([{ op: "delete", id: item.id }], "Deleted.");
    if (text === item.text) {
      state.editingId = null;
      renderItems();
      return Promise.resolve(true);
    }
    return changeItems([{ op: "update", id: item.id, text }], "Updated.");
  }

  async function addItem(event) {
    event?.preventDefault();
    const { itemInput } = els();
    const text = (itemInput?.value || "").trim();
    if (!text) return;
    if (await changeItems([{ op: "add", text }], "Saved.")) itemInput.value = "";
  }

  async function clearItems() {
    clearTimeout(state.confirmTimer);
    if (!state.confirmClear) {
      state.confirmClear = true;
      syncItemControls();
      state.confirmTimer = setTimeout(() => { state.confirmClear = false; syncItemControls(); }, 5000);
      return;
    }
    state.confirmClear = false;
    state.itemsBusy = true;
    syncItemControls();
    try {
      receiveItems(await api("DELETE", null, "/api/my/memory/items"));
      setItemsStatus("All saved memories deleted.", "ok");
    } catch (error) {
      setItemsStatus(error.message || "Memory could not be deleted.", "error");
    } finally {
      state.itemsBusy = false;
      syncItemControls();
    }
  }

  async function reloadItems() {
    try {
      receiveItems(await api("GET"));
    } catch (error) {
      setItemsStatus(error.message || "Memory could not be loaded.", "error");
    }
  }

  function clearFields() {
    const { inputs } = els();
    FIELDS.forEach(field => {
      if (inputs[field]) inputs[field].value = "";
    });
    updateCounts();
    // Bewusst nicht sofort speichern: Loeschen soll dieselbe bestaetigte
    // Handlung sein wie jede andere Aenderung.
    setStatus("Cleared. Press Save to apply.", "muted");
    syncControls();
  }

  function settingsModalIsOpen() {
    const modal = document.getElementById("systemPromptModal");
    return !!modal && getComputedStyle(modal).display !== "none";
  }

  function bind() {
    if (window.__userMemoryBound) return;
    const { section } = els();
    if (!section) return;
    window.__userMemoryBound = true;

    const { enabled, saveBtn, clearBtn, inputs } = els();
    saveBtn?.addEventListener("click", save);
    clearBtn?.addEventListener("click", clearFields);
    enabled?.addEventListener("change", toggleEnabled);
    els().auto?.addEventListener("change", toggleAuto);
    els().itemForm?.addEventListener("submit", addItem);
    els().itemsClear?.addEventListener("click", clearItems);
    // Undo unter einer Antwort: nur die Liste nachziehen. Ein ungespeicherter
    // Entwurf in den Textfeldern bleibt unberuehrt.
    window.addEventListener("consensio:memory-changed", () => {
      if (state.loaded) reloadItems();
    });
    FIELDS.forEach(field => {
      inputs[field]?.addEventListener("input", () => {
        updateCounts();
        syncControls();
      });
    });

    window.addEventListener("consensio:auth-state", event => {
      const uid = event.detail?.uid || null;
      if (uid === state.uid) return;
      state.loaded = false;
      state.saved = null;
      state.revision = null;
      state.uid = null;
      state.items = [];
      state.itemsRevision = null;
      state.editingId = null;
      renderItems();
      // Nur den Stand verwerfen, NICHT nachladen: dieses Ereignis feuert bei
      // jedem Seitenaufruf eines eingeloggten Kontos. Ein Fetch hier haette den
      // Read, den der Modal-Oeffner bewusst aufschiebt, an jeden Aufruf
      // gehaengt. Steht das Fenster gerade offen, wird sofort nachgezogen --
      // sonst zeigte es weiter das Profil des vorigen Kontos.
      if (settingsModalIsOpen() || !uid) {
        load();
        return;
      }
      writeForm(emptyProfile());
      setStatus("", "");
      syncControls();
    });

    // Die Einstellungen sind ein Modal: laden, wenn es tatsaechlich geoeffnet
    // wird, statt bei jedem Seitenaufruf einen Firestore-Read zu bezahlen.
    document.getElementById("editSystemPromptBtn")?.addEventListener("click", () => load());

    writeForm(emptyProfile());
    syncControls();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }

  window.App = window.App || {};
  window.App.userMemory = { load, save, isDirty, enableAgentMemory };
})();
