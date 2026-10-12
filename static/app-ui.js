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

function openSettingsModal() {
  const modal = document.getElementById("systemPromptModal");
  const textarea = document.getElementById("systemPromptInput");
  if (!modal || !textarea) return;

  textarea.value = getStoredSystemPrompt();
  // Immer auf dem ersten Reiter oeffnen. Der zuletzt benutzte waere clever,
  // aber unvorhersehbar — man findet Einstellungen ueber einen festen Ort.
  modal.style.display = "block";
  settingsTabs.reset();
  window.App?.trackAppEvent?.("app_settings_open");
}

function closeSettingsModal() {
  const modal = document.getElementById("systemPromptModal");
  if (modal) {
    modal.style.display = "none";
  }
}

function saveSystemPrompt() {
  const textarea = document.getElementById("systemPromptInput");
  if (textarea) {
    const text = textarea.value.trim() || null;
    // The account does not keep a prompt over 32,000 bytes (the field caps the
    // characters); the editor stays open with the text instead of dropping it.
    if (!window.App.userSettings.accepts("system_prompt", text)) {
      window.App.showPopup?.("This system prompt is too long to save. Please shorten it.");
      return;
    }
    window.App.userSettings.set("system_prompt", text);
  }
  closeSettingsModal();
  window.App?.trackAppEvent?.("app_settings_saved");
}

function openHelpModal() {
  const helpModal = document.getElementById("helpModal");
  if (helpModal) {
    helpModal.style.display = "block";
    window.App?.trackAppEvent?.("app_help_open");
  }
}

function closeHelpModal() {
  const helpModal = document.getElementById("helpModal");
  if (helpModal) {
    helpModal.style.display = "none";
  }
}

function bindSettingsModalControls() {
  if (window.__settingsModalControlsBound) return;
  window.__settingsModalControlsBound = true;

  settingsTabs.bind();

  document.getElementById("editSystemPromptBtn")?.addEventListener("click", openSettingsModal);
  document.getElementById("closeSystemPromptModal")?.addEventListener("click", closeSettingsModal);
  document.getElementById("saveSystemPromptBtn")?.addEventListener("click", saveSystemPrompt);
  document.getElementById("helpButton")?.addEventListener("click", openHelpModal);
  document.getElementById("closeHelpModal")?.addEventListener("click", closeHelpModal);
  // The account's prompt arrived (server, another tab, sign-out): an open
  // editor follows unless it holds an edit of its own.
  window.App.userSettings.onChange("system_prompt", detail => {
    const textarea = document.getElementById("systemPromptInput");
    if (detail.source === "local" || !textarea) return;
    if (textarea.value.trim() === (detail.previous.system_prompt || "")) textarea.value = getStoredSystemPrompt();
  });

  window.addEventListener("click", (event) => {
    if (event.target === document.getElementById("systemPromptModal")) {
      closeSettingsModal();
    }
    if (event.target === document.getElementById("helpModal")) {
      closeHelpModal();
    }
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
