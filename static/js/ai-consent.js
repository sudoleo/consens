// =====================================================================
// ai-consent.js
// App.aiConsent: before an account's first question goes to the AI
// providers, it agrees once (app/services/ai_consent.py; App Store
// guideline 5.1.2(i), and the web asks the same).
//
//   set(uid, given)   firebase.js after /user_status (its ai_consent)
//   clear()           on sign-out
//   ensure()          window.sendQuestion awaits it before Agent or Compare:
//                     true = send; false = "Not now" (the draft stays)
//   refused(fields)   a refusal with code ai_consent_required (agent-chat.js
//                     failRun, query-send.js finishFailed): the next Send asks
//
// Not known yet (no status, or a status without the field) asks nothing:
// the server is the gate; its refusal makes the next Send ask.
// Loaded in the "auth" group after confirm-dialog.js; used at runtime only.
// =====================================================================
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const REQUIRED = "ai_consent_required";
  let account = { uid: "", given: null };
  let asking = null;

  function t(text, params) {
    return App.t ? App.t(text, params) : text;
  }

  function currentUid() {
    return window.auth?.currentUser?.uid || "";
  }

  function set(uid, given) {
    account = { uid: String(uid || ""), given: typeof given === "boolean" ? given : null };
  }

  function clear() {
    account = { uid: "", given: null };
  }

  function needed() {
    return account.given === false && account.uid !== "" && account.uid === currentUid();
  }

  // The companies behind the registry's model families (window.MODEL_FAMILIES,
  // config.get_model_families): the dialog names what actually runs.
  function providers() {
    const families = Array.isArray(window.MODEL_FAMILIES) ? window.MODEL_FAMILIES : [];
    return families.map(family => family.citationLabel || family.label).filter(Boolean).join(", ");
  }

  async function record() {
    const user = window.auth?.currentUser;
    if (!user) return false;
    try {
      const token = await user.getIdToken();
      const response = await fetch("/api/my/ai-consent", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.ok;
    } catch (_) {
      return false;
    }
  }

  async function ask() {
    const uid = account.uid;
    const agreed = await App.confirm({
      title: t("Before your first question"),
      body: `${t("consens sends your question, your files, the chat so far and, if it is on, your memory through OpenRouter to AI models from these companies, which answer and check the work:")}\n${providers()}\n\n${t("Please don’t enter anything confidential.")}`,
      confirmLabel: t("Agree"),
      cancelLabel: t("Not now"),
      link: { href: "/privacy#providers", label: t("How your data is handled") },
    });
    if (!agreed) return false;
    if (!(await record())) {
      App.toast?.({ message: t("Your consent could not be saved. Try again."), tone: "error" });
      return false;
    }
    if (account.uid === uid) account.given = true;
    return true;
  }

  function ensure() {
    if (!needed() || !App.confirm) return Promise.resolve(true);
    // A second Send while the question is open waits for the same answer.
    asking = asking || ask().finally(() => { asking = null; });
    return asking;
  }

  function refused(fields) {
    const code = String(fields?.code || fields?.error_code || "");
    if (code !== REQUIRED) return false;
    const uid = currentUid();
    if (uid) account = { uid, given: false };
    return true;
  }

  App.aiConsent = { set, clear, needed, ensure, refused, providers };
})();
