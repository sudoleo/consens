/* Topic page: the follow form. Everything else the page does is shared with
 * Watch pages (static/js/check-page.js).
 *
 * An external file because /topics/{slug} runs under a script CSP without
 * 'unsafe-inline' (app/core/security.py). Server messages are only ever
 * inserted as text.
 */
(function () {
  "use strict";

  function followForm() {
    var form = document.getElementById("topicFollowForm");
    var status = document.getElementById("topicFollowStatus");
    if (!form || !status) return;
    var button = form.querySelector("button");
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      button.disabled = true;
      status.classList.remove("is-error");
      status.textContent = "Sending confirmation…";
      status.hidden = false;
      fetch("/api/topics/" + encodeURIComponent(form.dataset.slug) + "/follow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.querySelector("input[type=email]").value.trim() })
      }).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          if (!response.ok) throw new Error(data.error || data.detail || "Could not follow this Topic.");
          status.textContent = data.message || "Check your inbox and confirm to start following.";
          form.hidden = true;
        });
      }).catch(function (error) {
        status.textContent = error.message;
        status.classList.add("is-error");
      }).then(function () {
        button.disabled = false;
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", followForm);
  } else {
    followForm();
  }
})();
