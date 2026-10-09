// Auth identity/generation owner. Firebase supplies provider callbacks; this
// module owns the race-prevention state consumed by bookmarks and app views.
(function () {
  window.App = window.App || {};
  let uid = null;
  let generation = 0;
  let known = false;

  function snapshot() {
    return Object.freeze({ known, uid, generation });
  }

  function syncCompatibilityState() {
    window.__consensioAuthState = snapshot();
  }

  function setIdentity(nextUid) {
    const normalized = nextUid || null;
    if (normalized !== uid) {
      uid = normalized;
      generation += 1;
    }
    syncCompatibilityState();
    return generation;
  }

  // A bare "signed in on this browser" hint for the server: with it, opening
  // consens.io goes straight to /app instead of the landing page (see
  // routers/pages.py landing). It carries no identity; the login itself
  // stays in Firebase's browser storage.
  const APP_HINT = "consens_app";

  function rememberSignedIn(signedIn) {
    try {
      const secure = window.location.protocol === "https:" ? "; Secure" : "";
      document.cookie = signedIn
        ? `${APP_HINT}=1; Max-Age=31536000; Path=/; SameSite=Lax${secure}`
        : `${APP_HINT}=; Max-Age=0; Path=/; SameSite=Lax${secure}`;
    } catch (_) {
      // Cookies blocked: the landing page simply stays the entry point.
    }
  }

  function publish(nextUid) {
    known = true;
    uid = nextUid || null;
    rememberSignedIn(!!uid);
    syncCompatibilityState();
    window.dispatchEvent(new CustomEvent("consensio:auth-state", {
      detail: window.__consensioAuthState
    }));
  }

  function isCurrent(expectedUid, expectedGeneration, providerUid) {
    return expectedGeneration === generation
      && !!expectedUid
      && uid === expectedUid
      && providerUid === expectedUid;
  }

  syncCompatibilityState();
  window.App.authState = Object.freeze({
    get uid() { return uid; },
    get generation() { return generation; },
    get known() { return known; },
    setIdentity,
    publish,
    isCurrent,
    snapshot
  });
})();

