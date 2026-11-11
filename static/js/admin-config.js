(function () {
  const config = document.getElementById("adminBootstrapConfig");
  window.FIREBASE_CONFIG = {
    apiKey: config?.dataset.firebaseApiKey || "",
    authDomain: config?.dataset.firebaseAuthDomain || "",
    projectId: config?.dataset.firebaseProjectId || "",
    storageBucket: config?.dataset.firebaseStorageBucket || "",
    messagingSenderId: config?.dataset.firebaseMessagingSenderId || "",
    appId: config?.dataset.firebaseAppId || ""
  };
  // The app's theme before first paint: its saved choice, else the system's.
  // Blocked storage keeps the dark default the admin pages had.
  try {
    const saved = window.localStorage.getItem("theme");
    const prefersDark = !window.matchMedia || window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (saved === "dark" || (saved !== "light" && prefersDark)) {
      document.documentElement.classList.add("dark-mode");
    }
  } catch (error) {
    document.documentElement.classList.add("dark-mode");
  }
})();
