import { initializeApp } from "https://www.gstatic.com/firebasejs/9.22.0/firebase-app.js";
import { getAuth, signInWithEmailAndPassword, signOut, onAuthStateChanged, sendPasswordResetEmail, sendEmailVerification, onIdTokenChanged } from "https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js";
import {
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  setPersistence,
  browserLocalPersistence,
  browserSessionPersistence,
} from "https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js";

// Loaded as part of the content-addressed head group. Keeping this dependency
// in bundles.json means source mode cannot serve a stale nested module import.
const {
  showEmailVerificationGate,
  hideEmailVerificationGate,
} = window.App.emailVerification;

const googleProvider = new GoogleAuthProvider();
// Optional: Kontoauswahl erzwingen
googleProvider.setCustomParameters({ prompt: "select_account" });

if (!window.FIREBASE_CONFIG || !window.FIREBASE_CONFIG.apiKey) {
  console.error("[FATAL] FIREBASE_CONFIG fehlt/leer. Abbruch (kein Auto-Init).", window.FIREBASE_CONFIG);
  // Optional: UI-Hinweis anzeigen
  const el = document.getElementById("loginError");
  if (el) el.textContent = "Init failed: Missing Firebase config.";
  // return;  // <- wenn du sicher abbrechen willst
}

// Initialisiere Firebase mit der globalen Konfiguration, die aus dem HTML kommt
const app = initializeApp(window.FIREBASE_CONFIG);

// Initialisiere Auth
const auth = getAuth(app);
window.auth = auth;

function trackAppEvent(eventName, eventData = {}) {
  if (typeof window.trackUmamiEvent === "function") {
    window.trackUmamiEvent(eventName, eventData);
  }
}

// Core events (docs/analytics.md): "signup" for a new account, "login" for
// a returning one. Google tells the two apart; the auth_* events stay as
// the detailed record of each attempt.
// A first Google sign-in creates the account, so both timestamps match.
// (Read from metadata rather than getAdditionalUserInfo: the test doubles of
// the auth module export only what the app already imports.)
function trackGoogleSignIn(result) {
  let isNew = false;
  try {
    const meta = result?.user?.metadata || {};
    const created = Date.parse(meta.creationTime), last = Date.parse(meta.lastSignInTime);
    isNew = Number.isFinite(created) && Number.isFinite(last) && Math.abs(last - created) < 60000;
  } catch (_) {}
  trackAppEvent(isNew ? "signup" : "login", { method: "google" });
}

// Der Bestaetigungslink soll nicht in einer Firebase-Sackgasse enden, sondern
// zurueck in die App fuehren — dort steht die getippte Frage noch im Feld.
function verificationEmailSettings() {
  return {
    url: `${window.location.origin}/app?verified=1`,
    handleCodeInApp: false,
  };
}

function sendVerificationMail(user) {
  return sendEmailVerification(user, verificationEmailSettings());
}

// Firebase haelt emailVerified aus dem zuletzt geholten Token. Wer den Link
// gerade in einem anderen Tab geklickt hat, ist also serverseitig laengst
// bestaetigt, waehrend das lokale Objekt noch "false" sagt. reload() holt den
// echten Stand; das erzwungene Token loest onIdTokenChanged neu aus und die
// App faehrt ohne Neuladen in den verifizierten Zustand.
async function refreshVerificationState() {
  const current = auth.currentUser;
  if (!current) return false;
  await current.reload();
  if (!auth.currentUser?.emailVerified) return false;
  await auth.currentUser.getIdToken(true);
  return true;
}

// Logging out asks first, with the app's own question (App.confirm,
// confirm-dialog.js); the "Log out" entry of the account menu only calls
// openLogoutConfirm().
async function performLogout() {
  if (performLogout.inProgress) return;
  performLogout.inProgress = true;
  trackAppEvent("auth_logout_click");
  try {
    // Settings changed in the last moment still need the account's token;
    // sent beside the session cleanup, waited for at most 3 s. What does not
    // arrive is dropped with the account's values on sign-out.
    const settingsSent = window.App.userSettings.flush({ timeoutMs: 3000 });
    // A chat or a watch deleted a moment ago (its Undo still offered) is
    // deleted now, with this account's token; a watch kept running before.
    const deletesSent = Promise.race([
      Promise.allSettled([settleUndoableBookmarkDeletes(), window.App?.watchDashboard?.commitPending?.()]),
      new Promise(resolve => setTimeout(resolve, 3000))
    ]);
    // Clear the HttpOnly server session before dropping the Firebase identity.
    // If this request fails, keeping Firebase signed in avoids presenting a
    // false "logged out" state while the cookie could still authorize calls.
    const response = await fetch("/auth/session", {
      method: "DELETE",
      credentials: "same-origin",
      cache: "no-store"
    });
    if (!response.ok) throw new Error(`Session cleanup failed (${response.status})`);

    // Abort while the Firebase identity is still available. Cancel hooks can
    // then release prepared-but-unconsumed usage reservations with the run's
    // bound token; clearAll after signOut removes the remaining projections.
    window.App?.runRegistry?.cancelAll?.("logout");
    await settingsSent;
    await deletesSent;
    await signOut(auth);
    setActiveAuthIdentity(null);
    resetLoadedRunAfterLogout();
    clearAuthenticatedUiState();
    clearLocalProviderKeys();
  } catch (error) {
    console.error("Logout failed:", error);
    window.App?.toast?.({ message: "You couldn’t be logged out. You’re still logged in. Try again.", tone: "error" });
  } finally {
    performLogout.inProgress = false;
  }
}

async function openLogoutConfirm() {
  const confirmed = await window.App.confirm({
    title: "Log out of consens.io?",
    body: "You can log back in any time. Your chats stay saved to your account.",
    confirmLabel: "Log out",
  });
  if (confirmed) performLogout();
}

function resetLoadedRunAfterLogout() {
  // A response belongs to the authenticated session that loaded it. Abort
  // active streams first so a late SSE event cannot render it again after the
  // DOM and share/bookmark context have been cleared.
  window.App?.runRegistry?.clearAll?.("logout");
  window.clearResponseBoxes?.({ silent: true });
  window.clearPreparedBookmarkShareResult?.();
  window.App.state.set("currentEvidenceSources", [], "evidence");
  window.App.state.set("consensusCitationMeta", null, "consensus");
  window.App?.chatSession?.reset?.();
  window.App?.bookmarkSession?.reset?.();
  window.App?.sharedModal?.close?.();
  window.App?.watch?.resetAfterLogout?.();
  document.body.classList.add("is-hero");
  window.syncHeroResponseAccess?.();
}

// Standard-Persistenz global setzen (beim Laden, nicht im Click-Handler)
setPersistence(auth, browserLocalPersistence)
  .catch(() => setPersistence(auth, browserSessionPersistence))
  .catch(err => {
    console.error("[Auth] Failed to set persistence:", err);
  });

function renderMarkdownSafe(md) {
  const text = md || "";
  if (typeof window.marked?.parse !== "function" || typeof window.DOMPurify?.sanitize !== "function") {
    const node = document.createElement("div");
    node.textContent = text;
    window.App?.reportCriticalError?.({
      type: "dependency_unavailable",
      phase: "markdown_render",
      message: "Markdown renderer unavailable; displaying unformatted text.",
      details: "bookmark markdown"
    });
    return node.innerHTML;
  }
  const html = window.marked.parse(text);
  return window.DOMPurify.sanitize(html, {
    // nur sichere Protokolle für Links erlauben
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|tel:)/i
  });
}

// Kontostand: ein Tokenkonto pro Tag fuer alle Modi. Es lebt in
// App.tokenBudget (token-budget.js); /user_status und /usage liefern es als
// `token_budget`, genau wie jede Lauf-Antwort.

// merken, dass wir Bookmarks schon einmal geladen haben
let bookmarksLoaded = false;
let bookmarksNextCursor = null;
let bookmarksLoading = false;
let bookmarksLoadRequestId = 0;
let openedBookmarkId = null;
const bookmarkDetailCache = new Map();
// The chats opened last, as they were shown (detail plus transcript), newest
// last: switching back shows one at once and checks it in the background
// (openBookmark). Every save of a chat drops its entry.
const bookmarkViewCache = new Map();
const BOOKMARK_VIEW_CACHE_SIZE = 10;
const authState = window.App.authState;
let bookmarkViewEpoch = 0;
let accountMenuDocumentClickHandler = null;

// A pending bookmark fetch owns only the view epoch it started in. Selecting
// a live run or returning to the empty composer invalidates that fetch so its
// late response cannot replace the newer projection.
window.addEventListener("consensio:run-registry-change", event => {
  if (["created", "visible", "visible-cleared", "saved-view", "cleared"].includes(event.detail?.type)) {
    bookmarkViewEpoch += 1;
    // Whatever the view shows now, it is no longer a chat still loading.
    hideChatOpening();
    // Share/Watch rehydration is view-owned just like bookmark detail loading.
    // A late result from saved view A must not replace the result id projected
    // by live run B.
    clearPreparedBookmarkShareResult();
  }
});

function publishAuthState(uid) {
  authState.publish(uid);
}

function clearAccountMenuDocumentListener() {
  if (!accountMenuDocumentClickHandler) return;
  document.removeEventListener("click", accountMenuDocumentClickHandler);
  accountMenuDocumentClickHandler = null;
}

function setActiveAuthIdentity(uid) {
  return authState.setIdentity(uid);
}

function isCurrentAuthenticatedUser(uid, generation) {
  return authState.isCurrent(uid, generation, auth.currentUser?.uid);
}

function setBookmarksAccess(isLoggedIn) {
  const section = document.querySelector(".bookmarks-section");
  const toggle = document.getElementById("bookmarksToggle");
  const searchHead = document.querySelector(".sidebar-bookmarks-head");
  const searchTrigger = document.getElementById("bookmarkSearchTrigger");
  const search = document.getElementById("chatSearch");
  section?.classList.toggle("is-locked", !isLoggedIn);
  if (toggle) {
    toggle.disabled = !isLoggedIn;
    toggle.setAttribute("aria-disabled", String(!isLoggedIn));
    toggle.title = isLoggedIn ? "Show or hide your chats" : "Log in to keep your chats";
  }
  if (searchTrigger) {
    searchTrigger.disabled = !isLoggedIn;
    searchTrigger.setAttribute("aria-disabled", String(!isLoggedIn));
  }
  if (search) {
    search.disabled = !isLoggedIn;
    if (!isLoggedIn) search.value = "";
  }
  if (!isLoggedIn) {
    searchHead?.classList.remove("is-searching");
    searchTrigger?.setAttribute("aria-expanded", "false");
  }
}

const LEGACY_PROVIDER_KEY_STORAGE = [
    "openaiKey",
    "mistralKey",
    "anthropicKey",
    "geminiKey",
    "deepseekKey",
    "grokKey",
];

function clearLegacyProviderKeys() {
  LEGACY_PROVIDER_KEY_STORAGE.forEach(key => localStorage.removeItem(key));
}

function clearLocalProviderKeys() {
  ["openrouterKey", ...LEGACY_PROVIDER_KEY_STORAGE]
    .forEach(key => {
      localStorage.removeItem(key);
      const input = document.getElementById(key);
      if (input) input.value = "";
    });
}

// Einmalige Migration für bereits eingeloggte Nutzer, die seit der
// OpenRouter-Umstellung noch keinen Logout ausgeführt haben.
clearLegacyProviderKeys();

function clearAuthenticatedUiState() {
  bookmarkViewEpoch += 1;
  window.App?.runRegistry?.clearAll?.("auth_reset");
  clearAccountMenuDocumentListener();
  localStorage.removeItem("id_token");
  window.App?.usageRun?.clear?.();
  window.App.state.set("isUserPro", false, "userTier");
  window.App.tokenBudget?.clear?.();

  ["watchUsageDisplay", "countdownDisplay"]
    .forEach(id => {
      const node = document.getElementById(id);
      if (node) node.textContent = "";
    });
  window.App?.sidebarQuota?.setOpen?.(false);
  window.App?.sidebarQuota?.sync?.();

  const container = document.getElementById("bookmarksContainer");
  if (container) container.innerHTML = "";
  bookmarksLoaded = false;
  bookmarksNextCursor = null;
  bookmarksLoading = false;
  bookmarksLoadRequestId += 1;
  openedBookmarkId = null;
  bookmarkDetailCache.clear();
  bookmarkViewCache.clear();
  window.bookmarksData = [];
  window.App?.composerStarters?.clear?.();
  // The composer words remembered for the next first frame were this
  // account's (app-bootstrap.js), as is a status check still waiting.
  window.App?.firstFrame?.forget?.();
  clearStatusRetry();
  setBookmarksAccess(false);
}

// A status check that fails for a moment (network, a deploy, the tier
// service) must not swap Agent for Consensus under the reader for the rest of
// the session (Apple-Audit B8). The account then stays "being checked": Agent's
// composer stands (agent-chat.js expectingAgent), nothing is sent, the composer
// says so once a check has failed, and the check runs again by itself with a
// growing pause, at once when the browser is back online or the tab returns,
// or on "Try now". Only a refusal (4xx) settles it as no Agent.
const STATUS_RETRY_MS = [2000, 5000, 15000, 30000, 60000];
let statusRetry = null;

function clearStatusRetry() {
  if (statusRetry) window.clearTimeout(statusRetry.timer);
  statusRetry = null;
  if (window.App) window.App.agentAccessCheck = null;
}

function scheduleStatusRetry(user, generation, attempt) {
  if (statusRetry) window.clearTimeout(statusRetry.timer);
  const delay = STATUS_RETRY_MS[Math.min(attempt, STATUS_RETRY_MS.length - 1)];
  const run = async () => {
    if (statusRetry?.run !== run) return;
    window.clearTimeout(statusRetry.timer);
    if (!isCurrentAuthenticatedUser(user.uid, generation)) { clearStatusRetry(); return; }
    let token = null;
    try { token = await user.getIdToken(); } catch (_) { /* counted as a failed check below */ }
    if (statusRetry?.run !== run) return;
    if (!isCurrentAuthenticatedUser(user.uid, generation)) { clearStatusRetry(); return; }
    if (!token) { scheduleStatusRetry(user, generation, attempt + 1); return; }
    await checkUserStatusOnLoad(user, token, generation, attempt + 1);
  };
  statusRetry = { uid: user.uid, run, timer: window.setTimeout(run, delay) };
  window.App.agentAccessCheck = { uid: user.uid, failed: true, attempt };
  window.App.agentChat?.render?.();
  window.updateQuestionInputAccess?.();
}

window.App.retryAccountStatus = () => statusRetry?.run();
window.addEventListener("online", () => statusRetry?.run());
document.addEventListener("visibilitychange", () => { if (!document.hidden) statusRetry?.run(); });

async function checkUserStatusOnLoad(user, token, generation, attempt = 0) {
  if (!user || !token) return false;
  let loaded = false;
  let refused = false;

  try {
    const response = await fetch("/user_status", {
      method: "GET",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
      }
    });
    if (!isCurrentAuthenticatedUser(user.uid, generation)) return;

    // A refusal is an answer; a server or network error is not.
    refused = response.status >= 400 && response.status < 500;
    if (response.ok) {
      const data = await response.json();
      if (!isCurrentAuthenticatedUser(user.uid, generation)) return;

      loaded = true;
      clearStatusRetry();
      // The operator's own browsers leave the Umami numbers (docs/analytics.md).
      if (data.is_admin === true) window.consensioAnalytics?.excludeOperator?.();
      // Token and cost figures (.admin-only) are for the operator only (Apple-Audit H4).
      document.body.classList.toggle("viewer-is-admin", data.is_admin === true);
      // 1. Konto sofort zeigen: das Tokenkonto des Tages.
      window.App.state.set("isUserPro", data.is_pro, "userTier");
      window.App.tokenBudget?.apply?.(data.token_budget, { uid: user.uid, authoritative: true });

      // 2. UI AKTUALISIEREN

      // "is_pro" ist seit der Plus-Stufe kein vollstaendiger Status mehr: es
      // heisst nur "Frontier-Modelle" und ist fuer Plus false.
      // Wer hier weiterhin nur das Flag durchreicht, macht aus jedem
      // Plus-Konto beim Laden ein Free-Konto. /user_status liefert "tier".
      const tier = data.tier ?? data.is_pro;
      window.App.agentAccess = { uid: user.uid, allowed: data.agent_access === true };
      window.App.agentChat?.render?.();

      // A) Der saubere Weg (falls vorhanden):
      if (typeof window.updateUserTierUI === "function") {
          window.updateUserTierUI(tier, true);
      }
      // Die Stufe des KONTOS -- getrennt von der Stufe auf dem Schirm, die ein
      // geoeffneter Lauf mitbringt. Sie faerbt das Konto-Kuerzel.
      window.App?.accountTier?.set?.(tier);
      // Premium Agent models unlock with the tier, which arrives after access.
      window.App.agentChat?.render?.();

      // B) FALLBACK -- nur wenn es den sauberen Weg oben nicht gibt. Frueher
      // lief er immer und schrieb danach das Ergebnis von updateUserTierUI
      // wieder um: Plus verlor sein Badge und bekam den Free-Hinweis.
      if (typeof window.updateUserTierUI !== "function") {
        const badge = document.getElementById("proBadge");
        const upgradeLink = document.getElementById("upgradeLink");
        const isPro = data.is_pro === true;
        if (badge) badge.style.display = isPro ? "inline-block" : "none";
        if (upgradeLink) upgradeLink.style.display = isPro ? "none" : "inline-flex";
        document.querySelectorAll('.premium-option').forEach(option => {
          option.disabled = !isPro;
          option.textContent = option.textContent
            .replace(/^Pro:\s*/i, '')
            .replace(' (Pro only)', '')
            .trim();
          if (option.disabled && option.selected) option.parentNode.selectedIndex = 0;
        });
      }
    }
  } catch (error) {
    console.error("Fehler beim User-Status Check:", error);
  }
  // Not answered: asked again (see STATUS_RETRY_MS). Refused: no Agent for
  // this session; the mode selector then shows Consensus, so nothing is sent
  // differently unseen.
  if (isCurrentAuthenticatedUser(user.uid, generation) && window.App?.agentAccess?.uid !== user.uid) {
    if (!loaded && !refused) {
      scheduleStatusRetry(user, generation, attempt);
    } else {
      clearStatusRetry();
      window.App.agentAccess = { uid: user.uid, allowed: false };
      window.App.agentChat?.render?.();
    }
  }
  return loaded;
}

// The signed-in user object (with its uid + auth generation) whose UI this
// tab already set up. Firebase keeps the same User instance across its token
// refreshes; a new sign-in brings a new one.
let initializedAuthSession = null;

onIdTokenChanged(auth, async (user) => {
  const loginContainer = document.getElementById("loginContainer");
  const usageOptions   = document.getElementById("usageOptions");
  const previousAuthUid = authState.uid;
  const generation = setActiveAuthIdentity(user?.emailVerified ? user.uid : null);

  if (user) {
    // Unbestaetigt: kein Token persistieren, keine authentifizierten Calls —
    // aber auch KEIN Rauswurf mehr. Der Nutzer bleibt angemeldet, sieht die
    // App und den Bestaetigungs-Streifen. Ausgeloggt zu werden, waehrend man
    // im Postfach sucht, war der teuerste Moment im ganzen Funnel.
    if (!user.emailVerified) {
      // Kann sein, dass der Link gerade geklickt wurde und nur das lokale
      // Objekt veraltet ist. Ergibt der frische Stand "bestaetigt", laeuft
      // dieser Handler gleich noch einmal — dann durch den verifizierten Ast.
      let becameVerified = false;
      try {
        becameVerified = await refreshVerificationState();
      } catch (_) {
        // Offline oder gedrosselt: dann eben der Streifen.
      }
      if (becameVerified) return;
      // reload() hat den Handler womoeglich schon neu ausgeloest (dann
      // bestaetigt): der neuere Lauf gehoert der Seite, dieser raeumt nichts ab.
      if (generation !== authState.generation) return;

      try { localStorage.removeItem("id_token"); } catch (_) {}
      resetLoadedRunAfterLogout();
      clearAuthenticatedUiState();
      if (previousAuthUid) clearLocalProviderKeys();
      window.App.userSettings.stop();
      fetch("/auth/session", {
        method: "DELETE",
        credentials: "same-origin",
        cache: "no-store"
      }).catch(() => {});
      showEmailVerificationGate({
        email: user.email || "",
        onResend: () => {
          trackAppEvent("auth_verification_resend");
          return sendVerificationMail(auth.currentUser || user);
        },
        onRecheck: async () => {
          const verified = await refreshVerificationState();
          trackAppEvent("auth_verification_recheck", { verified });
          return verified;
        },
        onSignOut: () => {
          trackAppEvent("auth_verification_gate_sign_out");
          signOut(auth).catch(error => console.error("Sign-out from verification gate failed:", error));
        },
      });
      trackAppEvent("auth_verification_gate_shown");
      if (typeof window.updateQuestionInputAccess === "function") {
        window.updateQuestionInputAccess();
      }
      // resetLoadedRunAfterLogout() hat den Composer eben geleert; die Frage,
      // auf die dieser Nutzer wartet, gehoert wieder hinein.
      window.App?.restoreQuestionDraft?.();
      if (usageOptions) usageOptions.style.display = "none";
      setBookmarksAccess(false);
      if (loginContainer) {
        loginContainer.innerHTML = "";
        loginContainer.hidden = true;
      }
      // Die Gast-Buttons oben rechts waeren hier tote Knoepfe (openAuthModal
      // steigt bei bestehender Session aus). Der Ausweg steht im Streifen.
      const unverifiedTopActions = document.getElementById("authTopActions");
      if (unverifiedTopActions) unverifiedTopActions.hidden = true;
      publishAuthState(null);
      return; // <--- ganz wichtig
    }

    hideEmailVerificationGate();
    // Signed in (also on the way back from Google's redirect): the dialog
    // has done its job.
    closeAuthModal();

    if (previousAuthUid && previousAuthUid !== user.uid) {
      resetLoadedRunAfterLogout();
      clearAuthenticatedUiState();
      clearLocalProviderKeys();
      window.App.userSettings.stop();
    }

    // ab hier nur noch verifizierte Nutzer
    let token;
    try {
      token = await user.getIdToken(/* forceRefresh= */ false);
    } catch (_) {
      if (!isCurrentAuthenticatedUser(user.uid, generation)) return;
      document.documentElement.dataset.authUnavailable = "true";
      // This callback can run before the deferred app/popup module. Keep a
      // persistent, usable recovery control in the already parsed auth shell.
      if (loginContainer) {
        loginContainer.replaceChildren();
        loginContainer.hidden = false;
        const message = document.createElement("p");
        message.setAttribute("role", "status");
        message.textContent = "Your session could not be refreshed. Check your connection and reload.";
        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "btn";
        retry.textContent = "Reload";
        retry.addEventListener("click", () => window.location.reload());
        loginContainer.append(message, retry);
      }
      const watchUsage = document.getElementById("watchUsageDisplay");
      if (watchUsage) watchUsage.textContent = "—";
      window.App.tokenBudget?.markStale?.();
      const bookmarks = document.getElementById("bookmarksContainer");
      if (bookmarks?.querySelector(".skeleton")) bookmarks.replaceChildren();
      return;
    }
    if (!isCurrentAuthenticatedUser(user.uid, generation)) return;
    delete document.documentElement.dataset.authUnavailable;
    try { localStorage.setItem("id_token", token); } catch (_) {}
    if (typeof window.updateQuestionInputAccess === "function") {
      window.updateQuestionInputAccess();
    }

    let sessionCookieSet = false;
    try {
      // Dieser Call übernimmt nun die Arbeit für ALLE Login-Arten (Google, Email, Reload)
      const res = await fetch("/confirm-registration", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: token })
      });
      sessionCookieSet = res.ok;
      
      if (!res.ok) {
        // Hilft dir beim Debuggen: Was genau sagt das Backend?
        const errData = await res.json();
        console.warn("Registration Check Failed:", errData);
      }
    } catch (err) {
      console.error("Error during confirm-registration:", err);
    }
    // Signed out or switched while waiting: a newer run owns the page.
    if (!isCurrentAuthenticatedUser(user.uid, generation)) return;
    // Sent here to sign in by a private page (/app?next=/s/...): the session
    // cookie it needs is set now, so go back to it.
    if (sessionCookieSet && SIGNED_IN_RETURN) {
      window.location.replace(SIGNED_IN_RETURN);
      return;
    }

    // Firebase refreshes the ID token hourly and fires this handler again
    // for the same session. The session cookie above needs the new token;
    // status, usage, bookmarks, watches and the account menu are current.
    // Reloading them cost Firestore reads every hour in every open tab and
    // redrew the account menu under the user's pointer.
    const sessionKey = { user, key: `${user.uid}:${generation}` };
    if (initializedAuthSession?.user === user && initializedAuthSession.key === sessionKey.key) return;

    // The account's settings (run mode, models, display): loaded beside the
    // status check, applied by the modules as they arrive.
    window.App.userSettings.start({ uid: user.uid, getToken: () => user.getIdToken() });
    const statusLoaded = await checkUserStatusOnLoad(user, token, generation);
    if (!isCurrentAuthenticatedUser(user.uid, generation)) return;

    // 2) /usage carries the same tier and token account as /user_status; it
    // is only the second chance when that request failed.
    if (!statusLoaded) fetchUsageData(token, user.uid, generation);

    // 3) Bookmarks einmal pro Login laden
    if (!bookmarksLoaded) {
      bookmarksLoaded = await loadBookmarks();
    }
    if (!isCurrentAuthenticatedUser(user.uid, generation)) return;
    setBookmarksAccess(true);
    // The sidebar's watch count: the list the sign-in already loads (watch.js
    // on the auth state, the Watches page) is taken as it is; only a missing
    // one is fetched. A forced reload here was a second list request on
    // every sign-in (review 2).
    window.App?.watch?.loadState?.().catch(() => {});

    // 4) Usage-UI anzeigen
    if (usageOptions) {
      usageOptions.style.display = "block";
    }

    // Account-Reiter in den Settings einblenden. Seit die Einstellungen
    // Tabs sind, gehoert die Sichtbarkeit des PANELS allein dem Tab-Controller
    // (app-ui.js); hier wird nur noch der Reiter selbst freigegeben. Ein
    // inline gesetztes display wuerde den Controller sonst uebersteuern.
    window.App?.settingsTabs?.setTabAvailable?.("accountSettingsSection", true);

    // View-Switch-Pill ist immer sichtbar (auch ausgeloggt) — hier nichts tun.
    // Auth-Buttons oben rechts sind nur für Gäste.
    const authTopActions = document.getElementById("authTopActions");
    if (authTopActions) authTopActions.hidden = true;
    if (loginContainer) loginContainer.hidden = false;

    // 5) E‑Mail & Logout als Popup (öffnet aus der Sidebar-Fußzeile nach oben).
    // Echte Buttons statt span/a ohne href: nur so sind Öffner und Einträge
    // per Tab erreichbar — Logout gibt es nur hier.
    const emailInitial = user.email.charAt(0).toUpperCase();
    clearAccountMenuDocumentListener();
    loginContainer.innerHTML = `
      <div class="email-container">
        <button type="button" id="emailIcon" class="email-icon" aria-haspopup="menu" aria-expanded="false" aria-controls="emailPopup" aria-label="Open account menu"></button>
        <div id="emailPopup" aria-label="Account" class="email-popup" role="menu" hidden>
          <div class="popup-content" role="none">
            <span class="user-email" role="none">
              <span class="user-email-address"></span>
              <!-- Die Aufloesung zur Farbe am Kuerzel: hier steht der Name der
                   Stufe. user-tier.js fuellt und blendet ihn (Free: leer). -->
              <span id="accountTierLabel" class="pro-badge account-tier-label" hidden></span>
            </span>
            <button type="button" id="sharedLinksButton" class="top-bar-about" role="menuitem" tabindex="-1">Shared links</button>
            <button type="button" id="watchedLinksButton" class="top-bar-about" role="menuitem" tabindex="-1">Watches</button>
            <button type="button" id="logoutButton" class="top-bar-about" role="menuitem" tabindex="-1">Log out</button>
          </div>
        </div>
      </div>
    `;
    // Nutzerdaten nie in Markup interpolieren.
    const emailIcon = document.getElementById("emailIcon");
    const emailPopup = document.getElementById("emailPopup");
    emailIcon.textContent = emailInitial;
    emailPopup.querySelector(".user-email-address").textContent = user.email;
    // innerHTML hat #emailIcon gerade ersetzt: die Klasse, die die Kontostufe
    // traegt, ist mit dem alten Knoten weg und muss neu gesetzt werden.
    window.App?.accountTier?.render?.();

    // The address beside the initial opens the same menu (sidebar footer).
    const accountIdentity = document.getElementById("accountIdentity");
    const logoutButton = document.getElementById("logoutButton");
    const sharedLinksButton = document.getElementById("sharedLinksButton");
    const watchedLinksButton = document.getElementById("watchedLinksButton");
    const accountMenuItems = () => Array.from(emailPopup.querySelectorAll('[role="menuitem"]'));
    // Wer das Menue geoeffnet hat, bekommt beim Schliessen per Escape den Fokus
    // zurueck (Kuerzel oder die Adresse in der Fusszeile).
    let accountMenuOpener = emailIcon;

    function focusAccountMenuItem(index) {
      const items = accountMenuItems();
      if (!items.length) return;
      items[(index + items.length) % items.length].focus();
    }

    // One of the app's popovers (App.popover): opening it closes any other
    // menu or card, and it comes out of the control that opened it.
    window.App.popover?.register(emailPopup, { close: () => setAccountMenuOpen(false) });

    function setAccountMenuOpen(isOpen, { opener = null, focus = null } = {}) {
      if ((!emailPopup.hidden) !== isOpen) {
        if (isOpen && opener) accountMenuOpener = opener;
        if (isOpen) window.App.popover?.opened(emailPopup, { trigger: accountMenuOpener });
        else window.App.popover?.closed(emailPopup);
        emailPopup.hidden = !isOpen;
        emailIcon.setAttribute("aria-expanded", String(isOpen));
        if (accountIdentity) accountIdentity.setAttribute("aria-expanded", String(isOpen));
      }
      if (isOpen && focus === "first") focusAccountMenuItem(0);
      if (isOpen && focus === "last") focusAccountMenuItem(-1);
      if (!isOpen && focus === "opener") accountMenuOpener?.focus();
    }

    function toggleAccountMenu(opener) {
      const willOpen = emailPopup.hidden;
      setAccountMenuOpen(willOpen, { opener, focus: willOpen ? "first" : null });
    }

    function handleAccountOpenerKeydown(e, opener) {
      if (e.key === "Escape" && !emailPopup.hidden) {
        e.preventDefault();
        setAccountMenuOpen(false, { focus: "opener" });
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setAccountMenuOpen(true, { opener, focus: e.key === "ArrowDown" ? "first" : "last" });
      }
    }

    if (accountIdentity) {
      accountIdentity.textContent = user.email;
      accountIdentity.title = user.email;
      accountIdentity.setAttribute("aria-label", `Account menu for ${user.email}`);
      accountIdentity.setAttribute("aria-expanded", "false");
      accountIdentity.hidden = false;
      accountIdentity.onclick = e => { e.stopPropagation(); toggleAccountMenu(accountIdentity); };
      accountIdentity.onkeydown = e => handleAccountOpenerKeydown(e, accountIdentity);
    }
    const accountPlanLine = document.getElementById("accountPlanLine");
    if (accountPlanLine) accountPlanLine.hidden = false;

    // Ein <button> loest Enter/Leertaste selbst als click aus.
    emailIcon.addEventListener("click", e => {
      e.stopPropagation();
      toggleAccountMenu(emailIcon);
    });
    emailIcon.addEventListener("keydown", e => handleAccountOpenerKeydown(e, emailIcon));

    // Menue-Tastatur: Pfeile wandern (mit Umlauf), Home/End springen, Escape
    // schliesst und gibt den Fokus zurueck, Tab verlaesst das Menue.
    emailPopup.addEventListener("keydown", e => {
      const items = accountMenuItems();
      const index = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const step = e.key === "ArrowDown" ? 1 : -1;
        focusAccountMenuItem(index < 0 ? (step > 0 ? 0 : -1) : index + step);
      } else if (e.key === "Home" || e.key === "End") {
        e.preventDefault();
        focusAccountMenuItem(e.key === "Home" ? 0 : -1);
      } else if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        setAccountMenuOpen(false, { focus: "opener" });
      } else if (e.key === "Tab") {
        setAccountMenuOpen(false);
      }
    });

    // Übersicht der geteilten Consensus-Links direkt aus dem User-Menü öffnen.
    // stopPropagation ist wichtig: der umschließende #loginContainer hat einen
    // Klick-Handler, der eingeloggte Nutzer sonst ausloggt.
    if (sharedLinksButton) {
      sharedLinksButton.addEventListener("click", e => {
        e.stopPropagation();
        setAccountMenuOpen(false);
        if (typeof window.openShareDialog === "function") {
          window.openShareDialog("list");
        }
      });
    }

    if (watchedLinksButton) {
      watchedLinksButton.addEventListener("click", e => {
        e.stopPropagation();
        setAccountMenuOpen(false);
        if (typeof window.openWatchDialog === "function") {
          window.openWatchDialog("list");
        }
      });
    }

    logoutButton.addEventListener("click", e => {
      // stopPropagation: Klick soll weder das Icon-Toggle noch den
      // loginContainer-Handler treffen.
      e.stopPropagation();
      setAccountMenuOpen(false);
      openLogoutConfirm();
    });

    accountMenuDocumentClickHandler = e => {
      if (!loginContainer.contains(e.target)) {
        setAccountMenuOpen(false);
      }
    };
    document.addEventListener("click", accountMenuDocumentClickHandler);
    initializedAuthSession = sessionKey;
    publishAuthState(user.uid);

    } else {
        // Cleanup bei Logout
        initializedAuthSession = null;
        hideEmailVerificationGate();
        resetLoadedRunAfterLogout();
        clearAuthenticatedUiState();
        if (previousAuthUid) clearLocalProviderKeys();
        window.App.userSettings.stop();
        fetch("/auth/session", {
          method: "DELETE",
          credentials: "same-origin",
          cache: "no-store"
        }).catch(() => {});
        if (typeof window.updateQuestionInputAccess === "function") {
          window.updateQuestionInputAccess();
        }
        // Guests type too: resetLoadedRunAfterLogout() just emptied the
        // composer, and a question written before a reload belongs back in it.
        window.App?.restoreQuestionDraft?.();
        loginContainer.innerHTML = "";
        loginContainer.hidden = true;

        // Gäste: Login/Sign-up-Buttons oben rechts einblenden (View-Switch
        // bleibt sichtbar; Watches bittet beim Klick um Login).
        const authTopActionsOff = document.getElementById("authTopActions");
        if (authTopActionsOff) authTopActionsOff.hidden = false;

        const upgradeLinkOff = document.getElementById("upgradeLink");
        if (upgradeLinkOff) upgradeLinkOff.style.display = "none";
        const accountIdentityOff = document.getElementById("accountIdentity");
        if (accountIdentityOff) { accountIdentityOff.hidden = true; accountIdentityOff.textContent = ""; accountIdentityOff.onclick = null; }
        const accountPlanLineOff = document.getElementById("accountPlanLine");
        if (accountPlanLineOff) accountPlanLineOff.hidden = true;

        if (usageOptions) usageOptions.style.display = "none";

        window.App?.settingsTabs?.setTabAvailable?.("accountSettingsSection", false);

        // A) Badge verstecken (Direkter Zugriff)
        const badge = document.getElementById("proBadge");
        if (badge) badge.style.display = "none";

        // B) Kein Konto, kein Kontostand.
        window.App.tokenBudget?.clear?.();

        // C) Premium Modelle wieder sperren (HIER WAR DER FEHLER)
        const premiumOptions = document.querySelectorAll('.premium-option');
        premiumOptions.forEach(option => {
            option.disabled = true;
            option.textContent = option.textContent
                .replace(/^Pro:\s*/i, '')
                .replace(' (Pro only)', '')
                .trim();

            // Falls ausgewählt (Cache-Problem), zurücksetzen auf Standard
            if (option.selected) {
                option.parentNode.selectedIndex = 0;
            }
        });

        if (typeof window.updateUserTierUI === "function") {
            window.updateUserTierUI(false, false); // isPro=false, isLoggedIn=false
        }
        window.App?.accountTier?.set?.("free");
        document.body.classList.remove("viewer-is-admin");
        publishAuthState(null);
        // Only now is the session known to be gone. The field was drawn
        // above while the page still expected the account this browser
        // remembered (app-bootstrap.js expectedSession): an ended session
        // (password changed elsewhere, account disabled, a Google sign-in
        // that came back without a user) left it grey and locked under
        // "Log in" until a reload (review 1, regression of B4).
        if (typeof window.updateQuestionInputAccess === "function") {
          window.updateQuestionInputAccess();
        }
      }
    });

async function fetchUsageData(token, uid, generation) {
  try {
    const response = await fetch("/usage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: token })
    });
    if (!isCurrentAuthenticatedUser(uid, generation)) return false;
    const data = await response.json();
    if (!response.ok || !isCurrentAuthenticatedUser(uid, generation)) return false;

    // /usage is an authoritative tier snapshot too. This lets a Pro account
    // recover in the same session when the earlier /user_status request had a
    // transient failure.
    const isPro = data.is_pro === true;
    // Auch hier gilt: "is_pro" allein macht aus Plus ein Free-Konto.
    const tier = data.tier ?? isPro;
    window.App.state.set("isUserPro", isPro, "userTier");
    if (typeof window.updateUserTierUI === "function") {
      window.updateUserTierUI(tier, true);
    }
    window.App?.accountTier?.set?.(tier);
    window.App.agentChat?.render?.();
    // /usage is authoritative: after the UTC reset or an admin reset the
    // account may legitimately go back up. token-budget.js is in the head
    // group, so it exists before any module response arrives.
    window.App.tokenBudget?.apply?.(data.token_budget, { uid, authoritative: true });
    return true;
  } catch (err) {
    if (isCurrentAuthenticatedUser(uid, generation)) {
      console.error("Error when retrieving the quota:", err);
    }
    return false;
  }
}

window.refreshUsageData = async function () {
  const requestUser = auth.currentUser;
  if (!requestUser) return false;
  const requestUid = requestUser.uid;
  const requestGeneration = authState.generation;
  try {
    const token = await requestUser.getIdToken(false);
    if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return false;
    return await fetchUsageData(token, requestUid, requestGeneration);
  } catch (error) {
    if (isCurrentAuthenticatedUser(requestUid, requestGeneration)) {
      console.error("Could not refresh usage after UTC reset:", error);
    }
    return false;
  }
};

// ---------------------------------------------------------------------------
// Login / sign-up dialog (#loginModal in index.html, style in auth-modal.css)
//
// The dialog decides whether a newcomer stays. One form with two tabs (Log in
// | Sign up), Google first, every action shows that it is working, errors sit
// next to the control that caused them, and Enter submits.
// ---------------------------------------------------------------------------

const REMEMBERED_EMAIL_KEY = "consensio.authEmail";
const GOOGLE_REDIRECT_KEY = "consensio.googleRedirectPending";
// Same rule as RegisterRequest in app/api/routers/auth.py.
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;
const NETWORK_ERROR_MESSAGE = "Network error. Please check your internet connection and try again.";
const WRONG_CREDENTIALS_MESSAGE =
  "Email or password is not correct. Signed up with Google? Use “Continue with Google” above.";

const AUTH_MODE_COPY = {
  login: { title: "Log in to consens.io", lead: "Pick up where you left off." },
  register: {
    title: "Create your free account",
    lead: "Ask once and see where leading AI models agree and where they don’t.",
  },
};
// Opened for a reason (a guest's Send): that reason replaces the lead on both
// tabs until the dialog closes.
let authContextLead = "";

function mapFirebaseLoginError(error) {
  // SDK 9.22 predates Firebase's e-mail enumeration protection: a wrong
  // password arrives as auth/internal-error carrying INVALID_LOGIN_CREDENTIALS
  // and used to read "An error occurred" instead of "wrong password".
  const message = String(error?.message || "");
  switch (error?.code) {
    case "auth/user-not-found":
    case "auth/wrong-password":
    case "auth/invalid-credential":
    case "auth/invalid-login-credentials":
      return WRONG_CREDENTIALS_MESSAGE;
    case "auth/invalid-email":
      return "Enter a valid email address.";
    case "auth/user-disabled":
      return "This account is blocked. Write to contact@consens.io if this is a mistake.";
    case "auth/too-many-requests":
      return "Too many attempts to log in. Wait a few minutes or reset your password.";
    case "auth/network-request-failed":
      return NETWORK_ERROR_MESSAGE;
    default:
      if (/INVALID_LOGIN_CREDENTIALS|INVALID_PASSWORD|EMAIL_NOT_FOUND/.test(message)) {
        return WRONG_CREDENTIALS_MESSAGE;
      }
      return "Logging in didn’t work. Try again.";
  }
}

function mapPasswordResetError(error) {
  switch (error?.code) {
    case "auth/invalid-email":
    case "auth/missing-email":
      return "Enter a valid email address.";
    case "auth/too-many-requests":
      return "Too many requests. Wait a few minutes and try again.";
    case "auth/network-request-failed":
      return NETWORK_ERROR_MESSAGE;
    default:
      return "The password couldn’t be reset. Try again.";
  }
}

function mapGoogleSignInError(error) {
  switch (error?.code) {
    case "auth/popup-closed-by-user":
    case "auth/cancelled-popup-request":
    case "auth/user-cancelled":
      return "The Google window closed before you were logged in. Try again, or use your email below.";
    case "auth/popup-blocked":
      return "Your browser blocked the Google window. Allow pop-ups for consens.io and try again, or use your email below.";
    case "auth/web-storage-unsupported":
    case "auth/operation-not-supported-in-this-environment":
      return "This browser blocks what logging in with Google needs. Open consens.io in Safari or Chrome, or use your email below.";
    case "auth/user-disabled":
      return "This account is blocked. Write to contact@consens.io if this is a mistake.";
    case "auth/too-many-requests":
      return "Too many attempts. Please wait a few minutes and try again.";
    case "auth/network-request-failed":
      return NETWORK_ERROR_MESSAGE;
    default:
      return "Logging in with Google didn’t work this time. Try again, or use your email below.";
  }
}

// --- Environment --------------------------------------------------------

function isCoarsePointer() {
  return Boolean(window.matchMedia?.("(pointer: coarse)")?.matches);
}

function isMobileBrowser() {
  const ua = navigator.userAgent || "";
  return /Android|iPhone|iPad|iPod|Mobile/i.test(ua)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

// Google refuses OAuth inside embedded app browsers ("disallowed_useragent"),
// and their pop-ups go nowhere. Visitors from a LinkedIn post land exactly
// there, so they get a way out instead of a dead Google button.
function inAppBrowserName() {
  const ua = navigator.userAgent || "";
  if (/LinkedInApp/i.test(ua)) return "LinkedIn";
  if (/Instagram/i.test(ua)) return "Instagram";
  if (/FBAN|FBAV|FB_IAB|FBIOS/i.test(ua)) return "Facebook";
  if (/musical_ly|BytedanceWebview|TikTok/i.test(ua)) return "TikTok";
  if (/Snapchat/i.test(ua)) return "Snapchat";
  if (/\bLine\//.test(ua)) return "LINE";
  if (/; wv\)/.test(ua)) return "app";
  return "";
}

// Firebase's sign-in helpers are served from this very origin when
// FIREBASE_AUTH_DOMAIN names this host (app/api/routers/firebase_auth_proxy.py).
// Only then does the redirect flow survive Safari's storage partitioning, so
// only then do phones get the redirect instead of a pop-up tab.
function authDomainIsFirstParty() {
  return String(window.FIREBASE_CONFIG?.authDomain || "") === window.location.host;
}

function prefersGoogleRedirect() {
  return authDomainIsFirstParty() && isMobileBrowser();
}

function passwordSetupSettings() {
  return { url: `${window.location.origin}/app?setup=1`, handleCodeInApp: false };
}

function rememberEmail(email) {
  try { localStorage.setItem(REMEMBERED_EMAIL_KEY, email); } catch (_) {}
}

function rememberedEmail() {
  try { return localStorage.getItem(REMEMBERED_EMAIL_KEY) || ""; } catch (_) { return ""; }
}

function forgetRememberedEmail() {
  try { localStorage.removeItem(REMEMBERED_EMAIL_KEY); } catch (_) {}
}

// A fresh page starts the signed-in app from a clean slate (a guest's demo
// run does not belong to the account) and keeps the page the user was on.
async function continueSignedIn() {
  // A guest's question waiting for this sign-in goes out on the fresh page,
  // not in this one while it unloads (composer-invite.js).
  window.App.reloadingAfterSignIn = true;
  // The fresh page paints the account from its first frame
  // (app-bootstrap.js reads the stored token): without it the Google sign-in
  // came back as a guest page that turned into the app a second later
  // (Apple-Audit B4).
  try {
    const user = auth.currentUser;
    if (user?.emailVerified) localStorage.setItem("id_token", await user.getIdToken());
  } catch (_) { /* the fresh page still finds the session, one frame later */ }
  const url = new URL(window.location.href);
  url.searchParams.delete("setup");
  window.location.replace(url.pathname + url.search);
}

// --- Elements -----------------------------------------------------------

const formEl = document.getElementById("loginForm");
const titleEl = document.getElementById("authTitle");
const leadEl = document.getElementById("authLead");
const tabsEl = document.getElementById("authTabs");
const tabLoginEl = document.getElementById("authTabLogin");
const tabRegisterEl = document.getElementById("authTabRegister");
const singleMailNoteEl = document.getElementById("singleMailNote");

const emailEl = document.getElementById("loginEmail");
const passEl = document.getElementById("loginPassword");
const passFieldEl = document.getElementById("loginPasswordField");
const passRevealEl = document.getElementById("loginPasswordReveal");
const forgotRowEl = document.getElementById("forgotPasswordRow");
const forgotBtn = document.getElementById("forgotPasswordButton");

const loginBtn = document.getElementById("loginButton");
const confirmRegisterBtn = document.getElementById("confirmRegisterButton");
const loginNoticeEl = document.getElementById("loginNotice");
const loginErr = document.getElementById("loginError");
const registerErr = document.getElementById("registerError");

const googleBtn = document.getElementById("googleLoginButton");
const googleLabelEl = document.getElementById("googleLoginLabel");
const googleErr = document.getElementById("googleError");
const inAppNoticeEl = document.getElementById("inAppBrowserNotice");
const inAppNameEl = document.getElementById("inAppBrowserName");
const inAppHintEl = document.getElementById("inAppBrowserHint");
const inAppOpenEl = document.getElementById("inAppOpenBrowser");
const inAppCopyEl = document.getElementById("inAppCopyLink");

const registrationSuccessEl = document.getElementById("registrationSuccess");
const registrationSuccessEmailEl = document.getElementById("registrationSuccessEmail");
const registrationMailboxEl = document.getElementById("registrationMailboxLink");
const registrationResendBtn = document.getElementById("registrationResendButton");
const registrationChangeBtn = document.getElementById("registrationChangeButton");
const registrationStatusEl = document.getElementById("registrationStatus");
const registrationLoginBtn = document.getElementById("registrationLoginButton");

let lastRegisteredEmail = "";
let resendTimer = 0;

// --- Small state helpers -----------------------------------------------

function setButtonPending(button, isPending, pendingLabel) {
  if (!button) return;
  if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent.trim();
  button.disabled = isPending;
  button.setAttribute("aria-busy", String(isPending));
  button.textContent = isPending ? pendingLabel : button.dataset.idleLabel;
}

function setRegisterPending(isPending) {
  setButtonPending(confirmRegisterBtn, isPending, "Sending link…");
}

function setGooglePending(isPending, label = "Waiting for Google…") {
  googleBtn.disabled = isPending;
  googleBtn.setAttribute("aria-busy", String(isPending));
  googleLabelEl.textContent = isPending ? label : "Continue with Google";
}

function clearAuthMessages() {
  [loginErr, registerErr, googleErr, loginNoticeEl].forEach(node => { node.textContent = ""; });
  emailEl.removeAttribute("aria-invalid");
  passEl.removeAttribute("aria-invalid");
}

function showFieldError(target, field, message) {
  target.textContent = message;
  field.setAttribute("aria-invalid", "true");
  field.focus();
}

function hidePassword() {
  passEl.type = "password";
  passRevealEl.textContent = "Show";
  passRevealEl.setAttribute("aria-pressed", "false");
}

function setMode(mode) {
  const isRegister = mode === "register";
  window.clearInterval(resendTimer);
  formEl.dataset.mode = isRegister ? "register" : "login";
  formEl.hidden = false;
  tabsEl.hidden = false;
  registrationSuccessEl.hidden = true;
  setRegisterPending(false);
  setButtonPending(loginBtn, false);
  hidePassword();

  const copy = AUTH_MODE_COPY[formEl.dataset.mode];
  titleEl.textContent = copy.title;
  leadEl.textContent = authContextLead || copy.lead;
  [[tabLoginEl, !isRegister], [tabRegisterEl, isRegister]].forEach(([tab, selected]) => {
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });

  passFieldEl.hidden = isRegister;
  forgotRowEl.hidden = isRegister;
  singleMailNoteEl.classList.toggle("u-display-none", !isRegister);
  confirmRegisterBtn.classList.toggle("u-display-none", !isRegister);
  loginBtn.classList.toggle("u-display-none", isRegister);
  clearAuthMessages();
}

function selectAuthTab(mode) {
  if (formEl.dataset.mode === mode && !formEl.hidden) return;
  // Sign up hides the password row: the dialog follows its fields with one
  // height movement instead of jumping (Apple-Audit C9; App.watchUi.smoothHeight).
  const smooth = window.App?.watchUi?.smoothHeight;
  const box = formEl.closest(".auth-modal");
  if (smooth && box) smooth(box, () => setMode(mode));
  else setMode(mode);
  trackAppEvent("auth_mode_changed", { mode });
}

tabLoginEl.addEventListener("click", () => selectAuthTab("login"));
tabRegisterEl.addEventListener("click", () => selectAuthTab("register"));
tabsEl.addEventListener("keydown", event => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const next = event.key === "ArrowLeft" || event.key === "Home" ? tabLoginEl : tabRegisterEl;
  selectAuthTab(next === tabLoginEl ? "login" : "register");
  next.focus();
});

passRevealEl.addEventListener("click", () => {
  const show = passEl.type === "password";
  passEl.type = show ? "text" : "password";
  passRevealEl.textContent = show ? "Hide" : "Show";
  passRevealEl.setAttribute("aria-pressed", String(show));
  passEl.focus();
});

// One form for both tabs: Enter and the mobile keyboard's "Go" submit it,
// and the tab decides what that means.
formEl.addEventListener("submit", event => {
  event.preventDefault();
  if (formEl.dataset.mode === "register") handleRegister();
  else handleEmailLogin();
});

// --- Sign up: mailbox-only setup ----------------------------------------
//
// Existing and new addresses get the same answer and the same e-mail, so the
// form never tells a stranger whether an address has an account.

const MAILBOXES = [
  [/^(gmail|googlemail)\.com$/, "Gmail", "https://mail.google.com/mail/u/0/#inbox"],
  [/^(outlook|hotmail|live|msn)\.[a-z.]+$/, "Outlook", "https://outlook.live.com/mail/0/inbox"],
  [/^(yahoo|ymail)\.[a-z.]+$/, "Yahoo Mail", "https://mail.yahoo.com/"],
  [/^(icloud|me|mac)\.com$/, "iCloud Mail", "https://www.icloud.com/mail"],
  [/^gmx\.[a-z.]+$/, "GMX", "https://www.gmx.net/"],
  [/^web\.de$/, "WEB.DE", "https://web.de/"],
  [/^t-online\.de$/, "Telekom Mail", "https://email.t-online.de/"],
];

function mailboxFor(email) {
  const domain = String(email).split("@").pop().toLowerCase();
  const hit = MAILBOXES.find(([pattern]) => pattern.test(domain));
  return hit ? { name: hit[1], url: hit[2] } : null;
}

async function requestSetupLink(email) {
  try {
    const response = await fetch("/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email })
    });
    const data = await response.json().catch(() => ({}));
    if (response.ok && data.status === "check_inbox") return { ok: true };
    if (response.status === 429) {
      return { ok: false, message: "Too many attempts. Wait a minute and try again." };
    }
    if (response.status === 422) {
      return { ok: false, message: "Check the email address. It looks incomplete." };
    }
    return {
      ok: false,
      message: typeof data.detail === "string"
        ? data.detail
        : "We couldn’t send the link right now. Try again in a moment.",
    };
  } catch (error) {
    console.error("Registration request failed:", error);
    return { ok: false, message: "We couldn’t create your account. Check your connection and try again." };
  }
}

async function handleRegister() {
  if (confirmRegisterBtn.disabled) return;
  clearAuthMessages();
  const email = (emailEl.value || "").trim();
  if (!email) {
    showFieldError(registerErr, emailEl, "Enter your email address.");
    return;
  }
  if (!EMAIL_PATTERN.test(email)) {
    showFieldError(registerErr, emailEl, "Check the email address. It looks incomplete.");
    return;
  }
  trackAppEvent("auth_register_started");
  setRegisterPending(true);
  // Never try caller-chosen credentials here: that would reveal whether the
  // backend had just created the account.
  const result = await requestSetupLink(email);
  setRegisterPending(false);
  if (result.ok) {
    rememberEmail(email);
    showRegistrationSuccess(email);
    trackAppEvent("auth_register_result", { status: "success" });
    trackAppEvent("signup", { method: "email" });
  } else {
    registerErr.textContent = result.message;
    trackAppEvent("auth_register_result", { status: "error" });
  }
}

function startResendCooldown(seconds) {
  window.clearInterval(resendTimer);
  let left = seconds;
  const render = () => {
    registrationResendBtn.disabled = left > 0;
    registrationResendBtn.textContent = left > 0 ? `Send again in ${left} s` : "Send the link again";
  };
  render();
  resendTimer = window.setInterval(() => {
    left -= 1;
    render();
    if (left <= 0) window.clearInterval(resendTimer);
  }, 1000);
}

function showRegistrationSuccess(email) {
  lastRegisteredEmail = email;
  titleEl.textContent = "Check your inbox";
  leadEl.textContent = "One step left to your account.";
  registrationSuccessEmailEl.textContent = email;
  const mailbox = mailboxFor(email);
  registrationMailboxEl.hidden = !mailbox;
  if (mailbox) {
    registrationMailboxEl.href = mailbox.url;
    registrationMailboxEl.textContent = `Open ${mailbox.name}`;
  }
  registrationStatusEl.textContent = "";
  formEl.hidden = true;
  tabsEl.hidden = true;
  registrationSuccessEl.hidden = false;
  passEl.value = "";
  startResendCooldown(30);
  registrationSuccessEl.focus({ preventScroll: true });
}

registrationMailboxEl.addEventListener("click", () => {
  trackAppEvent("auth_register_open_inbox", { provider: registrationMailboxEl.textContent.replace(/^Open /, "") });
});

registrationResendBtn.addEventListener("click", async () => {
  if (!lastRegisteredEmail || registrationResendBtn.disabled) return;
  registrationResendBtn.disabled = true;
  registrationStatusEl.textContent = "Sending…";
  const result = await requestSetupLink(lastRegisteredEmail);
  registrationStatusEl.textContent = result.ok ? "Sent again. It can take a minute to arrive." : result.message;
  startResendCooldown(result.ok ? 60 : 20);
  trackAppEvent("auth_register_resend", { status: result.ok ? "success" : "error" });
});

registrationChangeBtn.addEventListener("click", () => {
  setMode("register");
  emailEl.value = lastRegisteredEmail;
  emailEl.focus();
  emailEl.select();
});

registrationLoginBtn.addEventListener("click", () => {
  setMode("login");
  if (lastRegisteredEmail) emailEl.value = lastRegisteredEmail;
  (emailEl.value ? passEl : emailEl).focus();
});

function handleForgotPassword() {
  clearAuthMessages();
  const email = (emailEl.value || "").trim();
  trackAppEvent("auth_password_reset_started");
  if (!EMAIL_PATTERN.test(email)) {
    showFieldError(loginErr, emailEl, "Enter your email address above, then tap “Forgot password?” again.");
    return;
  }
  const showSent = () => {
    rememberEmail(email);
    loginNoticeEl.textContent =
      `If an account exists for ${email}, a link to set a new password is on its way. Check your spam folder too.`;
    trackAppEvent("auth_password_reset_result", { status: "success" });
  };
  forgotBtn.disabled = true;
  sendPasswordResetEmail(auth, email, passwordSetupSettings())
    .catch(error => {
      // The way back into the app is a convenience; the e-mail is not.
      if (/continue-uri|unauthorized-domain/.test(error?.code || "")) return sendPasswordResetEmail(auth, email);
      throw error;
    })
    .then(showSent)
    .catch(error => {
      // "No such account" gets the same answer as a sent link.
      if (error?.code === "auth/user-not-found") {
        showSent();
        return;
      }
      loginErr.textContent = mapPasswordResetError(error);
      trackAppEvent("auth_password_reset_result", { status: "error" });
    })
    .finally(() => { forgotBtn.disabled = false; });
}

forgotBtn.addEventListener("click", handleForgotPassword);

// --- Log in with e-mail ---------------------------------------------------

async function handleEmailLogin() {
  if (loginBtn.disabled) return;
  clearAuthMessages();
  const email = (emailEl.value || "").trim();
  const password = passEl.value;
  if (!email) {
    showFieldError(loginErr, emailEl, "Enter your email address.");
    return;
  }
  if (!password) {
    showFieldError(loginErr, passEl, "Please enter your password.");
    return;
  }
  trackAppEvent("auth_email_login_started");
  setButtonPending(loginBtn, true, "Logging in…");
  try {
    const { user } = await signInWithEmailAndPassword(auth, email, password);
    forgetRememberedEmail();
    if (!user.emailVerified) {
      // Unbestaetigt heisst nicht mehr "raus": das Modal geht zu, die App
      // ist da, und der Streifen (onIdTokenChanged) erklaert den einen
      // fehlenden Schritt inklusive Resend.
      try { localStorage.removeItem("id_token"); } catch (_) {}
      setButtonPending(loginBtn, false);
      closeAuthModal();
      trackAppEvent("auth_email_login_result", { status: "unverified" });
      return;
    }
    const token = await user.getIdToken();
    try { localStorage.setItem("id_token", token); } catch (_) {}
    trackAppEvent("auth_email_login_result", { status: "success" });
    trackAppEvent("login", { method: "email" });
    continueSignedIn();
  } catch (error) {
    setButtonPending(loginBtn, false);
    loginErr.textContent = mapFirebaseLoginError(error);
    if (loginErr.textContent === WRONG_CREDENTIALS_MESSAGE) passEl.setAttribute("aria-invalid", "true");
    trackAppEvent("auth_email_login_result", { status: "error" });
  }
}

// --- Continue with Google -------------------------------------------------

function syncInAppBrowserNotice(emphasize = false) {
  const name = inAppBrowserName();
  inAppNoticeEl.hidden = !name;
  if (!name) return false;
  inAppNameEl.textContent = name === "app" ? "this app" : `the ${name} app`;
  const android = /Android/i.test(navigator.userAgent || "");
  inAppOpenEl.hidden = !android;
  if (android) {
    inAppOpenEl.href = `intent://${window.location.host}${window.location.pathname}${window.location.search}`
      + "#Intent;scheme=https;package=com.android.chrome;end";
  }
  inAppHintEl.textContent = android
    ? "Open consens.io in Chrome, or use your email below."
    : "Use the app’s ••• menu and choose “Open in browser”, or use your email below.";
  inAppNoticeEl.classList.toggle("is-emphasized", emphasize);
  return true;
}

inAppCopyEl.addEventListener("click", () => {
  const link = `${window.location.origin}${window.location.pathname}`;
  const done = label => {
    inAppCopyEl.textContent = label;
    window.setTimeout(() => { inAppCopyEl.textContent = "Copy link"; }, 2400);
  };
  trackAppEvent("auth_in_app_copy_link");
  if (!navigator.clipboard?.writeText) {
    done(link);
    return;
  }
  navigator.clipboard.writeText(link).then(() => done("Link copied"), () => done(link));
});

function startGoogleRedirect() {
  try { sessionStorage.setItem(GOOGLE_REDIRECT_KEY, "1"); } catch (_) {}
  setGooglePending(true, "Opening Google…");
  signInWithRedirect(auth, googleProvider).catch(error => {
    try { sessionStorage.removeItem(GOOGLE_REDIRECT_KEY); } catch (_) {}
    setGooglePending(false);
    googleErr.textContent = mapGoogleSignInError(error);
    trackAppEvent("auth_google_login_result", { status: "error", flow: "redirect", code: error?.code || "unknown" });
  });
}

function handleGoogleSignIn() {
  if (googleBtn.disabled) return;
  clearAuthMessages();
  const inApp = inAppBrowserName();
  if (inApp) {
    syncInAppBrowserNotice(true);
    trackAppEvent("auth_google_login_blocked", { browser: inApp });
    return;
  }
  if (prefersGoogleRedirect()) {
    trackAppEvent("auth_google_login_started", { flow: "redirect" });
    startGoogleRedirect();
    return;
  }
  trackAppEvent("auth_google_login_started", { flow: "popup" });
  setGooglePending(true);
  // signInWithPopup runs synchronously inside the click: one await before it
  // and Safari no longer counts the click and blocks the window.
  signInWithPopup(auth, googleProvider)
    .then(result => {
      trackAppEvent("auth_google_login_result", { status: "success", flow: "popup" });
      trackGoogleSignIn(result);
      setGooglePending(true, "Signing you in…");
      continueSignedIn();
    })
    .catch(error => {
      if (error?.code === "auth/popup-blocked" && authDomainIsFirstParty()) {
        trackAppEvent("auth_google_login_result", { status: "popup_blocked_redirect", flow: "popup" });
        startGoogleRedirect();
        return;
      }
      console.warn("Google sign-in failed:", error?.code || error);
      setGooglePending(false);
      googleErr.textContent = mapGoogleSignInError(error);
      trackAppEvent("auth_google_login_result", { status: "error", flow: "popup", code: error?.code || "unknown" });
    });
}

googleBtn.addEventListener("click", handleGoogleSignIn);

// --- Opening and closing ----------------------------------------------------

// The dialog is a native <dialog> opened through App.modalDialog
// (modal-dialog.js): the page behind is inert, Tab stays inside, Escape and
// the close button close it, focus goes back to whoever opened it, and it
// fades in and out like every other dialog (overlays.css). The backdrop
// closes it only for a deliberate click there, and never once something is
// typed (a dragged text selection ends its click on the backdrop).
function authDialog() {
  return document.getElementById("loginModal");
}

function authDialogHasTyping() {
  const modal = authDialog();
  return Boolean(modal && Array.from(modal.querySelectorAll("input"))
    .some(input => !["checkbox", "radio", "hidden"].includes(input.type) && input.value.trim()));
}

function bindAuthDialog(modal) {
  window.App.modalDialog?.bind(modal, {
    keepOpen: authDialogHasTyping,
    onClose: () => {
      authContextLead = "";
      hidePassword();
    },
  });
}

function showAuthModal(mode, trigger) {
  const modal = authDialog();
  if (!modal) return;
  if (mode) setMode(mode);
  syncInAppBrowserNotice();
  // On a phone a focused field opens the keyboard, which covers the Google
  // button before the user has chosen a way in.
  const initialFocus = (isCoarsePointer()
    ? document.getElementById("loginModalContent")
    : emailEl) || document.getElementById("closeLoginModal");
  bindAuthDialog(modal);
  if (modal.open) {
    initialFocus?.focus({ preventScroll: true });
    return;
  }
  if (window.App.modalDialog) {
    window.App.modalDialog.open(modal, { opener: trigger || null, focus: initialFocus });
  } else {
    modal.setAttribute("open", "");
    initialFocus?.focus({ preventScroll: true });
  }
}

function closeAuthModal() {
  const modal = authDialog();
  if (!modal?.open) return;
  if (window.App.modalDialog) window.App.modalDialog.close(modal);
  else {
    modal.removeAttribute("open");
    authContextLead = "";
    hidePassword();
  }
}

// Klick auf den Login-Bereich: Öffne das Modal, wenn nicht angemeldet.
// Eingeloggt passiert hier bewusst NICHTS - das User-Icon öffnet sein eigenes
// Popup (stopPropagation), Logout läuft ausschließlich über den bestätigten
// Logout-Button im Popup. Vorher loggte ein Klick knapp neben das Icon aus.
document.getElementById("loginContainer").addEventListener("click", event => {
  if (!auth.currentUser) {
    showAuthModal("login", event.currentTarget);
    trackAppEvent("auth_modal_open");
  }
});

// Auth-Buttons oben rechts (nur ausgeloggt sichtbar): öffnen das Modal direkt
// im passenden Modus — "Sign up" landet ohne Umweg im Registrierungsformular.
function openAuthModal(mode, trigger, source, { lead = "" } = {}) {
  if (auth.currentUser) return;
  authContextLead = lead;
  showAuthModal(mode, trigger);
  trackAppEvent("auth_modal_open", source ? { mode, source } : { mode });
}

// Demo end, the locked attachment menu and a guest's Send
// (composer-invite.js) open the same dialog.
window.App.openAuthModal = openAuthModal;

document.getElementById("authTopLoginBtn")?.addEventListener("click", event => openAuthModal("login", event.currentTarget));
document.getElementById("authTopSignupBtn")?.addEventListener("click", event => openAuthModal("register", event.currentTarget));

// Schließen des Modals
document.getElementById("closeLoginModal").addEventListener("click", closeAuthModal);
// Standard: beim Öffnen im Login-Modus
setMode("login");

// --- Coming back ---------------------------------------------------------

// Back from Google's redirect: the dialog shows that sign-in is finishing,
// onIdTokenChanged takes over, and a failure lands next to the Google button.
(function resumeGoogleRedirect() {
  let pending = false;
  try {
    pending = sessionStorage.getItem(GOOGLE_REDIRECT_KEY) === "1";
    sessionStorage.removeItem(GOOGLE_REDIRECT_KEY);
  } catch (_) {}
  if (!pending) return;
  showAuthModal("login");
  setGooglePending(true, "Signing you in…");
  getRedirectResult(auth)
    .then(result => {
      setGooglePending(false);
      if (!result?.user) return; // came back without choosing an account
      trackAppEvent("auth_google_login_result", { status: "success", flow: "redirect" });
      trackGoogleSignIn(result);
      closeAuthModal();
    })
    .catch(error => {
      setGooglePending(false);
      googleErr.textContent = mapGoogleSignInError(error);
      trackAppEvent("auth_google_login_result", { status: "error", flow: "redirect", code: error?.code || "unknown" });
    });
})();

// A private Watch page opens only with its owner's session cookie, which a
// mail app or another browser lacks. Its links and its "Sign in to view"
// button come here as /app?next=/s/...; once signed in (or at once, when this
// browser is signed in already) the auth handler above goes back. Only
// same-origin page paths are accepted, never a full URL or "//host".
const SIGNED_IN_RETURN = (() => {
  const next = new URL(window.location.href).searchParams.get("next") || "";
  return /^\/s\/[A-Za-z0-9_-]{1,240}$/.test(next) ? next : "";
})();
(function askToSignInForPrivatePage() {
  if (!SIGNED_IN_RETURN) return;
  let handled = false;
  onAuthStateChanged(auth, user => {
    if (handled) return;
    handled = true;
    if (user) return;
    showAuthModal("login");
    loginNoticeEl.textContent = "Log in to open your private watch page.";
  });
})();

// Back from the password-setup e-mail (continueUrl /app?setup=1, see
// app/services/registration.py): open the login with the address filled in.
(function resumePasswordSetup() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("setup")) return;
  url.searchParams.delete("setup");
  window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  let handled = false;
  onAuthStateChanged(auth, user => {
    if (handled) return;
    handled = true;
    if (user) return;
    showAuthModal("login");
    const email = rememberedEmail();
    if (email && !emailEl.value) emailEl.value = email;
    loginNoticeEl.textContent = "Your password is set. Log in to start.";
    if (email && !isCoarsePointer()) passEl.focus({ preventScroll: true });
    trackAppEvent("auth_setup_return");
  });
})();

// --- Account löschen (DSGVO Art. 17) ---
// The app asks once, in its own dialog (App.confirm), and says how it went
// in the notice line (App.toast); the browser's grey windows are gone
// (Apple audit E1). After a deletion the line is read before the page
// leaves for the start page.
const ACCOUNT_DELETED_READ_MS = 2400;
document.getElementById("deleteAccountBtn")?.addEventListener("click", async event => {
  const button = event.currentTarget;
  if (!auth.currentUser) {
    window.App.toast({ message: "Log in first.", tone: "error" });
    return;
  }
  const confirmed = await window.App.confirm({
    title: "Delete your account permanently?",
    body: "This removes your account, your chats and all data stored about you. This can’t be undone.",
    confirmLabel: "Delete account",
    danger: true,
  });
  if (!confirmed || !auth.currentUser) return;

  const failed = error => {
    trackAppEvent("auth_account_deletion_result", { status: "error" });
    window.App.toast({ message: window.App.userError(error, { fallback: "Your account couldn’t be deleted. Try again or write to contact@consens.io." }), tone: "error" });
  };
  const leave = () => window.setTimeout(() => { window.location.href = "/?landing=1"; }, ACCOUNT_DELETED_READ_MS);
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Deleting…";
  trackAppEvent("auth_account_deletion_started");
  try {
    const token = await auth.currentUser.getIdToken(true);
    const res = await fetch("/delete_account", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: token })
    });
    const data = await window.App.readJson(res).catch(() => ({}));
    if (res.status === 202 && data.cleanup_pending === true) {
      trackAppEvent("auth_account_deletion_result", { status: "cleanup_pending" });
      try { localStorage.removeItem("id_token"); } catch {}
      window.App.userSettings.stop();
      window.App.toast({ message: data.message || "Your account is blocked. Remaining data cleanup is queued and will be retried automatically.", duration: Infinity });
      await signOut(auth).catch(() => {});
      leave();
    } else if (res.ok && data.status === "deleted" && data.cleanup_pending !== true) {
      trackAppEvent("auth_account_deletion_result", { status: "success" });
      try { localStorage.removeItem("id_token"); } catch {}
      window.App.userSettings.stop();
      window.App.toast({ message: "Your account and data have been deleted.", tone: "success", duration: Infinity });
      // Der Auth-Account existiert nicht mehr; lokale Session beenden und zur Startseite
      signOut(auth).catch(() => {});
      leave();
    } else {
      failed(window.App.httpError(res, data));
    }
  } catch (err) {
    console.error("Account deletion failed:", err);
    failed(err);
  } finally {
    if (button.isConnected) {
      button.disabled = false;
      button.textContent = label;
    }
  }
});

async function recordModelVote(model, type, resultId = window.lastShareResultId) {
  // Prüfe, ob der Nutzer eingeloggt ist.
  if (!auth.currentUser) {
    return;
  }
  
  try {
    const requestUser = auth.currentUser;
    const generation = authState.generation;
    const id_token = await requestUser.getIdToken(/* forceRefresh= */ false);
    if (!isCurrentAuthenticatedUser(requestUser.uid, generation)) return;
    if (!id_token || !resultId) {
      console.error("No id_token available for voting.");
      return;
    }

    const response = await fetch("/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_token: id_token,
        model: model,
        vote_type: type,
        result_id: resultId
      })
    });
    const data = await response.json();
    if (!response.ok) {
      console.error("Error recording vote:", data.detail);
    }
  } catch (error) {
    console.error("Error connecting to backend for vote recording:", error);
  }
}

window.recordModelVote = recordModelVote;

// The sidebar shows the whole name; the row's CSS ellipsis cuts it where the
// space ends. The former five-word cut ("Our house is from 1978...")
// shortened even names that fitted.
function bookmarkLabelText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function bookmarkDisplayQuestion(bookmark) {
  return String(bookmark?.query || "").trim();
}

// Der Sidebar-Name ist die ERSTE Frage der Unterhaltung und bleibt danach
// stehen; `query` ist die zuletzt gestellte Frage und wandert mit jedem
// Follow-up weiter. Aeltere Bookmarks ohne gespeicherten Titel fallen auf
// die Frage zurueck.
function bookmarkDisplayTitle(bookmark) {
  return String(bookmark?.title || "").trim() || bookmarkDisplayQuestion(bookmark);
}

function bookmarkIdForQuestion(question) {
  const bytes = new TextEncoder().encode(String(question || ""));
  let binary = "";
  bytes.forEach(byte => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/[^a-zA-Z0-9]/g, "_").slice(0, 50);
}

window.App = window.App || {};
window.App.bookmarkSession = {
  activeId: null,
  pending: null,

  begin(question, { followup = false } = {}) {
    if (!followup || !this.activeId) {
      this.activeId = bookmarkIdForQuestion(question) || null;
    }
    return this.activeId;
  },

  restore(bookmarkId) {
    const value = String(bookmarkId || "").trim();
    this.activeId = /^[A-Za-z0-9_]{1,100}$/.test(value) ? value : null;
    return this.activeId;
  },

  currentId() {
    return this.activeId;
  },

  // A run gets a local sidebar row immediately. It deliberately stays out of
  // bookmarksData until the server returns real metadata: the outline is a
  // promise that a bookmark is being created, not a usable saved result.
  setRunActive(isActive, question = "") {
    if (isActive) {
      if (!auth.currentUser) return;
      if (!this.activeId) this.begin(question);
      const bookmarkId = this.activeId;
      if (!bookmarkId) return;

      if (!this.pending || this.pending.id !== bookmarkId) {
        const initialMeta = window.bookmarksData?.find(item => item.id === bookmarkId) || null;
        if (this.pending?.finishTimer) clearTimeout(this.pending.finishTimer);
        this.pending = {
          id: bookmarkId,
          question: bookmarkDisplayTitle(initialMeta) || String(question || "").trim(),
          initialMeta,
          latestMeta: null,
          runActive: true,
          writes: 0,
          finishTimer: null
        };
      } else {
        this.pending.runActive = true;
        if (this.pending.finishTimer) clearTimeout(this.pending.finishTimer);
        this.pending.finishTimer = null;
      }
      ensurePendingBookmarkDOM(this.pending);
      return;
    }

    if (!this.pending) return;
    this.pending.runActive = false;
    this.schedulePendingFinish();
  },

  noteWriteStarted(bookmarkId) {
    if (this.pending?.id !== bookmarkId) return;
    this.pending.writes += 1;
    if (this.pending.finishTimer) clearTimeout(this.pending.finishTimer);
    this.pending.finishTimer = null;
  },

  noteWriteFinished(bookmarkId) {
    if (this.pending?.id !== bookmarkId) return;
    this.pending.writes = Math.max(0, this.pending.writes - 1);
    this.schedulePendingFinish();
  },

  noteSavedMeta(meta) {
    if (!meta?.id || this.pending?.id !== meta.id) return false;
    this.pending.latestMeta = meta;
    this.pending.question = bookmarkDisplayTitle(meta) || this.pending.question;
    ensurePendingBookmarkDOM(this.pending);
    return true;
  },

  // Model fan-out hands directly into auto-consensus. The zero-delay fence
  // lets that synchronous hand-off claim the same pending row before it can
  // briefly turn into a clickable bookmark between the two phases.
  schedulePendingFinish() {
    if (!this.pending || this.pending.runActive || this.pending.writes > 0) return;
    if (this.pending.finishTimer) clearTimeout(this.pending.finishTimer);
    const pendingId = this.pending.id;
    this.pending.finishTimer = setTimeout(() => {
      if (this.pending?.id === pendingId) this.finishPending();
    }, 0);
  },

  finishPending() {
    const pending = this.pending;
    if (!pending || pending.runActive || pending.writes > 0) return;
    if (pending.finishTimer) clearTimeout(pending.finishTimer);
    this.pending = null;
    const readyMeta = pending.latestMeta
      || window.bookmarksData?.find(item => item.id === pending.id)
      || pending.initialMeta;
    if (readyMeta) replacePendingBookmarkWithReady(readyMeta);
    else document.querySelector(`.bookmark.is-pending[data-id="${pending.id}"]`)?.remove();
  },

  reset() {
    const pending = this.pending;
    if (pending?.finishTimer) clearTimeout(pending.finishTimer);
    this.pending = null;
    if (pending?.initialMeta) replacePendingBookmarkWithReady(pending.initialMeta);
    else document.querySelector(`.bookmark.is-pending[data-id="${pending?.id || ""}"]`)?.remove();
    this.activeId = null;
  }
};

// Familien eines Bookmarks: dieselbe Quelle wie die App (window.App.modelPrefs,
// gespeist aus cfg.PROVIDERS). Bookmarks aelterer Laeufe kennen nur die
// Familien, die es damals gab -- fehlende Schluessel sind einfach leer.
function bookmarkModelKeys() {
  return (window.App?.modelPrefs || []).map(pref => pref.key);
}

function bookmarkModelAnswerCount(bookmark) {
  const responses = bookmark?.responses && typeof bookmark.responses === "object" ? bookmark.responses : {};
  return bookmarkModelKeys().filter(name => String(responses[name] || "").trim()).length;
}

// Ein Direktvergleich (Agent Mode aus) legt Modellantworten ab und nie einen
// Consensus — daran, nicht am heutigen Stand des Schalters, ist er beim Laden
// zu erkennen. Ohne diese Unterscheidung blieb ein solches Bookmark unter
// eingeschaltetem Agent Mode unsichtbar hinter "Compare answers" haengen und
// zeigte nur noch die Frage. Ein abgebrochener Consensus-Lauf faellt in
// dieselbe Kategorie: seine Antworten sind alles, was es zu zeigen gibt.
function isDirectComparisonBookmark(bookmark) {
  const consensus = String(bookmark?.responses?.consensus || "").trim();
  return !consensus && bookmarkModelAnswerCount(bookmark) > 0;
}

function bookmarkMeta(bookmark) {
  const responses = bookmark?.responses && typeof bookmark.responses === "object" ? bookmark.responses : {};
  // Older bookmarks may still carry a "source_verification" snapshot of the
  // removed contradiction source check; it is no model answer and stays unread.
  const modelCount = Object.entries(responses).filter(([key, value]) =>
    !["consensus", "differences", "differences_data", "source_verification"].includes(key) && String(value || "").trim()
  ).length;
  return {
    id: bookmark?.id || "",
    query: bookmarkDisplayQuestion(bookmark),
    title: bookmarkDisplayTitle(bookmark),
    // Generated, or given by the person (Rename): either one stays.
    title_source: ["generated", "user"].includes(bookmark?.title_source) ? bookmark.title_source : "",
    mode: bookmark?.mode || "",
    timestamp: bookmark?.timestamp || null,
    has_consensus: bookmark?.responses && typeof bookmark.responses === "object"
      ? Boolean(String(responses.consensus || "").trim())
      : bookmark?.has_consensus === true,
    model_count: Number(bookmark?.model_count ?? modelCount) || 0,
    source_count: Number(bookmark?.source_count ?? bookmark?.sources?.length) || 0,
    attachment_count: Number(bookmark?.attachment_count ?? bookmark?.attachments?.length) || 0,
  };
}

function upsertBookmarkMeta(bookmark, {
  prepend = true,
  runId = null,
  writeType = "model",
  requestUid = auth.currentUser?.uid || null,
  nameIt = true
} = {}) {
  const meta = bookmarkMeta(bookmark);
  if (!meta.id) return;
  if (!bookmarkWriteAllowed(requestUid, meta.id)) return;
  // Keep the local row disabled while the surrounding run (and its queued
  // persistence writes) is still in flight.
  if (runId && window.App.runRegistry?.get?.(runId)) {
    window.App.runRegistry.update(runId, context => {
      context.bookmark.latestMeta = meta;
      context.bookmark.id = meta.id;
      context.bookmark.title = bookmarkDisplayTitle(meta) || context.bookmark.title;
      if (writeType === "consensus") context.persistence.consensusWrite = true;
    }, { render: false, eventType: "persistence" });
  } else {
    window.App.bookmarkSession?.noteSavedMeta?.(meta);
  }
  if (!window.bookmarksData) window.bookmarksData = [];
  const existingIndex = window.bookmarksData.findIndex(item => item.id === meta.id);
  // A saved write changed the chat: its remembered view is out of date.
  if (nameIt) bookmarkViewCache.delete(meta.id);
  if (existingIndex >= 0) {
    window.bookmarksData[existingIndex] = meta;
    updateBookmarkDOM(meta);
  } else {
    if (prepend) window.bookmarksData.unshift(meta);
    else window.bookmarksData.push(meta);
    addBookmarkToDOM(meta, { prepend });
  }
  if (runId) window.App.bookmarkUi?.finalizeRun?.(window.App.runRegistry?.get?.(runId));
  // A save confirmed by the server names its conversation once; the list
  // load never does (older chats keep their question as the name).
  if (nameIt && !KEPT_TITLE_SOURCES.has(meta.title_source)) requestBookmarkTitle(meta.id, requestUid);
  // A saved chat may change what the next new chat suggests.
  if (nameIt) window.App.composerStarters?.refresh?.();
}

// Asks the server for a short topic title (chat_titles.py) and swaps it in
// when it arrives. One request per bookmark and session; a failure leaves
// the question as the name.
const bookmarkTitleRequests = new Set();
async function requestBookmarkTitle(bookmarkId, requestUid) {
  const user = auth.currentUser;
  const key = `${requestUid}:${bookmarkId}`;
  if (!bookmarkId || !user || user.uid !== requestUid || bookmarkTitleRequests.has(key)) return;
  bookmarkTitleRequests.add(key);
  const generation = authState.generation;
  try {
    const idToken = await user.getIdToken(false);
    if (!isCurrentAuthenticatedUser(requestUid, generation)) return;
    const response = await fetch("/bookmarks/" + encodeURIComponent(bookmarkId) + "/title", {
      method: "POST",
      headers: { "Authorization": "Bearer " + idToken }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !isCurrentAuthenticatedUser(requestUid, generation)) return;
    if (data.bookmark?.title_source === "generated") applyBookmarkTitle(data.bookmark);
  } catch (error) {
    console.warn("Bookmark title unavailable:", error);
  }
}

// A name that outlives later saves: generated, or given by the person
// (Rename in the row menu).
const KEPT_TITLE_SOURCES = new Set(["generated", "user"]);

function applyBookmarkTitle(named, source = "generated") {
  if (!bookmarkWriteAllowed(auth.currentUser?.uid || null, named.id)) return;
  const title = bookmarkDisplayTitle(named);
  const entry = (window.bookmarksData || []).find(item => item.id === named.id);
  if (entry) Object.assign(entry, { title, title_source: source });
  // Every run of the chat, a running follow-up too, and the open chat's
  // basis: a follow-up sent next takes its name from there and showed the
  // old one in the sidebar while it ran (review F, review 2).
  window.App.runRegistry?.retitle?.(named.id, title, { source });
  window.App.bookmarkSession?.noteSavedMeta?.({ ...(entry || bookmarkMeta(named)), title, title_source: source });
  // The name settles in place of the question instead of switching.
  for (const label of document.querySelectorAll(`.bookmark[data-id="${named.id}"] > p`)) {
    if (label.textContent === bookmarkLabelText(title)) continue;
    label.textContent = bookmarkLabelText(title);
    if (source === "generated" && label.animate && !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      label.animate([{ opacity: 0 }, { opacity: 1 }], { duration: window.App?.motion?.ms?.("state") ?? 200, easing: window.App?.motion?.ease?.("out") ?? "ease-out" });
    }
  }
  document.querySelectorAll(`.bookmark[data-id="${named.id}"] .bookmark-menu-button`)
    .forEach(control => labelBookmarkMenu(control, bookmarkLabelText(title)));
  window.filterBookmarks?.(document.getElementById("chatSearch")?.value || "");
}

let lastBookmarkSaveNotice = { key: "", shownAt: 0 };
const bookmarkWriteChains = new Map();
const deletedBookmarkKeys = new Set();
const deletingBookmarks = new Map();

function bookmarkMutationKey(uid, bookmarkId) {
  return `${String(uid || "")}:${String(bookmarkId || "")}`;
}

function bookmarkWriteAllowed(uid, bookmarkId) {
  return !deletedBookmarkKeys.has(bookmarkMutationKey(uid, bookmarkId));
}

function snapshotBookmarkValue(value) {
  if (value === undefined) return undefined;
  try { return structuredClone(value); } catch (_) {}
  try { return JSON.parse(JSON.stringify(value)); } catch (_) { return null; }
}

function enqueueBookmarkWrite(
  requestUid,
  requestGeneration,
  bookmarkId,
  operation,
  runId = null,
  { allowStaleAuth = false } = {}
) {
  if (runId && window.App.runRegistry?.get?.(runId)) {
    window.App.runRegistry.update(runId, context => {
      context.persistence.pendingWrites += 1;
      context.bookmark.writes += 1;
    }, { render: false, eventType: "persistence" });
  } else {
    window.App.bookmarkSession?.noteWriteStarted?.(bookmarkId);
  }
  // Generation fences decide whether an operation may start or update UI, but
  // the server resource is owned by uid+bookmarkId across login generations.
  // A rapid logout/re-login of the same account must still drain an older
  // in-flight fetch before a new write/delete to that document begins.
  const queueKey = `${requestUid}:${bookmarkId}`;
  const previous = bookmarkWriteChains.get(queueKey) || Promise.resolve();
  const current = previous
    // A failed model snapshot must not prevent the authoritative consensus
    // snapshot behind it from repairing/completing the same bookmark.
    .catch(() => undefined)
    .then(() => {
      if (!allowStaleAuth && !isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;
      return operation();
    });
  bookmarkWriteChains.set(queueKey, current);
  return current.finally(() => {
    if (bookmarkWriteChains.get(queueKey) === current) {
      bookmarkWriteChains.delete(queueKey);
    }
    if (runId && window.App.runRegistry?.get?.(runId)) {
      window.App.runRegistry.update(runId, context => {
        context.persistence.pendingWrites = Math.max(0, context.persistence.pendingWrites - 1);
        context.bookmark.writes = Math.max(0, context.bookmark.writes - 1);
      }, { render: false, eventType: "persistence" });
      window.App.bookmarkUi?.finalizeRun?.(window.App.runRegistry.get(runId));
    } else {
      window.App.bookmarkSession?.noteWriteFinished?.(bookmarkId);
    }
  });
}

function showBookmarkSaveError(status, detail, scope = "") {
  const normalizedDetail = String(detail || "").trim();
  let message = "This chat couldn’t be saved.";
  if (normalizedDetail === "Bookmark limit reached.") {
    message = "Your saved chats are full. Delete an old chat to save new ones.";
  } else if (normalizedDetail === "Bookmark storage limit reached.") {
    message = "Your chat storage is full. Delete old chats to save new ones.";
  } else if (normalizedDetail === "Bookmark is too large.") {
    message = "This answer is too large to keep in your chats.";
  } else if (status === 429) {
    message = "Chats can’t be saved right now. Wait a minute and try again.";
  }

  // Ein Lauf speichert bis zu sechs Modellantworten parallel. Derselbe Fehler
  // darf deshalb genau einmal sichtbar werden, nicht als Popup-Kaskade.
  const key = `${scope}:${status}:${message}`;
  const now = Date.now();
  if (lastBookmarkSaveNotice.key === key && now - lastBookmarkSaveNotice.shownAt < 600_000) {
    return;
  }
  lastBookmarkSaveNotice = { key, shownAt: now };
  window.App?.showPopup?.(message);
}

async function saveBookmark(question, response, modelName, mode, previousQuestion = "", runOptions = null) {
  const modelLabel = String(runOptions?.modelLabel || "").trim() || null;
  const boundRunId = String(runOptions?.runId || "").trim() || null;
  const requestUser = runOptions?.auth?.user || auth.currentUser;
  if (!requestUser) return;
  const requestUid = runOptions?.auth?.uid || requestUser.uid;
  const requestGeneration = runOptions?.auth?.generation ?? authState.generation;
  const bookmarkId = runOptions?.bookmarkId
    || window.App.bookmarkSession?.currentId?.()
    || bookmarkIdForQuestion(question);
  const waitForDeleteOutcome = !bookmarkWriteAllowed(requestUid, bookmarkId);
  // Snapshot before entering the queue. A later bookmark/view switch cannot
  // change the payload of this run while it waits behind an earlier write.
  const sources = Array.isArray(runOptions?.sources)
    ? runOptions.sources.map(source => ({ ...source }))
    : (window.currentEvidenceSources || []).map(source => ({ ...source }));
  const attachmentsMeta = Array.isArray(runOptions?.attachments)
    ? runOptions.attachments.map(item => ({ ...item }))
    : (window.lastQuestionAttachmentsMeta || []).map(item => ({ ...item }));
  return enqueueBookmarkWrite(requestUid, requestGeneration, bookmarkId, async () => {
    if (waitForDeleteOutcome && !bookmarkWriteAllowed(requestUid, bookmarkId)) return;
    const id_token = await requestUser.getIdToken(false);
    if (!id_token || !isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;

    try {
      const res = await fetch("/bookmark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // HIER: sources hinzufügen
        body: JSON.stringify({
          id_token,
          question,
          response,
          modelName,
          modelLabel,
          mode,
          bookmarkId: bookmarkId || null,
          previousQuestion,
          sources: sources,
          attachments: attachmentsMeta
        })
      });
      if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;
      const data = await res.json();
      if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;

      if (!res.ok) {
        // The server's sentence (`error`, flat since Apple-Audit H6) names
        // the limit; `detail` was never sent, so the specific line never came.
        const errorDetail = window.App?.errorFields?.(data)?.error || data.detail || "";
        console.error("Error saving bookmark:", errorDetail);
        if (boundRunId) {
          window.App.runRegistry?.notePersistence?.(boundRunId, {
            status: "error",
            error: { type: "model", status: res.status, detail: errorDetail || "Chat save failed" }
          });
        }
        if (!boundRunId || window.App.runRegistry?.isVisible?.(boundRunId)) {
          showBookmarkSaveError(res.status, errorDetail, `${bookmarkId}:${question}`);
        }
        return;
      }

      if (data.bookmark) {
          if (!boundRunId) window.App.bookmarkSession?.restore?.(data.bookmark.id);
          upsertBookmarkMeta(data.bookmark, {
            runId: boundRunId,
            writeType: "model",
            requestUid
          });
          if (openedBookmarkId === data.bookmark.id) {
            bookmarkDetailCache.clear();
            bookmarkDetailCache.set(data.bookmark.id, data.bookmark);
          }
      }

    } catch (error) {
      console.error("Error in saveBookmark:", error);
      if (boundRunId) {
        window.App.runRegistry?.notePersistence?.(boundRunId, {
          status: "error",
          error: { type: "model", detail: error?.message || "Chat save failed" }
        });
      }
    }
  }, boundRunId);
}

window.saveBookmark = saveBookmark;

async function saveBookmarkConsensus(question, consensusText, differencesText, differencesData,
                                     resultId, consensusModel, modelLabels,
                                     previousQuestion = "", previousTurn = null,
                                     conversation = null) {
  const requestUser = auth.currentUser;
  const boundRunId = String(conversation?.runId || "").trim() || null;
  const boundAuth = conversation?.auth || null;
  const boundRequestUser = boundAuth?.user || requestUser;
  if (!boundRequestUser) return;
  const requestUid = boundAuth?.uid || boundRequestUser.uid;
  const requestGeneration = boundAuth?.generation ?? authState.generation;
  const bookmarkId = conversation?.bookmarkId
    || window.App.bookmarkSession?.currentId?.()
    || bookmarkIdForQuestion(question);
  const waitForDeleteOutcome = !bookmarkWriteAllowed(requestUid, bookmarkId);
  // Only identifiers and the small legacy-required text copies travel over
  // this compatibility path. Sources, structured differences, labels and
  // provider answers are materialized from the owner-bound completed run.
  // Sending those ignored copies used to reject valid runs at source 25 even
  // though the authoritative snapshot supports 50.
  const payloadSnapshot = {
    question: String(question || ""),
    consensusText: String(consensusText || ""),
    differencesText: String(differencesText || ""),
    resultId: resultId || null,
    chatId: conversation?.chatId || null,
    turnId: conversation?.turnId || null,
    previousQuestion: String(previousQuestion || ""),
    previousTurn: snapshotBookmarkValue(previousTurn) || null
  };
  return enqueueBookmarkWrite(requestUid, requestGeneration, bookmarkId, async () => {
    if (waitForDeleteOutcome && !bookmarkWriteAllowed(requestUid, bookmarkId)) return;
    const id_token = await boundRequestUser.getIdToken(/* forceRefresh= */ false);
    if (!id_token || !isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;

    try {
      const requestBody = JSON.stringify({
        id_token: id_token,
        question: payloadSnapshot.question,
        consensusText: payloadSnapshot.consensusText,
        differencesText: payloadSnapshot.differencesText,
        resultId: payloadSnapshot.resultId,
        bookmarkId: bookmarkId || null,
        chatId: payloadSnapshot.chatId,
        turnId: payloadSnapshot.turnId,
        previousQuestion: payloadSnapshot.previousQuestion,
        previousTurn: payloadSnapshot.previousTurn
      });
      let res = null;
      let data = null;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          res = await fetch("/bookmark/consensus", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: requestBody,
            keepalive: true
          });
          data = await res.json().catch(() => ({}));
        } catch (networkError) {
          if (attempt >= 2) throw networkError;
          await new Promise(resolve => setTimeout(resolve, 250 * (4 ** attempt)));
          if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;
          continue;
        }
        const retryable = res.status === 408 || res.status === 425
          || res.status === 429 || res.status >= 500;
        if (res.ok || !retryable || attempt >= 2) break;
        const retryDelay = res.status === 429
          ? 1000 * (attempt + 1)
          : 250 * (4 ** attempt);
        await new Promise(resolve => setTimeout(resolve, retryDelay));
        if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;
      }
      if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;
      if (!res.ok) {
        const errorDetail = window.App?.errorFields?.(data)?.error || data.detail || "Chat answer save failed";
        data.detail = errorDetail;
        console.error("Error saving consensus bookmark:", errorDetail, data.details || "");
        if (boundRunId) {
          window.App.runRegistry?.notePersistence?.(boundRunId, {
            status: "error",
            error: { type: "consensus", status: res.status, detail: errorDetail }
          });
        }
        if (!boundRunId || window.App.runRegistry?.isVisible?.(boundRunId)) {
          showBookmarkSaveError(res.status, data.detail, `${bookmarkId}:${question}`);
        }
        return;
      }
      if (data.bookmark) {
        if (boundRunId && window.App.runRegistry?.get?.(boundRunId)) {
          const persistedBookmark = snapshotBookmarkValue(data.bookmark);
          window.App.runRegistry.update(boundRunId, context => {
            context.persistence.consensusBookmark = persistedBookmark;
            context.persistence.consensusVersionParts = bookmarkShareVersionParts(data.bookmark);
          }, { render: false, eventType: "persistence" });
        }
        if (!boundRunId) window.App.bookmarkSession?.restore?.(data.bookmark.id);
        upsertBookmarkMeta(data.bookmark, {
          runId: boundRunId,
          writeType: "consensus",
          requestUid
        });
        if (openedBookmarkId === data.bookmark.id) {
          bookmarkDetailCache.clear();
          bookmarkDetailCache.set(data.bookmark.id, data.bookmark);
        }
      }
    } catch (error) {
      console.error("Error in saveBookmarkConsensus:", error);
      if (boundRunId) {
        window.App.runRegistry?.notePersistence?.(boundRunId, {
          status: "error",
          error: { type: "consensus", detail: error?.message || "Chat answer save failed" }
        });
      }
    }
  }, boundRunId);
}
window.saveBookmarkConsensus = saveBookmarkConsensus;

window.acceptPersistedConsensusBookmark = function (bookmarkMeta, conversation = null) {
  const runId = String(conversation?.runId || "").trim() || null;
  const requestUid = conversation?.auth?.uid || auth.currentUser?.uid || null;
  if (!bookmarkMeta?.id || !requestUid) return false;
  upsertBookmarkMeta(bookmarkMeta, {
    runId,
    writeType: "consensus",
    requestUid
  });
  if (!runId) window.App.bookmarkSession?.restore?.(bookmarkMeta.id);
  return true;
};

let bookmarkShareResultVersion = 0;
window.currentBookmarkShareResultPromise = null;
window.currentBookmarkShareResultContext = null;
// Why the last preparation of the chat on screen failed, in the server's
// words where it gave any: Share and Watch say it instead of a dead button.
window.currentBookmarkShareResultError = "";
const BOOKMARK_SHARE_RESULT_FAILED = "This chat couldn’t be prepared. Try again.";

window.clearPreparedBookmarkShareResult = function () {
  bookmarkShareResultVersion += 1;
  window.currentBookmarkShareResultPromise = null;
  window.currentBookmarkShareResultContext = null;
  window.currentBookmarkShareResultError = "";
  window.App.state.set("lastShareResultId", null, "share");
};

function prepareBookmarkShareResult(bookmark) {
  window.clearPreparedBookmarkShareResult();
  const bookmarkId = bookmark?.id;
  const consensusText = bookmark?.responses?.consensus;
  if (!auth.currentUser || !bookmarkId || !String(consensusText || "").trim()) {
    return null;
  }
  // An Agent chat shares the answer on screen by its turn (share-dialog.js):
  // a finished turn never changes, so no version needs binding.
  if (bookmark.mode === "Agent" || bookmark.execution_mode === "agent") {
    window.currentBookmarkShareResultContext = {
      bookmarkId,
      chatId: String(bookmark.chat_id || ""),
      turnId: String(bookmark.turn_id || "")
    };
    return window.currentBookmarkShareResultContext;
  }
  // Bind the exact snapshot on screen. The same bookmark document can advance
  // to a newer follow-up while this saved view remains visible; the server must
  // reject preparing that newer revision for an older view.
  window.currentBookmarkShareResultContext = {
    bookmarkId,
    versionParts: bookmarkShareVersionParts(bookmark)
  };
  return window.currentBookmarkShareResultContext;
}

function stableBookmarkJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableBookmarkJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map(key => (
      `${JSON.stringify(key)}:${stableBookmarkJson(value[key])}`
    )).join(",")}}`;
  }
  const json = JSON.stringify(value);
  return json === undefined ? "null" : json;
}

function bookmarkShareVersionParts(bookmark) {
  const responses = bookmark?.responses && typeof bookmark.responses === "object"
    ? bookmark.responses : {};
  return [
    String(bookmark?.query || ""),
    String(responses.consensus || ""),
    String(bookmark?.chat_id || ""),
    String(bookmark?.turn_id || ""),
    String(bookmark?.share_result_id || ""),
    stableBookmarkJson(responses.differences_data ?? null)
  ];
}

async function bookmarkShareVersion(parts) {
  if (!globalThis.crypto?.subtle || typeof TextEncoder !== "function") return "";
  const bytes = new TextEncoder().encode(JSON.stringify(Array.isArray(parts) ? parts : []));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

async function requestBookmarkShareResult() {
  const context = window.currentBookmarkShareResultContext;
  if (!context || !auth.currentUser) return null;
  const version = bookmarkShareResultVersion;
  const requestUser = auth.currentUser;
  const requestUid = requestUser.uid;
  const requestGeneration = authState.generation;
  const bookmarkId = context.bookmarkId;
  const agentTurn = Boolean(context.turnId);
  const expectedVersion = agentTurn ? "" : await bookmarkShareVersion(context.versionParts);
  if (version !== bookmarkShareResultVersion) return null;
  // Why it failed, in the server's words: the Share dialog says it.
  context.error = null;
  window.currentBookmarkShareResultError = "";
  const promise = enqueueBookmarkWrite(requestUid, requestGeneration, bookmarkId, async () => {
    try {
      if (version !== bookmarkShareResultVersion
          || !bookmarkWriteAllowed(requestUid, bookmarkId)) return null;
      const idToken = await requestUser.getIdToken(false);
      if (!idToken || !isCurrentAuthenticatedUser(requestUid, requestGeneration)) return null;
      const response = agentTurn
        ? await fetch(`/agent/chats/${encodeURIComponent(context.chatId)}/turns/${encodeURIComponent(context.turnId)}/share-result`, {
          method: "POST",
          headers: { Authorization: `Bearer ${idToken}` }
        })
        : await fetch("/bookmark/consensus/share-result", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: idToken, bookmarkId, expectedVersion })
        });
      const data = await window.App.readJson(response).catch(() => ({}));
      if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return null;
      if (!response.ok) throw window.App.httpError(response, data, "This chat couldn’t be prepared for sharing. Try again.");
      const resultId = String(data.result_id || "") || null;
      // An Agent answer is no Consensus result: votes and the Consensus
      // Watch keep reading lastShareResultId; the promise keeps the ID.
      if (version === bookmarkShareResultVersion && !agentTurn) {
        window.App.state.set("lastShareResultId", resultId, "share");
      }
      return version === bookmarkShareResultVersion ? resultId : null;
    } catch (error) {
      if (version === bookmarkShareResultVersion) {
        context.error = error;
        console.error("Error preparing bookmarked consensus for share/watch:", error);
        window.currentBookmarkShareResultError = window.App.userError(error, { fallback: BOOKMARK_SHARE_RESULT_FAILED });
      }
      return null;
    }
  });
  window.currentBookmarkShareResultPromise = promise;
  const resultId = await promise;
  if (!resultId && version === bookmarkShareResultVersion) {
    window.currentBookmarkShareResultPromise = null;
    window.currentBookmarkShareResultError ||= BOOKMARK_SHARE_RESULT_FAILED;
  }
  return resultId;
}

window.resolveCurrentShareResultId = async function () {
  if (window.lastShareResultId) return window.lastShareResultId;
  if (window.currentBookmarkShareResultPromise) {
    return await window.currentBookmarkShareResultPromise;
  }
  return await requestBookmarkShareResult();
};

function bookmarkModelPresentation() {
  return (window.App?.modelPrefs || []).map(pref => ({
    provider: pref.key,
    textId: pref.textId,
    citationLabel: pref.citationLabel || pref.key
  }));
}

function applyBookmarkModelPresentation(bookmark) {
  const responses = bookmark?.responses && typeof bookmark.responses === "object"
    ? bookmark.responses
    : {};
  const storedLabels = bookmark?.model_labels && typeof bookmark.model_labels === "object"
    ? bookmark.model_labels
    : {};
  const citationModels = [];

  bookmarkModelPresentation().forEach(({ provider, textId, citationLabel }) => {
    if (!String(responses[provider] || "").trim()) return;

    // model_labels is the immutable run provenance saved with the consensus.
    // Only change the response heading: selects/localStorage remain the source
    // of truth for the next run and must never be rewritten while browsing history.
    const storedLabel = typeof storedLabels[provider] === "string"
      ? storedLabels[provider].trim()
      : "";
    const visibleLabel = storedLabel || "Model not recorded";
    const labelEl = document.getElementById(textId);
    if (labelEl) {
      labelEl.textContent = visibleLabel;
      labelEl.title = storedLabel
        ? `Model used for this saved answer: ${storedLabel}`
        : "The exact model wasn’t recorded for this older chat.";
    }
    citationModels.push(storedLabel ? `${citationLabel}: ${storedLabel}` : citationLabel);
  });

  return citationModels;
}

// Diese Funktion füllt die UI mit den Daten eines Bookmarks
function normalizeConversationTurn(turn) {
  if (!turn || !turn.question) return null;
  if (!(turn.execution_mode === "agent" && turn.status === "failed")
      && !(turn.status === "completed" && turn.consensus)) return null;
  return { ...turn, consensus: turn.consensus || "", turn_id: turn.id || turn.turn_id || "" };
}

function bookmarkFallbackTurn(bookmark) {
  const question = bookmarkDisplayQuestion(bookmark);
  const responses = bookmark?.responses && typeof bookmark.responses === "object"
    ? bookmark.responses
    : {};
  const consensus = String(responses.consensus || "").trim();
  if (!question || !consensus) return null;

  const storedLabels = bookmark?.model_labels && typeof bookmark.model_labels === "object"
    ? bookmark.model_labels
    : {};
  const sources = Array.isArray(bookmark?.sources) ? bookmark.sources : [];
  const modelAnswers = {};
  bookmarkModelPresentation().forEach(({ provider }) => {
    const answer = String(responses[provider] || "").trim();
    if (!answer) return;
    modelAnswers[provider] = {
      provider,
      model_label: String(storedLabels[provider] || provider),
      answer,
      sources
    };
  });
  return {
    turn_id: String(bookmark?.turn_id || ""),
    status: "completed",
    question,
    attachments: Array.isArray(bookmark?.attachments) ? bookmark.attachments : [],
    mode: String(bookmark?.mode || ""),
    consensus_model: String(bookmark?.consensus_model || ""),
    consensus,
    differences: String(responses.differences || ""),
    differences_data: responses.differences_data || null,
    sources,
    model_answers: modelAnswers
  };
}

function materializeConversationBookmark(bookmark, conversationTurns) {
  const turns = (Array.isArray(conversationTurns) ? conversationTurns : [])
    .map(normalizeConversationTurn)
    .filter(Boolean)
    .sort((left, right) => Number(left.position || 0) - Number(right.position || 0));
  if (!turns.length) {
    return {
      bookmark,
      historyTurns: [],
      currentTurn: bookmarkFallbackTurn(bookmark)
    };
  }

  const currentTurn = turns[turns.length - 1];
  const responses = {
    consensus: currentTurn.consensus || "",
    differences: currentTurn.differences || "",
    differences_data: currentTurn.differences_data || null,
  };
  const modelLabels = {};
  Object.entries(currentTurn.model_answers || {}).forEach(([provider, item]) => {
    responses[provider] = typeof item === "string" ? item : String(item?.answer || "");
    const label = typeof item === "object" ? String(item?.model_label || "").trim() : "";
    if (label) modelLabels[provider] = label;
  });
  return {
    bookmark: {
      ...bookmark,
      query: currentTurn.question,
      mode: currentTurn.mode || bookmark.mode || "",
      // Die Anhaenge des Turns schlagen die des Dokuments: das Dokument kennt
      // nur die zuletzt gespeicherte Frage, der Turn kennt seine eigene. Ohne
      // diese Reihenfolge zeigte ein Chat, dessen letzte Frage ohne Datei
      // auskam, die Datei der vorigen Frage — oder gar keine. Chats von VOR
      // dieser Aenderung haben nichts am Turn stehen; fuer sie bleibt das
      // Dokument die einzige Quelle, und es beschreibt genau diese Frage.
      attachments: (Array.isArray(currentTurn.attachments) && currentTurn.attachments.length)
        ? currentTurn.attachments
        : (Array.isArray(bookmark.attachments) ? bookmark.attachments : []),
      responses,
      sources: Array.isArray(currentTurn.sources) ? currentTurn.sources : [],
      consensus_model: currentTurn.consensus_model || bookmark.consensus_model || "",
      model_labels: modelLabels,
      chat_id: bookmark.chat_id,
      turn_id: currentTurn.turn_id,
      previous_question: turns.length > 1 ? turns[turns.length - 2].question : "",
      previous_turn: turns.length > 1 ? turns[turns.length - 2] : null
    },
    historyTurns: turns.slice(0, -1),
    currentTurn
  };
}

// The transcript of a chat bookmark, by bookmark ID alone: it loads beside
// the bookmark detail instead of after it (Apple audit D2). The caller checks
// `chatId` against the detail's chat. A bookmark without a chat answers with
// no chat and no turns.
async function loadBookmarkConversationOnce(bookmarkId) {
  if (!auth.currentUser) return { chatId: "", turns: [] };
  const bookmark = { id: bookmarkId };
  let chatId = null;
  const requestUser = auth.currentUser;
  const requestUid = requestUser.uid;
  const requestGeneration = authState.generation;
  const idToken = await requestUser.getIdToken(false);
  if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) {
    throw new Error("The account changed while this chat was loading.");
  }
  const turns = [];
  const seenTurnIds = new Set();
  const seenCursors = new Set();
  let cursor = "";
  do {
    const path = "/bookmarks/" + encodeURIComponent(bookmark.id)
      + "/conversation?limit=50"
      + (cursor ? "&cursor=" + encodeURIComponent(cursor) : "");
    const response = await fetch(path, {
      headers: { "Authorization": "Bearer " + idToken }
    });
    if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) {
      throw new Error("The account changed while this chat was loading.");
    }
    const data = await response.json();
    if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) {
      throw new Error("The account changed while this chat was loading.");
    }
    if (!response.ok) {
      const error = new Error(data.detail || "This chat couldn’t be loaded.");
      error.retryable = response.status === 429 || response.status >= 500;
      throw error;
    }
    const pageChat = String(data.chat_id || "");
    if (chatId !== null && pageChat !== chatId) {
      throw new Error("This chat didn’t match its saved conversation.");
    }
    chatId = pageChat;
    (Array.isArray(data.turns) ? data.turns : []).forEach(turn => {
      const turnId = String(turn?.id || turn?.turn_id || "");
      if (turnId && seenTurnIds.has(turnId)) return;
      if (turnId) seenTurnIds.add(turnId);
      turns.push(turn);
    });
    const nextCursor = data.has_more ? String(data.next_cursor || "") : "";
    if (data.has_more && !nextCursor) {
      throw new Error("This chat’s conversation was incomplete.");
    }
    if (nextCursor && seenCursors.has(nextCursor)) {
      throw new Error("This chat’s conversation repeated a page.");
    }
    if (nextCursor) seenCursors.add(nextCursor);
    cursor = nextCursor;
  } while (cursor);
  return { chatId: chatId || "", turns };
}

async function loadBookmarkConversation(bookmarkId) {
  try {
    return await loadBookmarkConversationOnce(bookmarkId);
  } catch (error) {
    if (!error?.retryable) throw error;
    return await loadBookmarkConversationOnce(bookmarkId);
  }
}

function loadSingleBookmarkUI(sourceBookmark, conversationTurns = [], options = {}) {
    const materialized = materializeConversationBookmark(sourceBookmark, conversationTurns);
    const bookmark = materialized.bookmark;
    let bookmarkCitationModels = [];
    const displayQuestion = bookmarkDisplayQuestion(bookmark);
    // Ein Bookmark bringt seine eigene Ansicht mit: ein Direktvergleich laedt
    // als Direktvergleich zurueck (Composer oben, sechs Antworten darunter),
    // ein gefuehrter Lauf als Thread. Der aktuelle Agent-Mode-Schalter sagt
    // nur, was der NAECHSTE Lauf tun wird.
    const directComparison = isDirectComparisonBookmark(bookmark);
    // Ein geladenes Bookmark zeigt sofort Antworten und startet daher nie im
    // zentrierten Leerzustand.
    if (directComparison) {
        window.enterDirectComparisonView?.();
        window.App?.consensusPipeline?.dismiss?.();
    } else {
        window.exitHeroMode?.();
    }
    window.App?.followup?.reset?.();
    window.App?.chatSession?.reset?.();
    window.App?.bookmarkSession?.restore?.(sourceBookmark?.id);
    // One step, never emptied first: turns already on the page stay
    // (consensus-run.js renderStoredTurns).
    window.App?.followup?.renderStoredTurns?.(materialized.historyTurns.length
        ? materialized.historyTurns
        : (bookmark?.previous_turn ? [bookmark.previous_turn] : []));
    const continuationTurn = materialized.currentTurn;
    const authoritativeChatRestored = continuationTurn && bookmark.chat_id
      ? window.App?.chatSession?.restoreCompletedChat?.(
          bookmark.chat_id,
          continuationTurn.turn_id
        ) === true
      : false;
    window.App?.runRegistry?.showSavedView?.(
      { type: "bookmark", bookmarkId: sourceBookmark?.id || "" },
      {
        bookmarkId: sourceBookmark?.id || "",
        chatId: authoritativeChatRestored ? bookmark.chat_id : "",
        turnId: authoritativeChatRestored ? continuationTurn?.turn_id : "",
        question: displayQuestion,
        consensus: String(bookmark?.responses?.consensus || ""),
        executionMode: bookmark.mode === "Agent" ? "agent" : "consensus",
        currentTurn: continuationTurn || null,
        historyTurns: materialized.historyTurns || [],
        continuationUnavailable: !continuationTurn,
        title: bookmarkDisplayTitle(bookmark),
        bookmarkMeta: bookmarkMeta(sourceBookmark)
      }
    );
    window.App?.setAppTitle?.(displayQuestion);
    // Never let Share/Watch target a run that was displayed previously.
    // A consensus bookmark gets a reusable server-side snapshot on Share/Watch.
    prepareBookmarkShareResult(bookmark);

    // --- NEU: Quellen wiederherstellen ---
    // 1. Globale Variable setzen, damit injectMarkdown (in index.html) darauf zugreifen kann
    window.App.state.set("currentEvidenceSources", bookmark.sources || [], "evidence");

    // 2. Die Quellen-Liste (unten im UI) visuell rendern (falls die Funktion existiert)
    if (window.renderEvidenceSources) {
        window.renderEvidenceSources(bookmark.sources || []);
    }

    if (bookmark && bookmark.responses) {
        
        // HELPER: Nutzt die globale Funktion injectMarkdown aus der index.html, 
        // um Markdown korrekt zu rendern, Copy-Buttons hinzuzufügen etc.
        const renderContent = (container, text) => {
            if (!container) return;
            
            const content = text || "";
            
            if (window.injectMarkdown) {
                // Nutzt die Logik aus index.html (Marked + DOMPurify + Copy Buttons)
                window.injectMarkdown(container, content);
            } else {
                // Fallback, falls injectMarkdown noch nicht geladen ist
                // (nutzt die lokale renderMarkdownSafe Funktion von oben in firebase.js)
                container.innerHTML = typeof renderMarkdownSafe === "function" 
                                      ? renderMarkdownSafe(content) 
                                      : content;
            }
        };

        // Funktion für die Modell-Boxen
        const setModelContent = (id, text) => {
            const el = document.getElementById(id);
            if (el) {
                const contentArea = el.querySelector(".collapsible-content");
                renderContent(contentArea, text);
            }
        };

        (window.App?.modelPrefs || []).forEach(pref => {
            setModelContent(pref.responseId, bookmark.responses[pref.key]);
        });

        // --- Konsens Boxen ---
        // Strukturierten Zustand (Verdict, Karten, Badges) eines früheren Laufs
        // zuerst zurücksetzen, damit das geladene Bookmark nicht dessen Reste zeigt.
        window.resetConsensusInsights?.();
        const consensusDiv = document.getElementById("consensusResponse");
        if (window.resetCredibilityFrame) {
            window.resetCredibilityFrame(consensusDiv?.querySelector(".consensus-differences"));
        }

        const consensusText = bookmark.responses["consensus"] || "";

        // WICHTIG: Die Konsens-Antwort zuerst rendern – die Claim-Badges
        // (Modell-Zustimmung) verankern sich am Text der Hauptantwort.
        const conMain = window.App.consensusBodyEl(consensusDiv);
        // Consensus prose has carried no source references since 2026-09-11,
        // so a numeric [1] in it never picks up a citation (as in the live
        // run). Older answers with [S1] tags keep their citations.
        conMain.dataset.sourceReferences = /\[S\d/i.test(consensusText || '') ? 'legacy' : 'none';
        renderContent(conMain, consensusText);

        // --- Differences Box ---
        const conDiff = document.querySelector("#consensusResponse .consensus-differences p");

        // Strukturierte Ansicht (Verdict, Modellvergleich-Karten, Claim-Badges)
        // exakt wie nach einer echten Query rendern – sofern das Bookmark die
        // strukturierten differences_data enthält. Sonst Freitext-Fallback.
        const differencesData = bookmark.responses["differences_data"];
        const includedCount = bookmarkModelKeys()
            .filter(name => (bookmark.responses[name] || "").trim()).length;

        let structuredRendered = false;
        if (window.renderConsensusInsights && differencesData && typeof differencesData === "object") {
            structuredRendered = window.renderConsensusInsights(differencesData, includedCount, {sources: []});
        }

        // Resolve-Persistenz: Payload setzen, damit eine Resolve-Runde aus dem
        // geladenen Bookmark heraus ihr Ergebnis in dasselbe Bookmark schreibt.
        window.lastConsensusBookmarkPayload = (consensusText.trim() && bookmark.query) ? {
            question: bookmark.query,
            previousQuestion: bookmark.previous_question || "",
            previousTurn: bookmark.previous_turn || null,
            consensusText: consensusText,
            differencesText: bookmark.responses["differences"] || "",
            differencesData: (differencesData && typeof differencesData === "object") ? differencesData : null,
            conversation: materialized.currentTurn ? {
              bookmarkId: sourceBookmark.id,
              chatId: bookmark.chat_id,
              turnId: materialized.currentTurn.turn_id,
              modelResponses: Object.fromEntries(
                Object.entries(materialized.currentTurn.model_answers || {}).map(([provider, item]) => [
                  provider,
                  typeof item === "string" ? item : String(item?.answer || "")
                ])
              )
            } : { bookmarkId: sourceBookmark.id }
        } : null;

        if (!structuredRendered) {
            // Freitext-Fallback (ältere Bookmarks ohne differences_data),
            // inkl. optionaler Credibility-Badges (Farben). Das Panel bleibt
            // dann sichtbar aufgeklappt - der Freitext ist die einzige Analyse.
            window.App.differencesPanel?.expandForFallback?.();
            let diffText = bookmark.responses["differences"] || "";
            if (window.applyCredibilityFrame) {
                window.applyCredibilityFrame(conDiff, diffText);
            }
            if (window.colorizeCredibility) {
                diffText = window.colorizeCredibility(diffText);
            }
            renderContent(conDiff, diffText);
        }

        // Konsens-Bereich genau wie nach einer echten Anfrage einblenden – aber nur,
        // wenn das Bookmark tatsächlich einen Konsens enthält. So erscheint der
        // (rahmenlose) Bereich sichtbar und funktional (Copy, Quellen-Links).
        if (consensusText.trim()) {
            window.revealConsensusOutput?.();
            // Bookmark-Restore durchlaeuft keinen Query-/Consensus-Lifecycle.
            // Den fertigen Antwort-Footer daher explizit synchronisieren,
            // damit "Show model answers" und die vorhandenen Drawer immer
            // unter der wiederhergestellten Antwort stehen.
            window.updateAgentModeUI?.();
            window.App?.consensusPipeline?.renderProvenance?.();
            if (continuationTurn) {
                window.App?.followup?.offer?.(
                  displayQuestion,
                  consensusText,
                  continuationTurn
                );
            } else {
                window.App?.followup?.markContinuationUnavailable?.();
            }
        } else {
            window.hideConsensusOutput?.();
        }

        // Der Reasoning-Schalter beschreibt den NAECHSTEN Lauf und bleibt beim
        // Laden eines Bookmarks unangetastet -- auch fuer alte Bookmarks mit
        // mode "Deep Think" (Deep Think gibt es seit 2026-10-02 nicht mehr).

        // Historische Modellnamen erst nach allen Mode-Synchronisierungen
        // anwenden, weil updateReasoningUI sonst wieder die aktuelle Picker-
        // Auswahl in die Antworttitel schreiben würde.
        bookmarkCitationModels = applyBookmarkModelPresentation(bookmark);
        
        // Die Frage steht über der Antwort; das Eingabefeld unten bleibt frei
        // für die nächste Frage. Das gilt auch für den Direktvergleich: er
        // führt keinen Thread, aber die Frage gehört trotzdem auf den Schirm.
        if (bookmark.query) {
            window.App?.setThreadQuestion?.(displayQuestion);
            const questionInput = document.getElementById("questionInput");
            if (questionInput) {
                questionInput.value = "";
                questionInput.dispatchEvent(new Event("input", { bubbles: true }));
                window.syncDemoChipState?.();
            }
            // Ein Zitat gehört zu der Antwort, aus der es stammt — auf dem
            // Schirm steht jetzt eine andere.
            window.App?.quote?.clear?.();
            // Falls du eine globale Variable für die letzte Frage hast:
            window.App.state.set("lastQuestion", displayQuestion, "run");
        }

        // Anhänge des Bookmarks als Vorschau-Chips anzeigen (nur Metadaten,
        // die Dateien selbst sind nicht gespeichert und werden nicht mitgesendet)
        if (typeof window.showBookmarkAttachments === "function") {
            window.showBookmarkAttachments(bookmark.attachments || []);
        }
    }
    if (directComparison) window.App?.answerReader?.showDirectBookmark?.(bookmark);
    if (!continuationTurn) {
        window.App?.followup?.markContinuationUnavailable?.();
    }
    // === NEU: Citation-Meta immer nach dem Rendern setzen ===
    try {
        let includedModels = bookmarkCitationModels;

        if (!includedModels.length && typeof window.getIncludedModelNamesForCitation === "function") {
            // liest aus dem DOM (nur Boxen mit Inhalt & nicht "excluded")
            includedModels = window.getIncludedModelNamesForCitation();
        }

        window.App.state.set("consensusCitationMeta", {
            question: displayQuestion,
            includedModels: includedModels,
            consensusModel: bookmark.consensus_model || "",
            url: window.location.href.split("#")[0],
            dateISO:
                bookmark.created_at ||
                bookmark.createdAt ||
                bookmark.created_at_iso ||
                new Date().toISOString()
        }, "consensus");
    } catch (err) {
        console.warn("Could not rebuild consensusCitationMeta from bookmark:", err);
        window.App.state.set("consensusCitationMeta", null, "consensus");
    }
    if (options.conversationLoadFailed) {
        const message = authoritativeChatRestored
          ? "Some earlier messages could not be displayed. Follow-ups still use the saved chat context."
          : "The full saved conversation could not be loaded. Only the visible answer is available as follow-up context.";
        window.App?.showPopup?.(message);
    }
}

function renderBookmarksLoadMore() {
  document.getElementById("bookmarksLoadMore")?.remove();
  if (!bookmarksNextCursor) return;
  const container = document.getElementById("bookmarksContainer");
  if (!container) return;
  const button = document.createElement("button");
  button.type = "button";
  button.id = "bookmarksLoadMore";
  button.className = "bookmarks-load-more";
  button.textContent = "Load more";
  button.addEventListener("click", () => loadBookmarks({ append: true }));
  container.appendChild(button);
}

function restoreRegistryRunRows() {
  const currentUid = auth.currentUser?.uid || null;
  (window.App.runRegistry?.list?.() || []).forEach(context => {
    if (!currentUid || context.auth?.uid !== currentUid) return;
    if (context.bookmark?.deleted || context.bookmark?.deleting) return;
    if (context.bookmark?.uiReady && context.bookmark?.latestMeta) {
      replacePendingBookmarkWithReady(context.bookmark.latestMeta, context.runId);
    } else {
      window.App.runView?.ensureRunRow?.(context);
    }
  });
}

function renderBookmarksLoadError(container) {
  if (!container) return;
  container.innerHTML = "";
  restoreRegistryRunRows();
  const state = document.createElement("div");
  state.className = "bookmarks-load-error";
  const message = document.createElement("p");
  message.textContent = "Your chats couldn’t be loaded.";
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "bookmarks-load-more";
  retry.textContent = "Try again";
  retry.addEventListener("click", async () => {
    bookmarksLoaded = await loadBookmarks();
  });
  state.append(message, retry);
  container.appendChild(state);
}

async function loadBookmarks({ append = false, loadAll = false } = {}) {
  if (!auth.currentUser || bookmarksLoading) return false;
  const requestUser = auth.currentUser;
  const requestUid = requestUser.uid;
  const requestGeneration = authState.generation;
  const requestId = ++bookmarksLoadRequestId;
  bookmarksLoading = true;
  const container = document.getElementById("bookmarksContainer");
  try {
    const idToken = await requestUser.getIdToken(false);
    if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return false;
    let cursor = append ? bookmarksNextCursor : null;
    if (!append) {
      window.bookmarksData = [];
      bookmarksNextCursor = null;
      // Keep the first-paint placeholder until the metadata actually arrives.
      const skeleton = container?.querySelector(".bookmarks-skeleton");
      if (container) container.replaceChildren(...(skeleton ? [skeleton] : []));
      // A metadata refresh must not make an in-flight bookmark disappear.
      ensurePendingBookmarkDOM(window.App.bookmarkSession?.pending);
      restoreRegistryRunRows();
    }
    do {
      // 35 statt 30: auf einem grossen Monitor stand der "Load more"-Button
      // sonst dauerhaft unter einer Liste, die ohnehin komplett sichtbar war.
      const path = "/bookmarks?limit=35" + (cursor ? "&cursor=" + encodeURIComponent(cursor) : "");
      const response = await fetch(path, { headers: { "Authorization": "Bearer " + idToken } });
      if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return false;
      const data = await response.json();
      if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return false;
      if (!response.ok) throw new Error(data.detail || `Your chats couldn’t be loaded (${response.status}).`);
      const skeleton = container?.querySelector(".bookmarks-skeleton");
      const shown = new Set(container?.children || []);
      (data.bookmarks || []).forEach(item => upsertBookmarkMeta(item, { prepend: false, nameIt: false }));
      if (!append && container) revealLoadedBookmarks(container, skeleton, shown);
      else skeleton?.remove();
      bookmarksNextCursor = data.next_cursor || null;
      cursor = bookmarksNextCursor;
    } while (loadAll && cursor);
    renderBookmarksLoadMore();
    syncActiveBookmark();
    window.filterBookmarks?.(document.getElementById("chatSearch")?.value || "");
    // The example questions predicted from the newest chats (composer-starters.js).
    if (!append) window.App.composerStarters?.refresh?.();
    return true;
  } catch (error) {
    if (isCurrentAuthenticatedUser(requestUid, requestGeneration)) {
      console.error("Error in loadBookmarks:", error);
      if (!append || !window.bookmarksData?.length) renderBookmarksLoadError(container);
      else window.App?.showPopup?.("More chats couldn’t be loaded.");
    }
    return false;
  } finally {
    if (requestId === bookmarksLoadRequestId) bookmarksLoading = false;
  }
}

// The first page takes over from the placeholder in place: the skeleton
// fades out where it stood while the real rows fade in over it. Swapping
// grey bars for 35 rows in one frame read as a jolt at the end of loading.
function revealLoadedBookmarks(container, skeleton, shown) {
  const rows = [...container.children].filter(row => !shown.has(row) && row !== skeleton);
  const quiet = !container.animate || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (quiet || !rows.length || !skeleton?.isConnected) {
    skeleton?.remove();
    if (quiet) return;
  } else {
    // Out of the flow at its exact place, so the rows take its slot now.
    const top = skeleton.getBoundingClientRect().top - container.getBoundingClientRect().top - container.clientTop;
    skeleton.removeAttribute("role");
    skeleton.setAttribute("aria-hidden", "true");
    Object.assign(skeleton.style, { position: "absolute", top: `${top}px`, left: "0", right: "0", pointerEvents: "none" });
    container.style.position = "relative";
    const fade = skeleton.animate([{ opacity: 1 }, { opacity: 0 }], { duration: window.App?.motion?.ms?.("state") ?? 200, easing: window.App?.motion?.ease?.("out") ?? "ease-out", fill: "forwards" });
    fade.finished.catch(() => {}).then(() => {
      skeleton.remove();
      if (!container.querySelector(".bookmarks-skeleton")) container.style.position = "";
    });
  }
  // Only what is on screen settles in; the rows below the fold just appear.
  rows.slice(0, 16).forEach((row, index) => row.animate(
    [{ opacity: 0 }, { opacity: 1 }],
    { duration: window.App?.motion?.ms?.("state") ?? 200, delay: Math.min(index, 10) * 16, easing: window.App?.motion?.ease?.("out") ?? "ease-out", fill: "backwards" }
  ));
}

async function loadBookmarkDetail(bookmarkId) {
  if (!auth.currentUser) throw new Error("Authentication required");
  if (bookmarkDetailCache.has(bookmarkId)) return bookmarkDetailCache.get(bookmarkId);
  const requestUser = auth.currentUser;
  const requestUid = requestUser.uid;
  const requestGeneration = authState.generation;
  const idToken = await requestUser.getIdToken(false);
  if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) {
    throw new Error("The account changed while this chat was loading.");
  }
  const response = await fetch("/bookmarks/" + encodeURIComponent(bookmarkId), {
    headers: { "Authorization": "Bearer " + idToken }
  });
  if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) {
    throw new Error("The account changed while this chat was loading.");
  }
  const data = await response.json();
  if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) {
    throw new Error("The account changed while this chat was loading.");
  }
  if (!response.ok) throw new Error(data.detail || "This chat couldn’t be loaded.");
  bookmarkDetailCache.clear();
  bookmarkDetailCache.set(bookmarkId, data.bookmark);
  return data.bookmark;
}

// The chat on screen is marked in the list (shell.css .bookmark.is-active):
// at once when its row is chosen, and from then on by what the view shows.
function activeBookmarkId() {
  const registry = window.App.runRegistry;
  const visible = registry?.visible?.();
  if (visible) return visible.bookmark?.id || "";
  return registry?.getSelectedConversationIdentity?.()?.bookmarkId || "";
}
function syncActiveBookmark(bookmarkId = activeBookmarkId()) {
  document.querySelectorAll("#bookmarksContainer .bookmark").forEach(row => {
    const active = Boolean(bookmarkId) && row.dataset.id === bookmarkId;
    if (row.classList.contains("is-active") === active) return;
    row.classList.toggle("is-active", active);
    if (active) row.setAttribute("aria-current", "true"); else row.removeAttribute("aria-current");
  });
}
window.addEventListener("consensio:run-registry-change", () => syncActiveBookmark());

// While a chat that is not in memory loads, the thread already shows it:
// its question and a quiet answer skeleton (Apple audit D2). The view of the
// chat before is only hidden (body.chat-opening), so a failed load gives it
// back unchanged.
function showChatOpening(bookmarkId) {
  const column = document.querySelector(".container");
  if (!column) return null;
  hideChatOpening();
  const meta = (window.bookmarksData || []).find(item => item.id === bookmarkId);
  const block = document.createElement("div");
  block.className = "thread-opening";
  block.setAttribute("role", "status");
  block.setAttribute("aria-label", "Opening chat");
  const question = String(meta?.query || "").replace(/\s+/g, " ").trim();
  if (question) {
    const ask = document.createElement("div");
    ask.className = "thread-ask";
    const bubble = document.createElement("div");
    bubble.className = "thread-ask-bubble";
    const text = document.createElement("div");
    text.className = "thread-ask-text thread-opening-question";
    text.textContent = question;
    bubble.append(text);
    ask.append(bubble);
    block.append(ask);
  }
  const lines = document.createElement("div");
  lines.className = "answer-skeleton skeleton-group";
  lines.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 4; i += 1) {
    const line = document.createElement("span");
    line.className = "skeleton";
    lines.append(line);
  }
  block.append(lines);
  column.prepend(block);
  const wasHero = document.body.classList.contains("is-hero");
  window.exitHeroMode?.();
  document.body.classList.add("chat-opening");
  window.scrollTo({ top: 0, left: window.scrollX, behavior: "instant" });
  return { block, wasHero };
}
function hideChatOpening(opening = null, { restore = false } = {}) {
  document.body.classList.remove("chat-opening");
  document.querySelectorAll(".container > .thread-opening").forEach(block => block.remove());
  if (restore && opening?.wasHero) {
    document.body.classList.add("is-hero");
    window.syncHeroResponseAccess?.();
  }
}

// Detail and transcript of one chat, requested side by side. A transcript
// that is missing, broken or belongs to another chat falls back to the saved
// continuation data, as before.
async function loadBookmarkView(bookmarkId) {
  const conversation = loadBookmarkConversation(bookmarkId).catch(error => ({ error }));
  const bookmark = await loadBookmarkDetail(bookmarkId);
  const result = await conversation;
  let turns = [];
  let conversationLoadFailed = false;
  if (bookmark?.chat_id) {
    if (result.error || String(result.chatId || "") !== String(bookmark.chat_id)) {
      conversationLoadFailed = true;
      console.warn("Could not load full bookmark conversation; using saved continuation data.",
        result.error || new Error("This chat didn’t match its saved conversation."));
    } else {
      turns = result.turns;
    }
  }
  return { bookmark, turns, conversationLoadFailed };
}
function rememberBookmarkView(bookmarkId, view) {
  bookmarkViewCache.delete(bookmarkId);
  if (view.conversationLoadFailed) return;
  bookmarkViewCache.set(bookmarkId, view);
  while (bookmarkViewCache.size > BOOKMARK_VIEW_CACHE_SIZE) {
    bookmarkViewCache.delete(bookmarkViewCache.keys().next().value);
  }
}
// What a chat's view is made of, to tell whether a background check found
// anything new.
function bookmarkViewSignature(view) {
  return JSON.stringify([view.bookmark?.timestamp || null, view.bookmark?.title || "", view.bookmark?.responses?.consensus?.length || 0,
    (view.turns || []).map(turn => [turn.id || turn.turn_id, turn.status, turn.agent_review?.status, String(turn.consensus || "").length])]);
}

window.openBookmark = async function (bookmarkId) {
  if (!bookmarkWriteAllowed(auth.currentUser?.uid, bookmarkId)) return;
  // The tap is answered at once: the phone menu closes and the row is
  // marked before anything loads (Apple audit D2).
  window.App.chatScroll?.closeMenu?.();
  syncActiveBookmark(bookmarkId);
  const requestEpoch = ++bookmarkViewEpoch;
  const liveContext = window.App.runRegistry?.findByBookmarkId?.(bookmarkId);
  if (liveContext) {
    window.App.runRegistry.show(liveContext.runId);
    window.App.chatScroll?.opened?.();
    trackAppEvent("app_bookmark_opened", { source: "run_registry" });
    return;
  }
  const requestUid = auth.currentUser?.uid || null;
  const requestGeneration = authState.generation;
  const viewIsCurrent = () => requestEpoch === bookmarkViewEpoch
    && isCurrentAuthenticatedUser(requestUid, requestGeneration)
    && bookmarkWriteAllowed(requestUid, bookmarkId);
  const show = view => {
    hideChatOpening();
    openedBookmarkId = bookmarkId;
    loadSingleBookmarkUI(view.bookmark, view.turns, { conversationLoadFailed: view.conversationLoadFailed });
    window.App.chatScroll?.opened?.();
  };
  // A chat seen a moment ago is there at once and checked in the background;
  // only a change since then redraws it, without moving the reader.
  const cached = bookmarkViewCache.get(bookmarkId);
  if (cached) {
    bookmarkViewCache.delete(bookmarkId);
    bookmarkViewCache.set(bookmarkId, cached);
    show(cached);
    trackAppEvent("app_bookmark_opened", { source: "cache" });
    const shownEpoch = bookmarkViewEpoch;
    bookmarkDetailCache.delete(bookmarkId);
    try {
      const fresh = await loadBookmarkView(bookmarkId);
      const stillShown = shownEpoch === bookmarkViewEpoch && isCurrentAuthenticatedUser(requestUid, requestGeneration)
        && bookmarkWriteAllowed(requestUid, bookmarkId);
      if (!stillShown) return;
      if (bookmarkViewSignature(fresh) !== bookmarkViewSignature(cached)) {
        loadSingleBookmarkUI(fresh.bookmark, fresh.turns, { conversationLoadFailed: fresh.conversationLoadFailed });
      }
      rememberBookmarkView(bookmarkId, fresh);
    } catch (error) {
      console.warn("Could not check the opened chat for changes.", error);
    }
    return;
  }
  const row = document.querySelector(`.bookmark:not(.run-entry)[data-id="${bookmarkId}"]`);
  row?.classList.add("is-loading");
  const opening = showChatOpening(bookmarkId);
  try {
    const view = await loadBookmarkView(bookmarkId);
    if (!viewIsCurrent()) return;
    show(view);
    rememberBookmarkView(bookmarkId, view);
    trackAppEvent("app_bookmark_opened");
  } catch (error) {
    if (!viewIsCurrent()) return;
    hideChatOpening(opening, { restore: true });
    syncActiveBookmark();
    console.error("Error opening bookmark:", error);
    window.App?.showPopup?.("This chat couldn’t be opened. Try again.");
  } finally {
    row?.classList.remove("is-loading");
    // A newer choice took over the view: its own opening stays.
    if (requestEpoch !== bookmarkViewEpoch && !document.querySelector(".container > .thread-opening")) syncActiveBookmark();
  }
};

window.loadAllBookmarkMetadata = async function () {
  if (!bookmarksNextCursor) return true;
  return loadBookmarks({ append: true, loadAll: true });
};

window.loadBookmarks = loadBookmarks;

async function deleteBookmark(bookmarkId) {
  const requestUser = auth.currentUser;
  if (!requestUser) return;
  const requestUid = requestUser.uid;
  const requestGeneration = authState.generation;
  const mutationKey = bookmarkMutationKey(requestUid, bookmarkId);
  if (deletingBookmarks.has(mutationKey)) return deletingBookmarks.get(mutationKey);
  // Fence immediately. Earlier model/consensus/share writes drain first in
  // the same queue; anything started after this click is rejected, so no late
  // callback can recreate the document after DELETE.
  deletedBookmarkKeys.add(mutationKey);
  window.App.runRegistry?.blockBookmarkMutation?.(bookmarkId);
  window.App.runRegistry?.cancelActionsForBookmark?.(bookmarkId, "bookmark_deleted");
  const contexts = (window.App.runRegistry?.list?.() || []).filter(item => item.bookmark?.id === bookmarkId);
  contexts.forEach(context => { context.bookmark.deleting = true; });
  const metaIndex = (window.bookmarksData || []).findIndex(item => item.id === bookmarkId);
  const meta = window.bookmarksData?.[metaIndex];
  window.bookmarksData = (window.bookmarksData || []).filter(item => item.id !== bookmarkId);
  const rows = Array.from(document.querySelectorAll(`.bookmark[data-id="${bookmarkId}"]`)).map(row => {
    const saved = { row, parent: row.parentNode, next: row.nextSibling, animation: null };
    const height = row.getBoundingClientRect().height;
    const style = getComputedStyle(row);
    row.classList.add('is-deleting');
    if (row.animate && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      saved.animation = row.animate([
        { height: `${height}px`, opacity: 1, paddingTop: style.paddingTop, paddingBottom: style.paddingBottom, marginBottom: style.marginBottom, transform: 'translateX(0)' },
        { height: '0px', opacity: 0, paddingTop: '0px', paddingBottom: '0px', marginBottom: '0px', transform: 'translateX(-8px)' }
      ], { duration: window.App?.motion?.ms?.("state") ?? 200, easing: window.App?.motion?.ease?.("out") ?? 'ease-out', fill: 'forwards' });
      saved.animation.onfinish = () => row.remove();
    } else row.remove();
    return saved;
  });
  const restore = () => {
    if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;
    contexts.forEach(context => { context.bookmark.deleting = false; });
    if (meta && !window.bookmarksData.some(item => item.id === bookmarkId)) {
      window.bookmarksData.splice(Math.min(metaIndex, window.bookmarksData.length), 0, meta);
    }
    rows.forEach(({ row, parent, next, animation }) => {
      if (animation) { animation.onfinish = null; animation.cancel(); }
      row.classList.remove('is-deleting', 'is-undo-pending');
      if (!document.querySelector(`.bookmark[data-id="${bookmarkId}"]`) && parent?.isConnected) {
        parent.insertBefore(row, next?.parentNode === parent ? next : null);
      }
    });
    window.filterBookmarks?.(document.getElementById('chatSearch')?.value || '');
  };

  const deletion = enqueueBookmarkWrite(requestUid, requestGeneration, bookmarkId, async () => {
    let requestStarted = false;
    try {
      const id_token = await requestUser.getIdToken(false);
      if (!id_token) {
        deletedBookmarkKeys.delete(mutationKey);
        window.App.runRegistry?.unblockBookmarkMutation?.(bookmarkId);
        restore();
        if (isCurrentAuthenticatedUser(requestUid, requestGeneration)) window.App?.showPopup?.('This chat couldn’t be deleted. Try again.');
        return;
      }
      requestStarted = true;
      // keepalive: a deletion whose Undo the closing tab let happen
      // (visibilitychange) still arrives.
      const res = await fetch("/bookmark", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token, bookmarkId }),
        keepalive: true
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        restore();
        // A received 4xx proves that this request did not commit. A transport
        // failure or 5xx is ambiguous: the idempotent DELETE may already have
        // committed and only its response was lost. Keep the tombstone in that
        // case so queued/later saves cannot recreate the document.
        if (res.status >= 400 && res.status < 500) {
          deletedBookmarkKeys.delete(mutationKey);
          window.App.runRegistry?.unblockBookmarkMutation?.(bookmarkId);
          if (isCurrentAuthenticatedUser(requestUid, requestGeneration)) window.App?.showPopup?.('This chat couldn’t be deleted. Try again.');
        } else {
          if (isCurrentAuthenticatedUser(requestUid, requestGeneration)) window.App?.showPopup?.(
            "It’s not certain this chat was deleted. Delete it again or reload before you continue it."
          );
        }
        console.error("Error deleting bookmark:", data.detail);
        return;
      }

      // The user intent and server mutation remain valid after logout, but UI
      // from an old auth generation must not repaint a newly signed-in view.
      if (!isCurrentAuthenticatedUser(requestUid, requestGeneration)) return;

      // Lokales Array und DOM aktualisieren.
      window.bookmarksData = window.bookmarksData.filter(b => b.id !== bookmarkId);
      // A deleted chat's topic must not stay among the predicted examples.
      window.App.composerStarters?.refresh?.();
      bookmarkDetailCache.delete(bookmarkId);
      bookmarkViewCache.delete(bookmarkId);
      if (openedBookmarkId === bookmarkId) openedBookmarkId = null;
      (window.App.runRegistry?.list?.() || [])
        .filter(context => context.bookmark?.id === bookmarkId)
        .forEach(context => {
          if (window.App.runRegistry.isExecuting(context.runId)) {
            window.App.runRegistry.cancel(context.runId, "bookmark_deleted");
          }
          window.App.runRegistry.update(context.runId, current => {
            current.bookmark.deleted = true;
            current.bookmark.deleting = false;
            current.bookmark.latestMeta = null;
            current.bookmark.uiReady = true;
          }, { render: false, eventType: "persistence" });
        });
      const selectedBasis = window.App.runRegistry?.getSelectedConversationBasis?.();
      if (selectedBasis?.bookmarkId === bookmarkId) {
        window.App.runRegistry?.clearVisible?.();
        window.clearResponseBoxes?.({ silent: true });
      }
      document.querySelectorAll(`.bookmark[data-id="${bookmarkId}"]`).forEach(el => el.remove());
      window.clearPreparedBookmarkShareResult?.();
      trackAppEvent("app_bookmark_deleted");
    } catch (error) {
      restore();
      if (!requestStarted) {
        deletedBookmarkKeys.delete(mutationKey);
        window.App.runRegistry?.unblockBookmarkMutation?.(bookmarkId);
        if (isCurrentAuthenticatedUser(requestUid, requestGeneration)) window.App?.showPopup?.('This chat couldn’t be deleted. Try again.');
      } else {
        if (isCurrentAuthenticatedUser(requestUid, requestGeneration)) window.App?.showPopup?.(
          "It’s not certain this chat was deleted. Delete it again or reload before you continue it."
        );
      }
      console.error("Error in deleteBookmark:", error);
    }
  }, null, { allowStaleAuth: true }).finally(() => deletingBookmarks.delete(mutationKey));
  deletingBookmarks.set(mutationKey, deletion);
  return deletion;
}
window.deleteBookmark = deleteBookmark;

function updateBookmarkDOM(bookmark) {
  const row = document.querySelector(`.bookmark:not(.run-entry)[data-id="${bookmark.id}"]`);
  const label = row?.querySelector(":scope > p");
  if (label) label.textContent = bookmarkLabelText(bookmarkDisplayTitle(bookmark));
  const control = row?.querySelector(".bookmark-menu-button");
  if (control) labelBookmarkMenu(control, label?.textContent);
}

// ---- A chat row --------------------------------------------------------
// The title is the row's control (role="button", Enter or Space opens it,
// Apple audit E5); a pointer may press anywhere on the row. "…" opens a
// small menu with Rename, Share and Delete (E2); a deleted chat can be taken
// back for a few seconds. One delegated listener serves every row, so a run
// row that turns into a saved one in place keeps working.
const BOOKMARK_MENU_ICON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><circle cx="5.5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18.5" cy="12" r="1.6"/></svg>';
const BOOKMARK_MENU_ITEMS = [
  ["rename", "Rename", "M4 20h4L19 9l-4-4L4 16v4ZM14 6l4 4"],
  ["share", "Share", "M12 15V4m-4 4 4-4 4 4M5 13v6h14v-6"],
  ["delete", "Delete", "M5 7h14M10 7V5h4v2m-6 0 1 12h6l1-12"],
];
const BOOKMARK_UNDO_MS = 5000;

// Share only offers a chat with a saved answer to share: a Consensus or,
// since 2026-10-21, an Agent answer (its turn, share-dialog.js). A direct
// comparison has none and leaves Share out instead of opening a dialog that
// can only say no; so does a row whose chat is not in the list.
function bookmarkShareable(meta) {
  return meta?.has_consensus === true;
}

function labelBookmarkMenu(control, title) {
  control.setAttribute("aria-label", title ? `Chat options: ${title}` : "Chat options");
  control.title = "More";
}

function setBookmarkTitleControl(label) {
  label.setAttribute("role", "button");
  label.tabIndex = 0;
}

function createReadyBookmarkRow(bookmark, runId = null) {
  const div = document.createElement("div");
  div.className = "bookmark";
  div.dataset.id = bookmark.id;
  if (runId) div.dataset.runId = runId;
  // Die Frage kommt als freier Nutzertext und darf nie als HTML interpretiert
  // werden - deshalb textContent statt Template-Interpolation in innerHTML.
  const label = document.createElement("p");
  label.textContent = bookmarkLabelText(bookmarkDisplayTitle(bookmark));
  setBookmarkTitleControl(label);
  div.append(label, createBookmarkMenuButton(label.textContent));
  if (bookmark.id && bookmark.id === activeBookmarkId()) {
    div.classList.add("is-active");
    div.setAttribute("aria-current", "true");
  }
  // A chat whose deletion can still be taken back stays out of sight.
  if (undoableBookmarkDeletes.has(bookmark.id)) div.classList.add("is-undo-pending");
  return div;
}

function createBookmarkMenuButton(title) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "bookmark-menu-button";
  button.innerHTML = BOOKMARK_MENU_ICON;
  button.setAttribute("aria-haspopup", "menu");
  button.setAttribute("aria-expanded", "false");
  labelBookmarkMenu(button, title);
  return button;
}

document.addEventListener("click", event => {
  const container = document.getElementById("bookmarksContainer");
  if (!container?.contains(event.target)) return;
  const menuButton = event.target.closest(".bookmark-menu-button");
  if (menuButton) {
    event.stopPropagation();
    if (openBookmarkMenu?.button === menuButton) closeBookmarkMenu();
    else showBookmarkMenu(menuButton, { keyboard: event.detail === 0 });
    return;
  }
  if (event.target.closest(".bookmark-rename-input")) return;
  const row = event.target.closest(".bookmark");
  if (!row || row.classList.contains("run-entry") || row.classList.contains("is-pending")
      || row.classList.contains("is-deleting") || row.classList.contains("is-renaming") || !row.dataset.id) return;
  window.openBookmark(row.dataset.id);
});
document.addEventListener("keydown", event => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const label = event.target.closest?.("#bookmarksContainer .bookmark:not(.run-entry, .is-pending) > p[role='button']");
  if (!label || label.closest(".is-renaming")) return;
  event.preventDefault();
  window.openBookmark(label.parentElement.dataset.id);
});

// The menu lives on <body>, so the list's scrolling and soft edge never cut
// it; it sits at the "…" it came from and closes like any menu: Escape, a
// press elsewhere, Tab, or the list scrolling away under it.
let openBookmarkMenu = null;
function showBookmarkMenu(button, { keyboard = false } = {}) {
  closeBookmarkMenu();
  // A menu still on its way out gives way to the new one at once.
  document.querySelectorAll(".bookmark-menu.is-leaving").forEach(menu => menu.remove());
  const row = button.closest(".bookmark");
  if (!row?.dataset.id) return;
  const menu = document.createElement("div");
  menu.className = "bookmark-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", button.getAttribute("aria-label") || "Chat options");
  const meta = (window.bookmarksData || []).find(item => item.id === row.dataset.id);
  for (const [action, label, path] of BOOKMARK_MENU_ITEMS) {
    if (action === "share" && !bookmarkShareable(meta)) continue;
    const item = document.createElement("button");
    item.type = "button";
    item.className = `bookmark-menu-item${action === "delete" ? " is-destructive" : ""}`;
    item.setAttribute("role", "menuitem");
    item.tabIndex = -1;
    item.dataset.action = action;
    item.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg>`;
    const text = document.createElement("span");
    text.textContent = label;
    item.append(text);
    menu.append(item);
  }
  // One of the app's popovers: it closes any other menu and comes out of
  // its "…" (App.popover, overlays.css), and leaves the same way.
  window.App.popover?.register(menu, { close: () => closeBookmarkMenu() });
  window.App.popover?.opened(menu, { trigger: button });
  document.body.append(menu);
  const bounds = button.getBoundingClientRect();
  const width = menu.offsetWidth, height = menu.offsetHeight;
  const below = bounds.bottom + 4 + height <= window.innerHeight - 8;
  menu.style.left = `${Math.max(8, Math.min(bounds.right - width, window.innerWidth - width - 8))}px`;
  menu.style.top = `${below ? bounds.bottom + 4 : Math.max(8, bounds.top - 4 - height)}px`;
  menu.classList.toggle("opens-up", !below);
  button.setAttribute("aria-expanded", "true");
  row.classList.add("has-menu");
  openBookmarkMenu = { menu, button, row };
  const items = [...menu.querySelectorAll(".bookmark-menu-item")];
  const focusItem = index => items[(index + items.length) % items.length]?.focus({ preventScroll: true });
  menu.addEventListener("keydown", event => {
    const index = items.indexOf(document.activeElement);
    if (event.key === "ArrowDown") { event.preventDefault(); focusItem(index + 1); }
    else if (event.key === "ArrowUp") { event.preventDefault(); focusItem(index - 1); }
    else if (event.key === "Home") { event.preventDefault(); focusItem(0); }
    else if (event.key === "End") { event.preventDefault(); focusItem(items.length - 1); }
    else if (event.key === "Escape") { event.preventDefault(); closeBookmarkMenu({ focus: true }); }
    else if (event.key === "Tab") closeBookmarkMenu();
  });
  menu.addEventListener("click", event => {
    const item = event.target.closest(".bookmark-menu-item");
    if (!item) return;
    event.stopPropagation();
    const bookmarkId = row.dataset.id;
    closeBookmarkMenu({ focus: item.dataset.action !== "rename" && item.dataset.action !== "delete" });
    if (item.dataset.action === "rename") startBookmarkRename(row);
    else if (item.dataset.action === "share") shareBookmark(bookmarkId);
    else if (item.dataset.action === "delete") deleteBookmarkWithUndo(bookmarkId);
  });
  // Keyboard users land on the first item; after a pointer press the menu
  // itself holds focus, so the arrow keys still reach the items.
  menu.tabIndex = -1;
  if (keyboard) focusItem(0);
  else menu.focus({ preventScroll: true });
}
function closeBookmarkMenu({ focus = false } = {}) {
  if (!openBookmarkMenu) return;
  const { menu, button, row } = openBookmarkMenu;
  openBookmarkMenu = null;
  if (window.App.popover) {
    window.App.popover.leave(menu, () => {
      window.App.popover.unregister(menu);
      menu.remove();
    });
  } else menu.remove();
  button.setAttribute("aria-expanded", "false");
  row.classList.remove("has-menu");
  if (focus && button.isConnected) button.focus({ preventScroll: true });
}
document.addEventListener("pointerdown", event => {
  if (openBookmarkMenu && !openBookmarkMenu.menu.contains(event.target) && !openBookmarkMenu.button.contains(event.target)) {
    closeBookmarkMenu();
  }
}, true);
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && openBookmarkMenu && !openBookmarkMenu.menu.contains(event.target)) closeBookmarkMenu({ focus: true });
});
window.addEventListener("resize", () => closeBookmarkMenu(), { passive: true });
document.addEventListener("scroll", event => {
  if (openBookmarkMenu && event.target instanceof Element && event.target.contains(openBookmarkMenu.row)) closeBookmarkMenu();
}, { passive: true, capture: true });

// Rename in place: the title becomes a field of the same size; Enter or
// leaving it saves, Escape keeps the old name.
function startBookmarkRename(row) {
  const label = row.querySelector(":scope > p");
  const bookmarkId = row.dataset.id;
  if (!label || !bookmarkId || row.classList.contains("is-renaming")) return;
  const previous = label.textContent;
  const input = document.createElement("input");
  input.type = "text";
  input.className = "bookmark-rename-input";
  input.value = previous;
  input.maxLength = 120;
  input.setAttribute("aria-label", "Chat name");
  input.autocomplete = "off";
  input.spellcheck = false;
  row.classList.add("is-renaming");
  label.hidden = true;
  label.after(input);
  input.focus({ preventScroll: true });
  input.select();
  let finished = false;
  const finish = save => {
    if (finished) return;
    finished = true;
    const value = input.value.replace(/\s+/g, " ").trim();
    input.remove();
    label.hidden = false;
    row.classList.remove("is-renaming");
    if (document.activeElement === document.body || !document.activeElement) label.focus({ preventScroll: true });
    if (!save || !value || value === previous) return;
    label.textContent = bookmarkLabelText(value);
    renameBookmark(bookmarkId, value).then(named => {
      if (named) applyBookmarkTitle(named, "user");
    }).catch(error => {
      console.warn("Bookmark rename failed:", error);
      if (label.isConnected && label.textContent === bookmarkLabelText(value)) label.textContent = previous;
      window.App?.showPopup?.("This chat couldn’t be renamed. Try again.");
    });
  };
  input.addEventListener("keydown", event => {
    event.stopPropagation();
    // An Enter confirming an input method's word stays the word's (E8).
    if (event.key === "Enter" && !(event.isComposing || event.keyCode === 229)) { event.preventDefault(); finish(true); }
    else if (event.key === "Escape") { event.preventDefault(); finish(false); }
  });
  input.addEventListener("blur", () => finish(true));
}

async function renameBookmark(bookmarkId, title) {
  const user = auth.currentUser;
  if (!user) throw new Error("Authentication required");
  const requestUid = user.uid, generation = authState.generation;
  const idToken = await user.getIdToken(false);
  if (!isCurrentAuthenticatedUser(requestUid, generation)) return null;
  const response = await fetch("/bookmarks/" + encodeURIComponent(bookmarkId) + "/title", {
    method: "PATCH",
    headers: { "Authorization": "Bearer " + idToken, "Content-Type": "application/json" },
    body: JSON.stringify({ title })
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Rename failed (${response.status})`);
  if (!isCurrentAuthenticatedUser(requestUid, generation)) return null;
  bookmarkViewCache.delete(bookmarkId);
  return data.bookmark || null;
}

// Share works on the chat on screen: it opens first (at once when it was
// seen a moment ago), then the share dialog.
async function shareBookmark(bookmarkId) {
  await window.openBookmark(bookmarkId);
  if (activeBookmarkId() !== bookmarkId) return;
  // A chat whose Agent run is on screen opens no saved view to prepare:
  // Share takes the answer of that run, by its turn (share-dialog.js).
  const run = window.App.runRegistry?.visible?.();
  if (run?.bookmark?.id === bookmarkId && run.config?.executionMode === "agent") {
    window.App.answerShare?.open({ chatId: run.metadata?.chatId, turnId: run.consensus?.completedTurn?.id });
    return;
  }
  window.openShareDialog?.();
}

// A deleted chat leaves the list at once and "Chat deleted · Undo" offers
// it back for a few seconds; only then is it deleted on the server. Nothing
// is fenced or cancelled while it can still come back. A new run, a hidden
// page or signing out deletes it at once, so the chat limit and the page
// lifetime never hold it back.
const undoableBookmarkDeletes = new Map();
function collapseBookmarkRow(row) {
  const done = () => { row.classList.add("is-undo-pending"); row.style.removeProperty("overflow"); };
  if (!row.animate || matchMedia("(prefers-reduced-motion: reduce)").matches || !row.getClientRects().length) { done(); return; }
  const height = row.getBoundingClientRect().height;
  const style = getComputedStyle(row);
  row.style.overflow = "hidden";
  const animation = row.animate([
    { height: `${height}px`, opacity: 1, paddingTop: style.paddingTop, paddingBottom: style.paddingBottom, marginBottom: style.marginBottom },
    { height: "0px", opacity: 0, paddingTop: "0px", paddingBottom: "0px", marginBottom: "0px" }
  ], { duration: window.App?.motion?.ms?.("state") ?? 200, easing: window.App?.motion?.ease?.("out") ?? "ease-out" });
  animation.onfinish = done;
  row._collapse = animation;
}
function expandBookmarkRow(row) {
  row._collapse?.cancel();
  row._collapse = null;
  row.classList.remove("is-undo-pending");
  row.style.removeProperty("overflow");
  insertBookmarkRowSoftly(row);
}
// A row that joins the list opens its place instead of pushing the rows
// below by a whole row in one frame (Apple audit A11, C12).
function insertBookmarkRowSoftly(row) {
  if (!row.animate || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  // Measured in the frame the row first shows in, after everything else the
  // send wrote: read at once, it forced the half-built thread's layout in
  // the middle of the click (Apple-Audit D3).
  requestAnimationFrame(() => {
    if (!row.isConnected || !row.getClientRects().length) return;
    const height = row.getBoundingClientRect().height;
    if (!height) return;
    const style = getComputedStyle(row);
    row.animate([
      { height: "0px", opacity: 0, paddingTop: "0px", paddingBottom: "0px", overflow: "hidden" },
      { height: `${height}px`, opacity: 1, paddingTop: style.paddingTop, paddingBottom: style.paddingBottom, overflow: "hidden" }
    ], { duration: window.App?.motion?.ms?.("state") ?? 200, easing: window.App?.motion?.ease?.("out") ?? "cubic-bezier(.22, 1, .36, 1)" });
  });
}
function leaveDeletedChat() {
  window.App.runRegistry?.clearVisible?.();
  window.clearResponseBoxes?.({ silent: true });
  window.App?.setAppTitle?.();
  window.App?.setThreadQuestion?.("");
  const enterHero = () => { document.body.classList.add("is-hero"); window.syncHeroResponseAccess?.(); };
  if (window.App?.glideComposer) window.App.glideComposer(enterHero);
  else enterHero();
}
function deleteBookmarkWithUndo(bookmarkId) {
  if (!auth.currentUser || !bookmarkId || undoableBookmarkDeletes.has(bookmarkId)) return;
  if (!window.App?.undoNotice?.show) { deleteBookmark(bookmarkId); return; }
  const rows = [...document.querySelectorAll(`#bookmarksContainer .bookmark[data-id="${bookmarkId}"]`)];
  const wasOpen = activeBookmarkId() === bookmarkId;
  const entry = { promise: null };
  undoableBookmarkDeletes.set(bookmarkId, entry);
  rows.forEach(collapseBookmarkRow);
  if (wasOpen) leaveDeletedChat();
  window.filterBookmarks?.(document.getElementById("chatSearch")?.value || "");
  entry.notice = window.App.undoNotice.show({
    text: "Chat deleted",
    actionLabel: "Undo",
    duration: BOOKMARK_UNDO_MS,
    onAction() {
      undoableBookmarkDeletes.delete(bookmarkId);
      document.querySelectorAll(`#bookmarksContainer .bookmark[data-id="${bookmarkId}"]`).forEach(expandBookmarkRow);
      window.filterBookmarks?.(document.getElementById("chatSearch")?.value || "");
      if (wasOpen && !window.App.runRegistry?.visible?.() && document.body.classList.contains("is-hero")) window.openBookmark(bookmarkId);
    },
    onExpire() {
      undoableBookmarkDeletes.delete(bookmarkId);
      entry.promise = deleteBookmark(bookmarkId);
    },
  });
}
// Settles every deletion still waiting for its Undo; resolves once each was sent.
function settleUndoableBookmarkDeletes() {
  const entries = [...undoableBookmarkDeletes.values()];
  entries.forEach(entry => entry.notice?.settle());
  return Promise.allSettled(entries.map(entry => entry.promise).filter(Boolean));
}
window.addEventListener("consensio:run-registry-change", event => {
  if (event.detail?.type === "created" && undoableBookmarkDeletes.size) settleUndoableBookmarkDeletes();
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden && undoableBookmarkDeletes.size) settleUndoableBookmarkDeletes();
});

function ensurePendingBookmarkDOM(pending) {
  const container = document.getElementById("bookmarksContainer");
  if (!container || !pending?.id) return;
  let row = document.querySelector(`.bookmark[data-id="${pending.id}"]`);
  if (!row) {
    row = document.createElement("div");
    row.className = "bookmark";
    row.dataset.id = pending.id;
    container.prepend(row);
  }

  row.className = "bookmark is-pending";
  row.setAttribute("role", "status");
  row.setAttribute("aria-live", "polite");
  row.setAttribute("aria-disabled", "true");
  row.setAttribute(
    "aria-label",
    `Saving the chat ${pending.question || "for this question"}. It opens once the answer is ready.`
  );
  row.title = "This chat is being saved and opens once the answer is ready.";
  row.replaceChildren();

  const label = document.createElement("p");
  label.textContent = bookmarkLabelText(pending.question || "New chat");

  const spinner = document.createElement("span");
  spinner.className = "bookmark-pending-spinner";
  spinner.setAttribute("aria-hidden", "true");

  row.append(label, spinner);
}

function replacePendingBookmarkWithReady(bookmark, runId = null) {
  if (!bookmark?.id) return;
  const row = runId
    ? document.querySelector(`.bookmark.run-entry[data-run-id="${runId}"]`)
    : document.querySelector(`.bookmark[data-id="${bookmark.id}"]`);
  if (row?.classList.contains("run-entry")) { settleRunRow(row, bookmark, runId); return; }
  const readyRow = createReadyBookmarkRow(bookmark, runId);
  if (row) row.replaceWith(readyRow);
  else {
    document.getElementById("bookmarksContainer")?.prepend(readyRow);
    insertBookmarkRowSoftly(readyRow);
  }
}

// A finished run's row becomes the saved row in place: same node, same
// height, its title kept; the status words fade and the title takes their
// room in one glide (layout.css). Replacing it moved the list by 2 px and
// switched colour and length in one frame (Apple audit C7, A11).
function settleRunRow(row, bookmark, runId) {
  const hadFocus = row === document.activeElement;
  row.classList.remove("run-entry", "is-pending", ...[...row.classList].filter(name => name.startsWith("run-status-")));
  ["role", "tabindex", "aria-label", "title"].forEach(name => row.removeAttribute(name));
  row.dataset.id = bookmark.id;
  if (runId) row.dataset.runId = runId;
  let label = row.querySelector(":scope > p");
  if (!label) { label = document.createElement("p"); row.prepend(label); }
  const title = bookmarkLabelText(bookmarkDisplayTitle(bookmark));
  if (label.textContent !== title) label.textContent = title;
  setBookmarkTitleControl(label);
  const status = row.querySelector(":scope > .run-entry-status");
  if (status) {
    const quiet = !status.animate || matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (quiet) status.remove();
    else status.animate([{ opacity: 1 }, { opacity: 0 }], { duration: window.App?.motion?.ms?.("state") ?? 200, easing: window.App?.motion?.ease?.("out") ?? "ease-out", fill: "forwards" })
      .finished.catch(() => {}).then(() => status.remove());
  }
  if (!row.querySelector(":scope > .bookmark-menu-button")) row.append(createBookmarkMenuButton(title));
  if (undoableBookmarkDeletes.has(bookmark.id)) row.classList.add("is-undo-pending");
  syncActiveBookmark();
  if (hadFocus) label.focus({ preventScroll: true });
}

function addBookmarkToDOM(bookmark, { prepend = true } = {}) {
  const container = document.getElementById("bookmarksContainer");
  if (!container) return;

  // Prüfen, ob das Bookmark schon existiert (Update-Fall), um Duplikate zu vermeiden.
  // Ein Pending-Eintrag bleibt dabei absichtlich gesperrt.
  const existing = document.querySelector(`.bookmark[data-id="${bookmark.id}"]`);
  if (existing) return;

  const div = createReadyBookmarkRow(bookmark);

  if (prepend) container.prepend(div);
  else container.appendChild(div);

  // A chat saved while the list is open opens its place softly; the first
  // page of a list load has its own fade (revealLoadedBookmarks).
  if (prepend) insertBookmarkRowSoftly(div);
}

function finalizeRegistryRunBookmark(context) {
  if (!context || context.status !== "succeeded") return false;
  if (context.bookmark?.uiReady) return true;
  if (context.persistence?.pendingWrites > 0) return false;
  const meta = context.bookmark?.latestMeta;
  if (!meta?.id) return false;
  // Agent-mode success is only a complete bookmark once the authoritative
  // consensus snapshot has returned. Direct comparisons intentionally have
  // no consensus and become ready after their model writes drain.
  if (context.config?.agentMode !== false && !context.persistence?.consensusWrite) return false;
  window.App.runRegistry?.update?.(context.runId, current => {
    current.bookmark.uiReady = true;
    current.bookmark.status = "ready";
    current.persistence.status = "saved";
  }, { render: false, eventType: "persistence" });
  replacePendingBookmarkWithReady(meta, context.runId);
  return true;
}

window.App.bookmarkUi = Object.freeze({
  finalizeRun: finalizeRegistryRunBookmark,
  replacePendingBookmarkWithReady,
  insertSoftly: insertBookmarkRowSoftly,
  versionForParts: bookmarkShareVersion,
  versionParts: bookmarkShareVersionParts,
  invalidate(bookmarkId) {
    bookmarkDetailCache.delete(String(bookmarkId || ""));
    bookmarkViewCache.delete(String(bookmarkId || ""));
  },
  canWrite(bookmarkId, uid = auth.currentUser?.uid) {
    return bookmarkWriteAllowed(uid, bookmarkId);
  }
});
