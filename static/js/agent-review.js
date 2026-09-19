// Agent evidence uses the same reader, formatted answers and markers as Consensus.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const states = { required: "Review pending", running: "Checking the answer…", succeeded: "Comparison checked",
    partial: "Review incomplete", failed: "Review unavailable", cancelled: "Review stopped", missing: "Answer not reviewed" };
  function checkIssues(comparison, check) {
    if (!check) return [];
    let issues = check.issues;
    if (!Array.isArray(issues)) {
      // Older saved turns already contain judge coverage, but no issue list.
      issues = [];
      if (comparison.failed_models?.length) issues.push({code: 'models_unavailable', count: comparison.failed_models.length});
      const data = check.differences_data;
      if (data?.judges) {
        if (!data.judges.differences) issues.push({code: 'differences_unavailable'});
        if (!data.judges.coverage) issues.push({code: 'coverage_unavailable'});
        else if (data.judges.coverage.missing) issues.push({code: 'sentences_unchecked', count: data.judges.coverage.missing});
        for (const code of ['unindexed_sentences', 'truncated_answers']) {
          if (data.evidence_coverage?.[code]) issues.push({code, count: data.evidence_coverage[code]});
        }
      } else if (check.status === 'partial') issues.push({code: 'incomplete'});
    }
    issues = [...issues];
    const sources = check.source_verification;
    if (sources?.answer_version === check.answer_hash && sources.run_id === comparison.id
        && sources.basis_hash === comparison.basis_hash && ['partial', 'failed'].includes(sources.status)) {
      issues.push({code: 'sources_incomplete'});
    }
    return issues;
  }
  function issueText(issue) {
    const n = issue.count;
    return ({models_unavailable: `${n} comparison model${n === 1 ? '' : 's'} unavailable`,
      insufficient_answers: 'Fewer than two complete model answers are available',
      differences_unavailable: 'The differences check did not complete',
      coverage_unavailable: 'The coverage check did not complete',
      sentences_unchecked: `${n} sentence${n === 1 ? '' : 's'} could not be checked`,
      unindexed_sentences: `${n} sentence${n === 1 ? '' : 's'} fell outside the coverage check`,
      truncated_answers: 'Some model answers exceeded the review context',
      sources_incomplete: 'Some contradiction source checks did not complete',
      incomplete: 'The saved review is incomplete'})[issue.code] || 'The review is incomplete';
  }
  function statusText(state, issues) {
    if (!['succeeded', 'partial'].includes(state)) return states[state] || 'Review incomplete';
    if (issues.length && issues.every(i => i.code === 'models_unavailable')) {
      const n = issues.reduce((total, i) => total + i.count, 0);
      return `Comparison checked · ${n} model${n === 1 ? '' : 's'} unavailable`;
    }
    return issues.length ? 'Review incomplete' : states[state];
  }
  function node(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function safeSources(answers) {
    const sources = new Map();
    for (const answer of answers || []) {
      const citations = [...(answer.sources || [])];
      if (answer.text && window.marked?.parse && window.DOMPurify) {
        const template = document.createElement('template');
        template.innerHTML = window.DOMPurify.sanitize(window.marked.parse(answer.text));
        for (const link of template.content.querySelectorAll('a[href]')) {
          if (link.closest('code, pre') || link.querySelector('img, svg')) continue;
          const preceding = link.previousSibling?.textContent || '';
          const title = /^https?:\/\//i.test(link.textContent)
            ? preceding.match(/(?:^|[.,;:\n])\s*([^()[\]\n,;:]{1,100}?)\s*\($/)?.[1]?.trim() || link.textContent
            : link.textContent;
          citations.push({ url: link.getAttribute('href'), title });
        }
      }
      for (const source of citations) {
        try {
          const url = new URL(source.url);
          if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) continue;
          url.hash = '';
          if (!sources.has(url.href)) sources.set(url.href, { ...source, url: url.href, title: source.title || url.hostname });
        } catch (_) { /* Invalid citation. */ }
      }
    }
    return [...sources.values()];
  }
  function sourcePanel(sources) {
    const panel = node('div', 'agent-evidence-panel');
    const list = node('ol', 'answer-reader-sources');
    for (const source of sources) {
      const li = node('li'); const link = node('a', '', source.title);
      link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; li.append(link); list.append(li);
    }
    panel.append(sources.length ? list : node('p', 'agent-review-note', 'No source URLs were supplied for this answer.'));
    return panel;
  }
  function render(body, review, evidence = {}) {
    if (!body?.parentElement) return;
    const version = review?.versions?.find(v => v.id === review.answer_version);
    const raw = body.dataset.markdown ?? version?.text;
    const turnSources = safeSources([evidence, ...(evidence.events || []), {text: raw}, { sources: [...body.querySelectorAll('a[href]')]
      .filter(a => !a.closest('code, pre') && !a.querySelector('img, svg'))
      .map(a => a.sourceData || {url: a.getAttribute('href'), title: a.textContent}) },
      ...(review?.comparisons || []).flatMap(c => c.answers || []), ...(review?.versions || [])]);
    let host = body._agentReview;
    if (!review?.comparisons?.length) {
      if (host?._hasReview && typeof body.dataset.markdown === "string") window.injectMarkdown?.(body, body.dataset.markdown, []);
      window.linkifyAgentSources?.(body, turnSources);
      body._agentModels?.remove(); body._agentModels = null;
      if (!turnSources.length) { host?.remove(); body._agentReview = null; return; }
      if (!host?.isConnected) { host = node('section', 'agent-review'); body.after(host); body._agentReview = host; }
      const signature = JSON.stringify([evidence.key, evidence.question, turnSources]);
      if (host.dataset.signature === signature) return;
      host.dataset.signature = signature; host._hasReview = false; host.hidden = false;
      const context = { key: `agent-sources:${evidence.key || body.id || evidence.question}`, question: evidence.question || 'Answer sources',
        answers: [], sections: ['sources'], renderPanel: () => sourcePanel(turnSources) };
      const nav = node('nav', 'consensus-footer-tabs agent-evidence-links');
      const button = node('button', 'consensus-tab agent-evidence-link', `Sources ${turnSources.length}`);
      button.type = 'button'; button.dataset.section = 'sources';
      button.addEventListener('click', () => App.answerReader?.openContext(context, {section: 'sources', trigger: button}));
      nav.append(button); host.replaceChildren(nav); App.answerReader?.refreshContext(context); return;
    }
    if (!host?.isConnected) {
      host = node("section", "agent-review"); body.after(host); body._agentReview = host;
      host.setAttribute("aria-label", "Answer evidence");
    }
    const exact = !!version && raw === version.text && version.hash === review.answer_hash;
    const boundCheck = comparison => {
      const check = review.checks?.find(c => c.comparison_id === comparison.id);
      return exact && check?.answer_hash === version.hash && check?.basis_hash === comparison.basis_hash ? check : null;
    };
    const signature = JSON.stringify([review, raw, exact, turnSources]);
    if (host.dataset.signature === signature) { window.linkifyAgentSources?.(body, turnSources); return; }
    host.dataset.signature = signature;
    host._hasReview = true;
    host.replaceChildren();
    const issues = review.comparisons.flatMap(c => checkIssues(c, boundCheck(c)));
    const state = ['succeeded', 'partial'].includes(review.status) && !review.comparisons.every(boundCheck) ? 'required'
      : review.status === 'succeeded' && issues.length ? 'partial' : review.status;
    host.hidden = !version && ["required", "running"].includes(state);
    const summary = node("div", "agent-review-summary");
    const status = node("span", "agent-review-status", statusText(state, issues));
    status.setAttribute("role", "status"); status.dataset.state = state;
    status.title = [...issues.map(issueText), "Model agreement compares perspectives; it is not independent fact checking."].join('. ');
    summary.append(status); host.append(summary);
    const tabs = node("nav", "consensus-footer-tabs agent-evidence-links");
    tabs.setAttribute("aria-label", "Explore answer evidence"); host.append(tabs);
    const fallback = node("div", "consensus-claims-fallback"); fallback.hidden = true; host.append(fallback);
    let contexts;
    contexts = review.comparisons.map(comparison => {
      const check = boundCheck(comparison);
      const answers = comparison.answers || [];
      const sources = turnSources;
      const findAnswer = name => answers.find(a => [a.provider, a.provider_label, a.model?.label].some(v => v?.toLowerCase() === name?.toLowerCase()));
      const context = { key: `agent-evidence:${comparison.id}`, question: comparison.question, scopeLabel: "Comparison focus",
        contextLabel: comparison.question.length > 64 ? comparison.question.slice(0, 61) + "…" : comparison.question,
        contextGroup: () => contexts,
        answers: [
          ...answers.map(a => ({ provider: a.provider_label || a.provider, model: a.model?.model, label: a.model?.label || a.provider,
            text: a.text, sources: safeSources([a]), sourceReferences: 'agent', status: "complete" })),
          ...(comparison.failed_models || []).map((m, i) => ({ provider: `unavailable-${i}`, model: m.model, label: m.label,
            text: "", status: comparison.status === "cancelled" ? "canceled" : "error", error: m.failure?.error || "This model did not return a complete answer.", sources: [] }))
        ] };
      const open = (section, options = {}) => App.answerReader?.openContext(context, { section, ...options });
      const navigation = {
        canOpen: name => !!findAnswer(name),
        open: (name, quote, trigger) => open("answers", { model: findAnswer(name)?.provider_label || findAnswer(name)?.provider, quote, trigger })
      };
      context.renderPanel = kind => {
        const panel = node("div", "agent-evidence-panel");
        if (kind === "sources") {
          return sourcePanel(sources);
        }
        const localIssues = checkIssues(comparison, check);
        panel.append(node("p", "agent-evidence-status", statusText(check?.status || state, localIssues)));
        if (check) {
          const unavailable = comparison.failed_models || [];
          panel.append(node('p', 'agent-review-note', `${answers.length} of ${answers.length + unavailable.length} models returned complete answers.`));
          for (const model of unavailable) panel.append(node('p', 'agent-review-note', `${model.label}: ${model.failure?.error || 'No complete answer was returned.'}`));
          for (const issue of localIssues.filter(i => i.code !== 'models_unavailable')) panel.append(node('p', 'agent-review-note', issueText(issue) + '.'));
          if (localIssues.length && localIssues.every(i => i.code === 'models_unavailable')) {
            panel.append(node('p', 'agent-review-note', 'The differences and coverage checks completed for the available model answers.'));
          }
        }
        if (!check || !check.differences_data) {
          panel.append(node("p", "agent-review-note", exact ? "The answer has no completed check for this comparison yet."
            : "The text changed. This version needs a new review."));
        } else {
          const cards = node("div", "agent-evidence-differences");
          window.renderStoredDifferenceCards?.(cards, check.differences_data, {
            modelLabel: name => findAnswer(name)?.model?.label || name, answerNavigation: navigation
          });
          panel.append(cards);
          const verification = check.source_verification;
          if (verification?.answer_version === review.answer_hash && verification.run_id === comparison.id
              && verification.basis_hash === comparison.basis_hash) {
            const report = node('div', 'agent-source-check');
            panel.insertBefore(report, cards);
            App.sourceVerification?.render(cards, report, verification, {
              differencesData: check.differences_data, differenceCards: cards
            });
          } else if (typeof review.check_sources === 'boolean') {
            panel.append(node('p', 'agent-review-note', !review.check_sources ? 'Contradiction source checks were off for this message.'
              : ['failed', 'cancelled', 'missing'].includes(state) ? 'Contradiction source checks did not complete.'
              : 'Contradiction source checks pending.'));
          }
        }
        panel.append(node("p", "agent-review-note", "Model agreement is not independent fact checking."));
        const basis = node("details", "agent-evidence-context");
        basis.append(node("summary", "", "Comparison context"));
        if (comparison.reason) basis.append(node("p", "", comparison.reason));
        if (comparison.context) basis.append(node("p", "", comparison.context));
        panel.append(basis);
        if ((review.versions || []).length > 1) {
          const history = node("details", "agent-evidence-context"); history.append(node("summary", "", "Earlier answer version"));
          for (const prior of review.versions.slice(0, -1)) {
            history.append(node("p", "agent-review-note", `Version ${prior.id} · ${states[prior.status] || "Not reviewed"}`));
            const text = node("div", "consensus-answer-body"); window.injectMarkdown?.(text, prior.text, []); history.append(text);
            window.linkifyAgentSources?.(text, safeSources([{sources}, {text: prior.text}]));
          }
          panel.append(history);
        }
        return panel;
      };
      context.mark = () => {
        fallback.replaceChildren(); fallback.hidden = true;
        if (typeof raw === "string") window.injectMarkdown?.(body, raw, []);
        if (check?.differences_data) window.renderStoredConsensusClaims?.(body, check.differences_data, fallback, sources, {
          answerNavigation: navigation,
          focusDifference: differenceIndex => open("differences", { index: differenceIndex, trigger: document.activeElement })
        });
        window.linkifyAgentSources?.(body, sources);
      };
      context.links = () => {
        const differences = check?.differences_data?.differences || [];
        const contradictions = differences.filter(d => d.type === "contradiction").length;
        return [["differences", contradictions ? "Contradictions" : differences.length ? "Differences" : "Review", contradictions || differences.length || null],
          ["answers", "Answers", answers.length], ["sources", "Sources", sources.length]];
      };
      return context;
    });
    let chosen = contexts.find(c => c.key === host._selectedBasis) || contexts[0];
    function select(context) {
      chosen = context; host._selectedBasis = context.key;
      context.mark(); tabs.replaceChildren();
      for (const [section, label, count] of context.links()) {
        const button = node("button", "consensus-tab agent-evidence-link"); button.type = "button";
        button.dataset.section = section; button.setAttribute("aria-controls", "modelAnswerReader");
        button.append(node("span", "consensus-tab-label", label));
        if (count !== null) button.append(node("span", "consensus-tab-count", String(count)));
        button.addEventListener("click", () => App.answerReader?.openContext(context, { section, trigger: button }));
        tabs.append(button);
      }
    }
    if (contexts.length > 1) {
      const label = node("label", "agent-evidence-focus"); label.append(node("span", "", "Evidence for"));
      const picker = node("select"); picker.setAttribute("aria-label", "Comparison basis");
      for (const context of contexts) picker.append(new Option(context.contextLabel, context.key));
      picker.value = chosen.key; picker.addEventListener("change", () => select(contexts.find(c => c.key === picker.value)));
      label.append(picker); summary.append(label);
    }
    select(chosen);
    if (body.classList.contains('thread-history-answer-body')) {
      body._agentModels?.remove();
      const models = node('div', 'agent-inline-models agent-history-models');
      const stack = node('span', 'agent-model-stack'); models.append(stack);
      const seen = new Set();
      for (const context of contexts) for (const answer of context.answers) {
        const key = answer.model || answer.label;
        if (seen.has(key)) continue;
        seen.add(key);
        const button = node('button', 'agent-inline-model'); button.type = 'button';
        button.title = answer.label; button.setAttribute('aria-label', `Read ${answer.label}`);
        button.append(App.createModelMark?.(answer) || node('span', 'model-mark-fallback', answer.label.slice(0, 1)));
        button.addEventListener('click', () => App.answerReader?.openContext(context, { model: answer.provider, trigger: button }));
        stack.append(button);
      }
      body.before(models); body._agentModels = models;
    }
    contexts.forEach(c => App.answerReader?.refreshContext(c));
  }
  App.agentReview = { render };
})();
