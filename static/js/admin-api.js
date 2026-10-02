export function adminErrorMessage(data, status) {
  // main wraps HTTPException.detail in `error`; bare FastAPI uses `detail`.
  // Only display known string fields. Validation arrays/unknown objects may
  // contain submitted values and must never be stringified into the UI.
  for (const value of [data?.error, data?.detail]) {
    if (typeof value === "string" && value.trim()) return value;
    if (value && !Array.isArray(value) && typeof value === "object") {
      for (const field of [value.message, value.error]) {
        if (typeof field === "string" && field.trim()) return field;
      }
    }
  }
  return `HTTP ${status}`;
}

export function createAdminClient(auth) {
  return async function adminRequest(method, path, body) {
    const user = auth.currentUser;
    if (!user) throw new Error("Not logged in");
    const idToken = await user.getIdToken();
    const response = await fetch(path, {
      method,
      headers: {
        "Authorization": `Bearer ${idToken}`,
        "Content-Type": "application/json"
      },
      body: body ? JSON.stringify(body) : undefined
    });
    let data = {};
    try { data = await response.json(); } catch (_) { /* empty */ }
    if (!response.ok) {
      throw new Error(adminErrorMessage(data, response.status));
    }
    return data;
  };
}

