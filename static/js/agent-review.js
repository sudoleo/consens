// Agent evidence uses the same reader, formatted answers and markers as Consensus.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  const states = { required: "Review pending", running: "Checking the answer…", succeeded: "Comparison checked",
    partial: "Partly checked", failed: "Check could not run", cancelled: "Check stopped", missing: "Answer not checked" };
  // Short, calm reasons for one model call that ended without a result. The
  // provider's own error text never reaches the page (see provider_failure).
  const reasons = { provider_rate_limited: 'the provider was busy', provider_timeout: 'the provider stopped responding',
    provider_unavailable: 'the model was unavailable at its provider', provider_access: 'the provider declined the request',
    output_limit: 'it used its whole output allowance before finishing',
    late_cutoff: 'it was still writing when the answer was checked', stopped: 'the run was stopped' };
  function failureReason(failure) {
    return reasons[failure?.code] || 'no complete answer arrived';
  }
  // The answer text is fixed and its review finished before the run ended.
  function reviewedAnswer(review, raw) {
    const version = review?.versions?.find(v => v.id === review.answer_version);
    return Boolean(version && typeof raw === 'string' && raw.trim() && raw === version.text
      && version.hash === review.answer_hash && ['succeeded', 'partial'].includes(review.status));
  }
  // The note under an answer whose run did not finish cleanly. A complete,
  // checked answer needs none: whatever failed afterwards changes nothing the
  // reader relies on. Otherwise one calm sentence, never a provider message.
  function failureNote(failure, review, raw) {
    const message = failure?.error || failure?.message || '';
    if (typeof raw !== 'string' || !raw.trim()) return message;
    if (reviewedAnswer(review, raw)) return '';
    return 'This answer may be incomplete because the run ended early. Everything received has been saved, and you can ask again at any time.';
  }
  const activityContexts = new WeakMap();
  // The live run renders evidence only once, from its final review object; an
  // activity card built from the streamed review finds its context by key.
  const contextsByKey = new Map();
  function currentCheck(review, comparison, raw) {
    const version = review?.versions?.find(v => v.id === review.answer_version);
    const check = review?.checks?.find(c => c.comparison_id === comparison.id);
    return version && raw === version.text && version.hash === review.answer_hash
      && check?.answer_hash === version.hash && check?.basis_hash === comparison.basis_hash ? check : null;
  }
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
    return ({models_unavailable: `${n} comparison model${n === 1 ? '' : 's'} returned no usable answer; the check uses the remaining answers`,
      insufficient_answers: 'Fewer than two complete model answers arrived, so no comparison was possible',
      differences_unavailable: 'The differences check could not run, so disagreements are not marked',
      coverage_unavailable: 'The coverage check could not run, so sentences are not marked as supported',
      sentences_unchecked: `${n} sentence${n === 1 ? '' : 's'} could not be checked`,
      unindexed_sentences: `${n} sentence${n === 1 ? '' : 's'} fell outside the coverage check`,
      truncated_answers: 'Some model answers were too long to check in full',
      sources_incomplete: 'Some contradiction source checks did not finish',
      incomplete: 'The saved check is incomplete'})[issue.code] || 'The check is incomplete';
  }
  function statusText(state, issues) {
    if (!['succeeded', 'partial'].includes(state)) return states[state] || states.partial;
    if (issues.length && issues.every(i => i.code === 'models_unavailable')) {
      const n = issues.reduce((total, i) => total + i.count, 0);
      return `Comparison checked · ${n} model${n === 1 ? '' : 's'} without an answer`;
    }
    return issues.length ? states.partial : states[state];
  }
  // The line under the answer speaks only when it changes how far the reader
  // can rely on the marks. A finished check, or one that simply had fewer
  // answers to work with, needs no words: the marks and counts say enough.
  const decisive = new Set(['insufficient_answers', 'differences_unavailable', 'coverage_unavailable']);
  function summaryText(state, issues) {
    if (!['succeeded', 'partial'].includes(state)) return states[state] || states.partial;
    const codes = new Set(issues.map(i => i.code).filter(code => decisive.has(code)));
    if (codes.has('insufficient_answers')) return 'Not compared · fewer than two models answered';
    if (codes.has('differences_unavailable')) return 'Disagreements not checked';
    return codes.size ? states.partial : '';
  }
  // The reader's status is one quiet line: how many models answered and how
  // far the check got. Missing models, late answers and minor gaps sit behind
  // it as a disclosure instead of five stacked sentences.
  function checkWord(state, issues) {
    if (!['succeeded', 'partial'].includes(state)) return states[state] || states.partial;
    if (!issues.length) return state === 'succeeded' ? 'Checked' : states.partial;
    return issues.every(i => i.code === 'models_unavailable') ? 'Checked' : states.partial;
  }
  function evidenceStatus(comparison, answers, check, state, issues) {
    const unavailable = check ? comparison.failed_models || [] : [];
    const total = answers.length + unavailable.length;
    const count = !check ? '' : unavailable.length ? `${answers.length} of ${total} models answered`
      : `${total} model${total === 1 ? '' : 's'} answered`;
    const line = [count, checkWord(check?.status || state, issues)].filter(Boolean).join(' · ');
    const details = [];
    for (const model of unavailable) details.push(model.partial_text
      ? `${model.label}: stopped before it finished, ${failureReason(model.failure)}. Its partial answer is under Answers, not in the check.`
      : `${model.label}: no answer, ${failureReason(model.failure)}.`);
    // Arrived after the answer was written: part of the check, not of the text.
    const late = check ? answers.filter(a => a.late).map(a => a.model?.label || a.provider_label || a.provider) : [];
    if (late.length) details.push(`${late.join(', ')} answered after the answer was written. ${late.length === 1 ? 'Its answer is' : 'Their answers are'} part of the check, not of the answer text.`);
    if (check) for (const issue of issues) {
      if (issue.code !== 'models_unavailable' && !decisive.has(issue.code)) details.push(issueText(issue) + '.');
    }
    if (!details.length) return node('p', 'agent-evidence-status', line);
    const box = node('details', 'agent-evidence-status');
    box.append(node('summary', '', line));
    const list = node('ul', 'agent-evidence-status-detail');
    for (const text of details) list.append(node('li', '', text));
    box.append(list);
    return box;
  }
  // Copy and evidence share one row: the actions bar lives inside the host.
  function keepActions(host, previous) {
    const sibling = [host.previousElementSibling, host.nextElementSibling]
      .find(el => el?.classList.contains('agent-answer-actions'));
    const bar = previous || sibling;
    if (bar) host.append(bar);
  }
  function node(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function renderActivity(host, review, raw) {
    const comparisons = review?.comparisons || [];
    host.hidden = !comparisons.length;
    const signature = JSON.stringify([review, raw]);
    if (host.dataset.signature === signature) return;
    host.dataset.signature = signature;
    host.replaceChildren();
    if (!comparisons.length) return;
    host.append(node('h3', '', 'Comparison details'));
    comparisons.forEach((comparison, index) => {
      const card = node('section', 'agent-activity-insight');
      const answers = comparison.answers || [], missing = comparison.failed_models || [];
      card.append(node('h4', '', `Comparison ${index + 1} · ${comparison.status === 'running' ? 'Collecting answers…'
        : `${answers.length} model ${answers.length === 1 ? 'answer' : 'answers'}`}`));
      if (comparison.question) card.append(node('p', 'agent-activity-focus', comparison.question));
      if (comparison.reason) card.append(node('p', '', comparison.reason));
      const names = answers.map(a => a.model?.label || a.provider_label || a.provider).filter(Boolean);
      if (names.length) card.append(node('p', 'agent-activity-models', `Models: ${names.join(', ')}`));
      const unfinished = missing.filter(m => m.partial_text), silent = missing.filter(m => !m.partial_text);
      if (silent.length) card.append(node('p', '', `Did not respond: ${silent.map(m => m.label || m.model).join(', ')}`));
      if (unfinished.length) card.append(node('p', '', `Stopped before finishing: ${unfinished.map(m => m.label || m.model).join(', ')} (kept as incomplete)`));
      const pending = comparison.pending_models || [];
      if (pending.length) card.append(node('p', '', `Still answering: ${pending.map(m => m.label || m.model).join(', ')}`));
      const check = currentCheck(review, comparison, raw);
      const issues = checkIssues(comparison, check);
      const state = check?.status || (['running', 'failed', 'cancelled', 'missing'].includes(review.status) ? review.status : 'required');
      card.append(node('p', 'agent-activity-check', comparison.status === 'running' && !check
        ? 'Waiting for independent model answers.' : statusText(state, issues)));
      const differences = check?.differences_data?.differences || [];
      if (differences.length) {
        const list = node('ul', 'agent-activity-findings');
        for (const difference of differences.slice(0, 3)) {
          const text = difference.claim || difference.consensus_anchor;
          if (text) list.append(node('li', '', `${difference.type === 'contradiction' ? 'Disagreement' : 'Difference'}: ${text}`));
        }
        if (differences.length > 3) list.append(node('li', '', `${differences.length - 3} more in the detailed review.`));
        card.append(list);
      } else if (check?.status === 'succeeded' && Array.isArray(check.differences_data?.differences)) {
        card.append(node('p', '', 'The completed comparison check reported no differences.'));
      }
      for (const issue of issues) card.append(node('p', 'agent-activity-limitation', issueText(issue)));
      const verification = check?.source_verification;
      if (verification?.answer_version === check?.answer_hash && verification?.run_id === comparison.id
          && verification?.basis_hash === comparison.basis_hash) {
        const scope = verification.scope;
        if (Number.isInteger(scope?.checked_contradictions) && Number.isInteger(scope?.contradictions)) {
          card.append(node('p', '', `Source checks: ${scope.checked_contradictions} of ${scope.contradictions} disagreements checked.`));
        }
      } else if (review.check_sources === false) {
        card.append(node('p', '', 'Contradiction source checks were off for this message.'));
      }
      const actions = node('div', 'agent-activity-insight-actions');
      for (const [section, label] of [['answers', 'Read model answers'], ['differences', 'Explore review and sources']]) {
        const button = node('button', 'consensus-tab', label); button.type = 'button';
        button.disabled = section === 'answers' ? !answers.length : !check;
        button.addEventListener('click', () => {
          const key = `agent-evidence:${comparison.id}`;
          const context = activityContexts.get(review)?.find(c => c.key === key) || contextsByKey.get(key);
          if (context) App.answerReader?.openContext(context, { section, trigger: button });
        });
        actions.append(button);
      }
      card.append(actions); host.append(card);
    });
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
  function evidenceButton(section, label, count) {
    const button = node('button', 'consensus-tab agent-evidence-link');
    button.type = 'button';
    button.dataset.section = section;
    button.setAttribute('aria-controls', 'modelAnswerReader');
    button.setAttribute('aria-label', count === null ? label : `${label} ${count}`);
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.classList.add('agent-evidence-icon');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS(icon.namespaceURI, 'path');
    path.setAttribute('d', {
      differences: 'M12 20v-7M12 13 5 6M12 13l7-7M5 11V6h5M14 6h5v5',
      answers: 'M4 4h12v10H8l-4 4V4ZM16 8h4v12l-4-4h-4',
      sources: 'M14 3H5v18h14V8ZM14 3v5h5M8 12h8M8 16h6',
    }[section]);
    icon.append(path);
    button.append(icon, node('span', 'consensus-tab-label', label));
    if (count !== null) button.append(node('span', 'consensus-tab-count', String(count)));
    return button;
  }
  // The first time a live answer receives its marks they stroke on in reading
  // order, like a marker pen going over the text (the landing page's gesture).
  // Later re-renders of the same answer show them at once.
  const MARKS = '.cx-claim:is(.is-thin, .is-unanimous, .is-minor, .is-split, .is-major)';
  // A re-render during the reveal (a fresh DOM when the run ends) continues
  // the stroke where it was, through negative delays, instead of restarting.
  function revealMarks(body, hash) {
    // Marks hidden by the highlight setting (all markers off, or e.g. green
    // ones filtered out) neither animate nor take a place in the sequence.
    const visible = el => !el.classList.contains('is-marker-filtered');
    const marks = document.body.classList.contains('consensus-markers-hidden') ? []
      : [...body.querySelectorAll(MARKS)].filter(visible);
    if (!marks.length) return;
    const now = performance.now();
    if (body._revealedMarks !== hash) {
      body._revealedMarks = hash;
      body._revealStart = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? null : now;
    } else if (marks[0].style.getPropertyValue('--cx-reveal-delay')) {
      return; // Same spans, animation already running.
    }
    if (body._revealStart == null || now - body._revealStart > body._revealTotal) return;
    const elapsed = now - body._revealStart;
    const step = Math.min(38, 900 / marks.length);
    let delay = 0, index = 0;
    for (const el of [...body.querySelectorAll(`${MARKS}, .claim-badge`)].filter(visible)) {
      const mark = el.matches(MARKS);
      if (mark) delay = Math.round(index++ * step);
      el.style.setProperty('--cx-reveal-delay', `${Math.round((mark ? delay : delay + 260) - elapsed)}ms`);
    }
    body._revealTotal = delay + 900;
    body.classList.add('is-marks-revealing');
    clearTimeout(body._revealTimer);
    body._revealTimer = setTimeout(() => {
      body.classList.remove('is-marks-revealing');
      for (const el of body.querySelectorAll('[style*="--cx-reveal-delay"]')) el.style.removeProperty('--cx-reveal-delay');
    }, Math.max(0, body._revealTotal - elapsed));
  }
  function render(body, review, evidence = {}) {
    if (!body?.parentElement) return;
    const version = review?.versions?.find(v => v.id === review.answer_version);
    const raw = body.dataset.markdown ?? version?.text;
    // A source pill carries a favicon and may stand for several sources.
    const turnSources = safeSources([evidence, ...(evidence.events || []), {text: raw}, { sources: [...body.querySelectorAll('a[href]')]
      .filter(a => !a.closest('code, pre') && (a.matches('.src-ref') || !a.querySelector('img, svg')))
      .flatMap(a => a.sourceGroup?.length ? a.sourceGroup.map(entry => entry.src).filter(Boolean)
        : [a.sourceData || {url: a.getAttribute('href'), title: a.textContent}]) },
      ...(review?.comparisons || []).flatMap(c => c.answers || []), ...(review?.versions || [])]);
    let host = body._agentReview;
    if (!review?.comparisons?.length) {
      if (host?._hasReview && typeof body.dataset.markdown === "string") window.injectMarkdown?.(body, body.dataset.markdown, []);
      window.linkifyAgentSources?.(body, turnSources);
      body._agentModels?.remove(); body._agentModels = null;
      if (!turnSources.length) {
        // Copy lives inside the evidence row; hand it back to the answer first.
        const bar = host?.querySelector(':scope > .agent-answer-actions');
        if (bar) body.after(bar);
        host?.remove(); body._agentReview = null; return;
      }
      if (!host?.isConnected) { host = node('section', 'agent-review'); body.after(host); body._agentReview = host; }
      const signature = JSON.stringify([evidence.key, evidence.question, turnSources]);
      if (host.dataset.signature === signature) return;
      host.dataset.signature = signature; host._hasReview = false; host.hidden = false;
      const actions = host.querySelector(':scope > .agent-answer-actions');
      const context = { key: `agent-sources:${evidence.key || body.id || evidence.question}`, question: evidence.question || 'Answer sources',
        answers: [], sections: ['sources'], renderPanel: () => sourcePanel(turnSources) };
      const nav = node('nav', 'consensus-footer-tabs agent-evidence-links');
      nav.setAttribute('aria-label', 'Explore answer evidence');
      const button = evidenceButton('sources', 'Sources', turnSources.length);
      button.addEventListener('click', () => App.answerReader?.openContext(context, {section: 'sources', trigger: button}));
      nav.append(button); host.replaceChildren(nav); keepActions(host, actions); App.answerReader?.refreshContext(context); return;
    }
    if (!host?.isConnected) {
      host = node("section", "agent-review"); body.after(host); body._agentReview = host;
      host.setAttribute("aria-label", "Answer evidence");
    }
    const exact = !!version && raw === version.text && version.hash === review.answer_hash;
    const boundCheck = comparison => currentCheck(review, comparison, raw);
    const signature = JSON.stringify([review, raw, exact, turnSources, body._agentRenderSerial || 0]);
    if (host.dataset.signature === signature) {
      activityContexts.set(review, host._contexts);
      window.linkifyAgentSources?.(body, turnSources); return;
    }
    host.dataset.signature = signature;
    host._hasReview = true;
    const actions = host.querySelector(':scope > .agent-answer-actions');
    host.replaceChildren();
    const issues = review.comparisons.flatMap(c => checkIssues(c, boundCheck(c)));
    const state = ['succeeded', 'partial'].includes(review.status) && !review.comparisons.every(boundCheck) ? 'required'
      : review.status === 'succeeded' && issues.length ? 'partial' : review.status;
    host.hidden = !version && ["required", "running"].includes(state);
    const summary = node("div", "agent-review-summary");
    const status = node("span", "agent-review-status", summaryText(state, issues));
    status.setAttribute("role", "status"); status.dataset.state = state;
    status.hidden = !status.textContent;
    status.title = [...issues.map(issueText), "Model agreement compares perspectives; it is not independent fact checking."].join('. ');
    summary.append(status); host.append(summary);
    const tabs = node("nav", "consensus-footer-tabs agent-evidence-links agent-evidence-grid");
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
            text: a.text, sources: safeSources([a]), sourceReferences: 'agent', status: "complete",
            ...(a.truncated ? { badge: 'Cut off', note: 'Stopped at its output limit, so its end is missing. It is used as a shortened answer.' } : {}) })),
          // Text a model wrote before it stopped stays readable, marked, and
          // outside the answer and its check.
          ...(comparison.failed_models || []).map((m, i) => m.partial_text
            ? { provider: `unavailable-${i}`, model: m.model, label: m.label, text: m.partial_text, status: "incomplete",
                sources: safeSources([{ text: m.partial_text }]), sourceReferences: 'agent',
                error: `Stopped before it finished: ${failureReason(m.failure)}. Not used for the answer or its check.` }
            : { provider: `unavailable-${i}`, model: m.model, label: m.label,
            text: "", status: comparison.status === "cancelled" ? "canceled" : "error",
            error: `No answer from this model: ${failureReason(m.failure)}. The comparison uses the other answers.`, sources: [] })
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
        panel.append(evidenceStatus(comparison, answers, check, state, localIssues));
        for (const issue of localIssues.filter(i => decisive.has(i.code))) {
          // These change how the panel reads (no marks at all), so they stay visible.
          panel.append(node('p', 'agent-review-note agent-evidence-limit', issueText(issue) + '.'));
        }
        // Everything after the cards is supporting detail: one quiet footer
        // below a hairline instead of notes and reports above the findings.
        const footer = node("div", "agent-evidence-footer");
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
            // The per-card results sit in the cards; the overall report is
            // supporting detail and follows them instead of preceding them.
            const report = node('div', 'agent-source-check');
            footer.append(report);
            App.sourceVerification?.render(cards, report, verification, {
              differencesData: check.differences_data, differenceCards: cards
            });
          } else if (typeof review.check_sources === 'boolean') {
            footer.append(node('p', 'agent-review-note', !review.check_sources ? 'Contradiction source checks were off for this message.'
              : ['failed', 'cancelled', 'missing'].includes(state) ? 'Contradiction source checks did not complete.'
              : 'Contradiction source checks pending.'));
          }
        }
        footer.append(node("p", "agent-review-note", "Model agreement is not independent fact checking."));
        const basis = node("details", "agent-evidence-context");
        basis.append(node("summary", "", "Comparison context"));
        if (comparison.reason) basis.append(node("p", "", comparison.reason));
        if (comparison.context) basis.append(node("p", "", comparison.context));
        footer.append(basis);
        if ((review.versions || []).length > 1) {
          const history = node("details", "agent-evidence-context"); history.append(node("summary", "", "Earlier answer version"));
          for (const prior of review.versions.slice(0, -1)) {
            history.append(node("p", "agent-review-note", `Version ${prior.id} · ${states[prior.status] || "Not reviewed"}`));
            const text = node("div", "consensus-answer-body"); window.injectMarkdown?.(text, prior.text, []); history.append(text);
            window.linkifyAgentSources?.(text, safeSources([{sources}, {text: prior.text}]));
          }
          footer.append(history);
        }
        panel.append(footer);
        return panel;
      };
      context.mark = () => {
        // Same text, check, sources and DOM: keep the marked DOM. Rebuilding
        // it on every live update restarted the reveal and hover state.
        const markSignature = JSON.stringify([raw, context.key, check?.differences_data || null, sources,
          body._agentRenderSerial || 0]);
        if (body._markSignature === markSignature && body.querySelector('.cx-claim')) {
          // The evidence row was rebuilt: its key-claims list moves along.
          const previous = body._markFallback;
          if (previous && previous !== fallback) { fallback.replaceChildren(...previous.childNodes); fallback.hidden = previous.hidden; }
          body._markFallback = fallback;
          return;
        }
        body._markSignature = markSignature;
        body._markFallback = fallback;
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
    host._contexts = contexts;
    contextsByKey.clear();
    for (const context of contexts) contextsByKey.set(context.key, context);
    activityContexts.set(review, contexts);
    let chosen = contexts.find(c => c.key === host._selectedBasis) || contexts[0];
    function select(context) {
      chosen = context; host._selectedBasis = context.key;
      context.mark(); tabs.replaceChildren();
      for (const [section, label, count] of context.links()) {
        const button = evidenceButton(section, label, count);
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
    if (evidence.reveal) revealMarks(body, review.answer_hash);
    summary.hidden = [...summary.children].every(child => child.hidden);
    keepActions(host, actions);
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
  App.agentReview = { render, renderActivity, failureNote, failureReason };
})();
