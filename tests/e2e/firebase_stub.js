// E2E-Stub fuer /static/firebase.js bzw. das gehashte Firebase-Bundle - wird
// von Playwright per Route anstelle des echten Moduls ausgeliefert
// (siehe tests/e2e/conftest.py).
// Simuliert einen eingeloggten, E-Mail-verifizierten Free-User ohne echtes
// Firebase. Das Sentinel-Token akzeptiert das Backend nur mit MOCK_AUTH=1.
//
// Muss alle window.*-Vertraege bedienen, die andere Module OHNE Optional-
// Chaining aufrufen (saveBookmark, saveBookmarkConsensus, recordModelVote,
// sendFeedback, window.auth.currentUser) - siehe docs/codebase-map.md §8.

const E2E_TOKEN = "e2e-mock-token";

window.auth = {
  currentUser: {
    uid: "e2e-mock-user",
    email: "e2e@consens.io.invalid",
    emailVerified: true,
    getIdToken: async () => E2E_TOKEN,
  },
};

window.bookmarksData = [];

// Mirror the real firebase.js access setup for an authenticated user.
const bookmarksSection = document.querySelector(".bookmarks-section");
const bookmarksToggle = document.getElementById("bookmarksToggle");
const bookmarkSearchTrigger = document.getElementById("bookmarkSearchTrigger");
const bookmarkSearchInput = document.getElementById("chatSearch");
bookmarksSection?.classList.remove("is-locked");
for (const control of [bookmarksToggle, bookmarkSearchTrigger, bookmarkSearchInput]) {
  if (!control) continue;
  control.disabled = false;
  control.setAttribute("aria-disabled", "false");
}

window.recordModelVote = () => {};
window.saveBookmark = () => {};
window.saveBookmarkConsensus = () => {};
window.loadBookmarks = async () => {};
window.deleteBookmark = async () => {};
window.sendFeedback = async () => ({ ok: true });

// Tier-UI als "eingeloggt, Free" initialisieren, sobald user-tier.js geladen
// ist. Module laufen vor den defer-Skripten; das echte firebase.js erledigt
// das im asynchronen onAuthStateChanged-Callback, daher hier ein Poll.
(function initTierUI(attempt) {
  if (typeof window.updateUserTierUI === "function") {
    window.App.authState.setIdentity(window.auth.currentUser.uid);
    // Wie /user_status: Agent ist seit 2026-10-02 fuer jedes Konto offen.
    // Ohne diese Antwort bliebe der Zugang "pending", und der Sende-Waechter
    // fuer eine gespeicherte Agent-Wahl sperrte #sendButton dauerhaft.
    window.App.agentAccess = { uid: window.auth.currentUser.uid, allowed: true };
    window.updateUserTierUI('free', true);
    window.App.accountTier.set('free');
    window.App.authState.publish(window.auth.currentUser.uid);
    window.App.agentChat?.render?.();
    return;
  }
  if (attempt < 100) setTimeout(() => initTierUI(attempt + 1), 50);
})(0);
