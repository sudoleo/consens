(function () {
  window.App = window.App || {};
  const values = {
    telegram: null,
    limits: null,
    // The account's watches as /api/my/watches listed them with the limits
    // (null until loaded): what an Agent Watch card compares its question to.
    watches: null,
    limitRequest: null,
    sessionEpoch: 0,
    authUid: window.__consensioAuthState?.uid || null
  };
  const state = Object.freeze({
    get telegram() { return values.telegram; },
    get limits() { return values.limits; },
    get watches() { return values.watches; },
    get limitRequest() { return values.limitRequest; },
    get sessionEpoch() { return values.sessionEpoch; },
    get authUid() { return values.authUid; },
    setTelegram(value) {
      values.telegram = value;
      return value;
    },
    setLimits(value) {
      values.limits = value;
      return value;
    },
    setWatches(value) {
      values.watches = value;
      return value;
    },
    setLimitRequest(value) {
      values.limitRequest = value;
      return value;
    },
    resetSession() {
      values.sessionEpoch += 1;
      values.telegram = null;
      values.limits = null;
      values.watches = null;
      values.limitRequest = null;
    },
    updateAuthUid(uid) {
      const changed = uid !== values.authUid;
      values.authUid = uid;
      return changed;
    }
  });
  window.App.watchState = state;
})();
