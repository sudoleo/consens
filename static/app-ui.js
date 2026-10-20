// The own system prompt is an account setting (user-settings.js, which also
// drops the built-in defaults older versions stored). Empty: the app default.
function getStoredSystemPrompt() {
  return window.App.userSettings.get("system_prompt") || "";
}

/**
 * Die Einstellungen als Reiter statt als eine lange Bahn.
 *
 * Sechs Kategorien untereinander waren beim Oeffnen eine Wand: der Nutzer musste
 * scrollen, um zu wissen, was es ueberhaupt gibt. Jetzt ist genau EINE Kategorie
 * sichtbar und die Liste links ist das Inhaltsverzeichnis.
 *
 * Die Sichtbarkeit der Panels gehoert ausschliesslich hierher. firebase.js hat
 * frueher `style.display` direkt auf dem Account-Panel gesetzt; ein Inline-Style
 * haette diesen Controller uebersteuert, deshalb schaltet firebase.js jetzt
 * ueber `setTabAvailable` nur noch den REITER frei.
 */
const settingsTabs = (function () {
  function tabs() {
    return Array.from(document.querySelectorAll("[data-settings-tab]"));
  }

  function panelOf(tab) {
    return document.getElementById(tab.dataset.settingsTab);
  }

  function available(tab) {
    return !tab.hidden;
  }

  function activate(panelId, options) {
    const all = tabs();
    if (!all.length) return;
    let target = all.find(tab => tab.dataset.settingsTab === panelId && available(tab));
    if (!target) target = all.find(available);
    if (!target) return;

    all.forEach(tab => {
      const isActive = tab === target;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
      // Genau ein Reiter liegt in der Tab-Reihenfolge; zwischen den Reitern
      // navigieren die Pfeiltasten (WAI-ARIA Tabs-Muster).
      tab.tabIndex = isActive ? 0 : -1;
      const panel = panelOf(tab);
      if (panel) panel.hidden = !isActive;
    });

    if (options?.focus) target.focus();
    // Keep the selected section visible in the horizontal mobile navigation.
    if (target.getClientRects().length) {
      target.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
    const body = document.querySelector(".settings-body");
    if (body) body.scrollTop = 0;
  }

  function activeTab() {
    return tabs().find(tab => tab.classList.contains("is-active")) || null;
  }

  function setTabAvailable(panelId, isAvailable) {
    const tab = tabs().find(item => item.dataset.settingsTab === panelId);
    if (!tab) return;
    tab.hidden = !isAvailable;
    // Der aktive Reiter darf nicht verschwinden, waehrend sein Panel offen ist
    // (Logout mit geoeffnetem Account-Tab): dann faellt die Auswahl zurueck.
    if (!isAvailable && tab.classList.contains("is-active")) activate(null);
  }

  function step(delta) {
    const usable = tabs().filter(available);
    const index = usable.indexOf(activeTab());
    if (index < 0) return;
    const next = usable[(index + delta + usable.length) % usable.length];
    activate(next.dataset.settingsTab, { focus: true });
  }

  function bind() {
    const nav = document.querySelector(".settings-nav");
    if (!nav || nav.dataset.bound === "true") return;
    nav.dataset.bound = "true";
    const stackedLayout = window.matchMedia("(max-width: 699px)");
    const syncOrientation = () => {
      nav.setAttribute("aria-orientation", stackedLayout.matches ? "horizontal" : "vertical");
      const active = activeTab();
      if (active?.getClientRects().length) {
        active.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    };
    syncOrientation();
    stackedLayout.addEventListener("change", syncOrientation);

    nav.addEventListener("click", event => {
      const tab = event.target.closest("[data-settings-tab]");
      if (tab) activate(tab.dataset.settingsTab);
    });

    nav.addEventListener("keydown", event => {
      const usable = tabs().filter(available);
      if (event.key === "ArrowDown" || event.key === "ArrowRight") step(1);
      else if (event.key === "ArrowUp" || event.key === "ArrowLeft") step(-1);
      else if (event.key === "Home") activate(usable[0]?.dataset.settingsTab, { focus: true });
      else if (event.key === "End") activate(usable[usable.length - 1]?.dataset.settingsTab, { focus: true });
      else return;
      event.preventDefault();
    });

    activate(null);
  }

  return { bind, activate, setTabAvailable, reset: () => activate(null) };
})();

// Sofort veroeffentlichen, nicht erst beim Binden: firebase.js kann den
// Account-Reiter freigeben, bevor DOMContentLoaded gelaufen ist. Waere der Bus
// dann noch leer, bliebe der Reiter fuer eingeloggte Konten unsichtbar.
window.App = window.App || {};
window.App.settingsTabs = settingsTabs;

// Settings and Help are native <dialog>s opened through App.modalDialog
// (focus in and back, Escape, deliberate backdrop clicks only).
function openSettingsModal(event) {
  const modal = document.getElementById("systemPromptModal");
  const textarea = document.getElementById("systemPromptInput");
  if (!modal || !textarea || window.App.modalDialog.isOpen(modal)) return;

  textarea.value = getStoredSystemPrompt();
  syncSettingsGuestNote();
  // Immer auf dem ersten Reiter oeffnen. Der zuletzt benutzte waere clever,
  // aber unvorhersehbar — man findet Einstellungen ueber einen festen Ort.
  // Reset before showing: focus lands on the tab that is then selected.
  settingsTabs.reset();
  window.App.modalDialog.open(modal, {
    opener: event?.currentTarget || document.getElementById("editSystemPromptBtn"),
    focus: () => modal.querySelector(".settings-nav-item.is-active")
  });
  window.App?.trackAppEvent?.("app_settings_open");
}

function closeSettingsModal() {
  window.App.modalDialog.close(document.getElementById("systemPromptModal"));
}

// A guest finds Memory and the key greyed out: the line under the header
// says why and offers the way in (Apple-Audit H13).
function syncSettingsGuestNote() {
  const note = document.getElementById("settingsGuestNote");
  if (note) note.hidden = Boolean(window.auth?.currentUser);
}

function logInFromSettings() {
  closeSettingsModal();
  window.App.askToLogIn?.("Log in to keep your memory and settings on your account.",
    { trigger: document.getElementById("editSystemPromptBtn"), source: "settings" });
}

function saveSystemPrompt() {
  const textarea = document.getElementById("systemPromptInput");
  if (textarea) {
    const text = textarea.value.trim() || null;
    // The account does not keep a prompt over 32,000 bytes (the field caps the
    // characters) or with a broken character; the editor stays open with the
    // text instead of dropping it.
    if (!window.App.userSettings.accepts("system_prompt", text)) {
      window.App.showPopup?.("This system prompt can’t be saved: it is too long or contains an invalid character.");
      return;
    }
    window.App.userSettings.set("system_prompt", text);
  }
  closeSettingsModal();
  window.App?.trackAppEvent?.("app_settings_saved");
}

// Help stacks over the open Settings dialog; closing it hands focus back to
// the "?" button inside Settings.
function openHelpModal(event) {
  const opened = window.App.modalDialog.open(document.getElementById("helpModal"), {
    opener: event?.currentTarget || document.getElementById("helpButton")
  });
  if (opened) window.App?.trackAppEvent?.("app_help_open");
}

function closeHelpModal() {
  window.App.modalDialog.close(document.getElementById("helpModal"));
}

function bindSettingsModalControls() {
  if (window.__settingsModalControlsBound) return;
  window.__settingsModalControlsBound = true;

  settingsTabs.bind();
  // The backdrop closes only a click that also started on it: selecting
  // text in a field and releasing over the backdrop used to close Settings
  // and drop the unsaved edit (audit F5).
  window.App.modalDialog.bind(document.getElementById("systemPromptModal"));
  window.App.modalDialog.bind(document.getElementById("helpModal"));

  document.getElementById("editSystemPromptBtn")?.addEventListener("click", openSettingsModal);
  document.getElementById("closeSystemPromptModal")?.addEventListener("click", closeSettingsModal);
  document.getElementById("saveSystemPromptBtn")?.addEventListener("click", saveSystemPrompt);
  document.getElementById("helpButton")?.addEventListener("click", openHelpModal);
  document.getElementById("settingsLoginButton")?.addEventListener("click", logInFromSettings);
  window.addEventListener("consensio:auth-state", syncSettingsGuestNote);
  document.getElementById("closeHelpModal")?.addEventListener("click", closeHelpModal);
  // The account's prompt arrived (server, another tab, sign-out): an open
  // editor follows unless it holds an edit of its own.
  window.App.userSettings.onChange("system_prompt", detail => {
    const textarea = document.getElementById("systemPromptInput");
    if (detail.source === "local" || !textarea) return;
    if (textarea.value.trim() === (detail.previous.system_prompt || "")) textarea.value = getStoredSystemPrompt();
  });
}

function bindAppUiControls() {
  bindSettingsModalControls();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindAppUiControls);
} else {
  bindAppUiControls();
}
