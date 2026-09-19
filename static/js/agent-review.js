// Exact answer versions and per-comparison marker projection, live and saved.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const labels = { required: "Review required", running: "Reviewing answer", succeeded: "Review complete",
    partial: "Partial review", failed: "Review failed", cancelled: "Review stopped", missing: "Required review missing" };
  function node(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function render(body, review) {
    if (!body?.parentElement) return;
    let host = body._agentReview;
    if (!review?.comparisons?.length) {
      if (host && typeof body.dataset.markdown === "string") window.injectMarkdown?.(body, body.dataset.markdown, []);
      host?.remove(); body._agentReview = null; return;
    }
    if (!host?.isConnected) {
      host = node("section", "agent-review"); body.after(host); body._agentReview = host;
      host.setAttribute("aria-label", "Comparison and answer review");
    }
    const version = review.versions?.find(v => v.id === review.answer_version);
    const raw = body.dataset.markdown ?? version?.text;
    const exact = !!version && raw === version.text && version.hash === review.answer_hash;
    const boundCheck = comparison => {
      const check = review.checks?.find(c => c.comparison_id === comparison.id);
      return exact && check?.answer_hash === version.hash && check?.basis_hash === comparison.basis_hash ? check : null;
    };
    const signature = JSON.stringify([review, exact]);
    if (host.dataset.signature === signature) return;
    host.dataset.signature = signature;
    host.replaceChildren();
    const state = review.status === "succeeded" && !review.comparisons.every(boundCheck) ? "required" : review.status;
    const status = node("div", "agent-review-status", `${labels[state] || "Review incomplete"}${version ? ` · Version ${version.id}` : ""}`);
    status.setAttribute("role", "status");
    host.append(status, node("p", "agent-review-note", "These checks compare model answers. Model agreement is not independent fact checking."));
    if (version && !exact) host.append(node("p", "agent-review-note", "The text changed. This version needs a new review."));
    const buttons = node("div", "agent-review-bases");
    host.append(buttons);
    const fallback = node("div", "consensus-claims-fallback"); fallback.hidden = true;
    const differences = node("div", "agent-review-differences");
    host.append(fallback, differences);
    function mark(comparison, button) {
      for (const b of buttons.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === button));
      const check = boundCheck(comparison);
      differences.replaceChildren(); fallback.replaceChildren();
      // Always remove the previous basis, including stale/incomplete results.
      if (typeof raw === "string") window.injectMarkdown?.(body, raw, []);
      if (!check) return;
      if (!check.differences_data) {
        differences.append(node("p", "agent-review-note", "No completed judge result for this comparison.")); return;
      }
      const findAnswer = name => comparison.answers?.find(a => a.provider === name.toLowerCase() || a.provider_label === name || a.model?.label === name);
      const label = name => findAnswer(name)?.model?.label || name;
      window.renderStoredConsensusClaims?.(body, check.differences_data, fallback, [], { answerNavigation: {
        canOpen: name => !!findAnswer(name),
        open(name) {
          const answer = findAnswer(name);
          const section = [...host.querySelectorAll(".agent-comparison-response")].find(el => el._answer === answer);
          if (!section) return;
          section.parentElement.open = true; section.open = true;
          section.scrollIntoView?.({ block: "center", behavior: "smooth" });
          section.querySelector("summary").focus();
        }
      } });
      window.renderStoredDifferenceCards?.(differences, check.differences_data, { modelLabel: label });
    }
    review.comparisons.forEach((comparison, index) => {
      const check = boundCheck(comparison);
      const button = node("button", "agent-basis-select", `Comparison ${index + 1} · ${labels[check?.status] || labels[state] || "Review incomplete"}`);
      button.type = "button"; button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => mark(comparison, button)); buttons.append(button);
      const details = node("details", "agent-comparison");
      details.append(node("summary", "", comparison.question));
      details.append(node("p", "agent-review-note", comparison.reason));
      if (comparison.context) details.append(node("p", "agent-review-note", comparison.context));
      for (const answer of comparison.answers || []) {
        const response = node("details", "agent-comparison-response");
        response._answer = answer;
        response.append(node("summary", "", answer.model?.label || answer.provider));
        response.append(node("div", "agent-comparison-answer", answer.text));
        for (const source of answer.sources || []) {
          try {
            const url = new URL(source.url);
            if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) continue;
            const link = node("a", "agent-source", source.title || url.hostname);
            link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; response.append(link);
          } catch (_) { /* Invalid citation. */ }
        }
        details.append(response);
      }
      for (const model of comparison.failed_models || []) details.append(node("p", "agent-review-note", `${model.label}: no completed answer`));
      host.append(details);
      if (!index) mark(comparison, button);
    });
    if ((review.versions || []).length > 1) {
      const history = node("details", "agent-review-versions"); history.append(node("summary", "", "Earlier answer version"));
      for (const prior of review.versions.slice(0, -1)) {
        history.append(node("p", "agent-review-note", `Version ${prior.id} · ${labels[prior.status] || prior.status}`),
          node("div", "agent-comparison-answer", prior.text));
      }
      host.append(history);
    }
  }
  App.agentReview = { render };
})();
