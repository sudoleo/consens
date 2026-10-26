// Agent evidence uses the same reader, formatted answers and markers as Consensus.
(function () {
  "use strict";
  const App = window.App = window.App || {};
  // "off": the user switched the answer check off (Settings › Agent · Beta),
  // so no judge ran; the line says why the answer has no marks.
  // One word per state of the answer check, the same everywhere (App.words,
  // Apple-Audit H9).
  const W = App.words || {};
  const states = { required: "Answer check pending", running: W.checking || "Checking the answer…", succeeded: W.checked || "Checked",
    partial: W.partlyChecked || "Partly checked", failed: "Answer check failed", cancelled: "Answer check stopped", missing: "Not checked",
    off: W.checkOff || "Answer check off" };
  // Turns saved between 7303e034 and the full answer check (both 2026-10-09) did not
  // check the answer of a comparison that checked a pasted text (`skipped`);
  // since then it is judged like any answer.
  const PASSAGE_CHECKED = "passage_checked";
  const PASSAGE_NOTE = "Your text was checked sentence by sentence; the result is shown above the answer.";
  const OFF_NOTE = "The answer check is off in Settings › Agent · Beta, so this answer was not checked against the model answers.";
  // Short, calm reasons for one model call that ended without a result. The
  // provider's own error text never reaches the page (see provider_failure).
  const reasons = { provider_rate_limited: 'the provider was busy', provider_timeout: 'the provider stopped responding',
    provider_unavailable: 'the model was unavailable at its provider', provider_access: 'the provider declined the request',
    provider_rejected: 'the provider rejected the request',
    output_limit: 'it used its whole output allowance before finishing',
    empty_answer: 'it stopped twice without writing an answer',
    late_cutoff: 'it was still writing when the answer was finished', stopped: 'the run was stopped' };
  function failureReason(failure) {
    return reasons[failure?.code] || 'no complete answer arrived';
  }
  // The answer text is fixed and its review finished (or was switched off)
  // before the run ended. In audit mode a fixed answer is complete whatever
  // became of its review: their final round starts only once it is written.
  function reviewedAnswer(review, raw) {
    const version = review?.versions?.find(v => v.id === review.answer_version);
    const settled = isAudit(review) ? !['required', 'running'].includes(review.status)
      : ['succeeded', 'partial', 'off'].includes(review?.status);
    return Boolean(version && typeof raw === 'string' && raw.trim() && raw === version.text
      && version.hash === review.answer_hash && settled);
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
  // The agreement score under an Agent answer: the same number and words as
  // the Consensus verdict (consensus-insights.js), set quietly in the
  // evidence row. Only the number carries the traffic-light colour. Settings
  // decide how much shows: body.agreement-score-hidden keeps the words,
  // body.agreement-verdict-hidden removes it (agent-chat.css).
  function agreementLevel(score) {
    return score >= 85 ? 'High agreement' : score >= 65 ? 'Strong agreement' : score >= 40 ? 'Partial agreement'
      : score >= 20 ? 'Low agreement' : 'Very low agreement';
  }
  function agreementNode(check, modelCount) {
    const agreement = check?.differences_data?.agreement;
    if (!agreement || typeof agreement.score !== 'number' || agreement.coverage_status === 'insufficient') return null;
    const score = Math.max(0, Math.min(100, Math.round(agreement.score)));
    const level = agreementLevel(score);
    const el = node('span', 'agent-agreement');
    el.dataset.tone = score >= 65 ? 'calm' : score >= 40 ? 'warn' : 'alert';
    el.title = (modelCount === 1 ? `${level}: agreement score ${score}/100 across 1 model. `
      : `${level}: agreement score ${score}/100 across ${modelCount} models. `)
      + 'Model agreement compares perspectives; it is not independent fact checking.';
    const value = node('span', 'agent-agreement-score');
    value.append(node('span', 'agent-agreement-num', String(score)), node('span', 'agent-agreement-unit', '/100 agreement'));
    el.append(value, node('span', 'agent-agreement-level', level));
    return el;
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
    // No check ran (answer check off): no limit of a check to explain. The
    // reader still lists models without an answer (evidenceStatus).
    if (!check || check.status === 'off') return [];
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
    return [...issues];
  }
  function issueText(issue) {
    const n = issue.count;
    return ({models_unavailable: n === 1 ? '1 comparison model returned no usable answer; the check uses the remaining answers'
        : `${n} comparison models returned no usable answer; the check uses the remaining answers`,
      insufficient_answers: 'Fewer than two complete model answers arrived, so no comparison was possible',
      differences_unavailable: 'The answer check couldn’t look for disagreements, so none are marked',
      coverage_unavailable: 'The answer check couldn’t compare each sentence, so none is marked as supported',
      sentences_unchecked: n === 1 ? '1 sentence could not be checked' : `${n} sentences could not be checked`,
      unindexed_sentences: n === 1 ? '1 sentence fell outside the answer check' : `${n} sentences fell outside the answer check`,
      truncated_answers: 'Some model answers were too long to check in full',
      incomplete: 'The saved check is incomplete'})[issue.code] || 'The check is incomplete';
  }
  function statusText(state, issues) {
    if (!['succeeded', 'partial'].includes(state)) return states[state] || states.partial;
    if (issues.length && issues.every(i => i.code === 'models_unavailable')) {
      const n = issues.reduce((total, i) => total + i.count, 0);
      return n === 1 ? `${states.succeeded} · 1 model without an answer` : `${states.succeeded} · ${n} models without an answer`;
    }
    return issues.length ? states.partial : states[state];
  }
  // The line under the answer speaks only when it changes how far the reader
  // can rely on the marks. A finished check, or one that simply had fewer
  // answers to work with, needs no words: the marks and counts say enough.
  // Nor does a check the reader switched off: repeating "off" under every
  // answer reads like a warning (the reader and the activity still say it).
  const decisive = new Set(['insufficient_answers', 'differences_unavailable', 'coverage_unavailable']);
  function summaryText(state, issues) {
    if (state === 'off') return '';
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
  // Above the findings only what they cannot say themselves: a missing
  // model, a check still running or incomplete. "4 models answered ·
  // Checked" for a complete check only confused (Max 2026-10-23); it is no
  // line at all now (null).
  function evidenceStatus(comparison, answers, check, state, issues) {
    const unavailable = check ? comparison.failed_models || [] : [];
    const total = answers.length + unavailable.length;
    const word = checkWord(check?.status || state, issues);
    const parts = [unavailable.length ? `${answers.length} of ${total} models answered` : '', word === 'Checked' ? '' : word];
    const details = [];
    for (const model of unavailable) details.push(model.partial_text
      ? `${model.label}: stopped before it finished, ${failureReason(model.failure)}. Its partial answer is under Answers, not in the check.`
      : `${model.label}: no answer, ${failureReason(model.failure)}.`);
    // Arrived after the answer was written: shown, but neither in the text nor in its check.
    const late = check ? answers.filter(a => a.late).map(a => a.model?.label || a.provider_label || a.provider) : [];
    if (late.length) details.push(`${late.join(', ')} answered after the answer was written. ${late.length === 1 ? 'Its answer is' : 'Their answers are'} under Answers, not part of the answer or its check.`);
    if (check) for (const issue of issues) {
      if (issue.code !== 'models_unavailable' && !decisive.has(issue.code)) details.push(issueText(issue) + '.');
    }
    // Notes on a complete check (an answer that came late) open under the count.
    if (details.length && !parts.some(Boolean)) parts[0] = total === 1 ? '1 model answered' : `${total} models answered`;
    // Part by part through App.t: the joined line has no entry of its own.
    const line = parts.filter(Boolean).map(part => window.App.t(part)).join(' · ');
    if (!line) return null;
    if (!details.length) return node('p', 'agent-evidence-status', line);
    const box = node('details', 'agent-evidence-status');
    box.append(node('summary', '', line));
    const list = node('ul', 'agent-evidence-status-detail');
    for (const text of details) list.append(node('li', '', text));
    box.append(list);
    return box;
  }
  function node(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  // What the comparison cards show. The streaming answer counts only through
  // whether a check belongs to it, a model's text only through being there:
  // both change on every tick while the agent writes, and rebuilding the cards
  // each time swallowed clicks on their buttons (Apple audit D7).
  const UNSHOWN_TEXT = new Set(['text', 'partial_text']);
  function activitySignature(review, raw) {
    const bound = (review?.comparisons || []).map(c => Boolean(currentCheck(review, c, raw)));
    return JSON.stringify([review, bound], (key, value) =>
      UNSHOWN_TEXT.has(key) && typeof value === 'string' ? value !== '' : key === 'claims' ? undefined : value);
  }
  function renderActivity(host, review, raw) {
    if (isAudit(review)) return renderAuditActivity(host, review);
    const comparisons = review?.comparisons || [];
    host.hidden = !comparisons.length;
    // The buttons open the newest review's contexts, also when it rendered the same.
    host._activityReview = review;
    const signature = activitySignature(review, raw);
    if (host._activitySignature === signature) return;
    host._activitySignature = signature;
    host.replaceChildren();
    if (!comparisons.length) return;
    // The comparisons continue the timeline (agent-chat.css); the heading
    // stays for screen readers only.
    host.append(node('h3', 'visually-hidden', 'Comparison details'));
    comparisons.forEach((comparison, index) => {
      const card = node('section', 'agent-activity-insight');
      const answers = comparison.answers || [], missing = comparison.failed_models || [];
      // Whole sentences: the page translates a text as one (docs/i18n.md).
      const number = index + 1, count = answers.length;
      card.append(node('h4', '', comparison.status === 'running' ? `Comparison ${number} · Collecting answers…`
        : count === 1 ? `Comparison ${number} · 1 model answer` : `Comparison ${number} · ${count} model answers`));
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
      // The comparison checked a pasted text instead (agent_comparison.py).
      const passageChecked = check?.skipped === PASSAGE_CHECKED;
      card.append(node('p', 'agent-activity-check', comparison.status === 'running' && !check
        ? 'Waiting for independent model answers.' : passageChecked ? PASSAGE_NOTE : statusText(state, issues)));
      const differences = check?.differences_data?.differences || [];
      if (differences.length) {
        const list = node('ul', 'agent-activity-findings');
        for (const difference of differences.slice(0, 3)) {
          const text = difference.claim || difference.consensus_anchor;
          if (!text) continue;
          // The label is translated on its own; the claim is model text.
          const item = node('li', '', difference.type === 'contradiction' ? 'Disagreement' : 'Difference');
          const claim = node('span', '', text);
          claim.setAttribute('data-i18n-skip', '');
          item.append(': ', claim);
          item.dataset.type = difference.type === 'contradiction' ? 'contradiction' : 'difference';
          list.append(item);
        }
        if (differences.length > 3) list.append(node('li', '', `${differences.length - 3} more in the detailed review.`));
        card.append(list);
      } else if (check?.status === 'succeeded' && Array.isArray(check.differences_data?.differences)) {
        card.append(node('p', '', 'The completed comparison check reported no differences.'));
      }
      for (const issue of issues) card.append(node('p', 'agent-activity-limitation', issueText(issue)));
      const actions = node('div', 'agent-activity-insight-actions');
      // Without a check there is no review to explore, only the sources.
      const explore = check?.status === 'off' ? ['sources', 'Explore sources'] : ['differences', 'Explore review and sources'];
      for (const [section, label] of [['answers', 'Read model answers'], explore]) {
        const button = node('button', 'consensus-tab', label); button.type = 'button';
        button.disabled = section === 'answers' ? !answers.length : !check;
        button.addEventListener('click', () => {
          const key = `agent-evidence:${comparison.id}`;
          const context = activityContexts.get(host._activityReview)?.find(c => c.key === key) || contextsByKey.get(key);
          if (context) App.answerReader?.openContext(context, { section, trigger: button });
        });
        actions.append(button);
      }
      card.append(actions); host.append(card);
    });
  }
  // The links a markdown text carries, parsed once per text. Every open of a
  // chat and every review update ran marked and DOMPurify again over each
  // turn's answer and all its model answers (Apple audit D5). The cache
  // holds the newest texts up to a size, so a streaming answer's many
  // intermediate versions push out only themselves over time.
  const textLinks = new Map();
  let textLinkChars = 0;
  function linksOf(text) {
    const known = textLinks.get(text);
    if (known) return known;
    const links = [];
    const template = document.createElement('template');
    template.innerHTML = window.DOMPurify.sanitize(window.marked.parse(text));
    for (const link of template.content.querySelectorAll('a[href]')) {
      if (link.closest('code, pre') || link.querySelector('img, svg')) continue;
      const preceding = link.previousSibling?.textContent || '';
      const title = /^https?:\/\//i.test(link.textContent)
        ? preceding.match(/(?:^|[.,;:\n])\s*([^()[\]\n,;:]{1,100}?)\s*\($/)?.[1]?.trim() || link.textContent
        : link.textContent;
      links.push({ url: link.getAttribute('href'), title });
    }
    textLinks.set(text, links);
    textLinkChars += text.length;
    while (textLinks.size > 1 && (textLinks.size > 160 || textLinkChars > 2_000_000)) {
      const oldest = textLinks.keys().next().value;
      textLinkChars -= oldest.length;
      textLinks.delete(oldest);
    }
    return links;
  }
  function safeSources(answers) {
    const sources = new Map();
    for (const answer of answers || []) {
      const citations = [...(answer.sources || [])];
      if (typeof answer.text === 'string' && answer.text && window.marked?.parse && window.DOMPurify) {
        citations.push(...linksOf(answer.text));
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
  // The server's match form of a URL (agent_read_source.url_key): any
  // scheme as https, host case-insensitive, no trailing slash, no fragment.
  function readKey(value) {
    try {
      const url = new URL(value);
      if (!['http:', 'https:'].includes(url.protocol)) return '';
      return `https://${url.host.toLowerCase()}${url.pathname.replace(/\/+$/, '') || '/'}${url.search}`;
    } catch (_) { return ''; }
  }
  // Sources the agent opened itself (read_source) and really read, also by
  // the grounding redirect an answer cited.
  function readUrls(review) {
    const keys = new Set();
    for (const item of Array.isArray(review?.read_sources) ? review.read_sources : []) {
      if (item?.status !== 'completed') continue;
      for (const url of [item.url, item.cited_url]) {
        const key = readKey(url);
        if (key) keys.add(key);
      }
    }
    return keys;
  }
  function sourcePanel(sources, read = new Set()) {
    const panel = node('div', 'agent-evidence-panel');
    const list = node('ol', 'answer-reader-sources');
    for (const source of sources) {
      const li = node('li'); const link = node('a', '', source.title);
      link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; li.append(link);
      if (read.size && read.has(readKey(source.url))) li.append(' ', node('span', 'agent-source-read', 'Read by the agent'));
      list.append(li);
    }
    panel.append(sources.length ? list : node('p', 'agent-review-note', 'No source URLs were supplied for this answer.'));
    return panel;
  }
  function evidenceButton(section, label, count) {
    const button = node('button', 'consensus-tab agent-evidence-link');
    // "Review" names the place of the answer check here, not an action:
    // German reads it as „Widersprüche“ (docs/i18n.md, context).
    button.dataset.i18nContext = 'answer tabs';
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
  // Later re-renders of the same answer show them at once. Provisional marks
  // carry no colour (preview()), so every coloured mark is new to the reader.
  const MARKS = '.cx-claim:is(.is-thin, .is-unanimous, .is-minor, .is-split, .is-major)';
  // A re-render during the reveal (a fresh DOM when the run ends) continues
  // the stroke where it was, through negative delays, instead of restarting.
  function revealMarks(body, hash) {
    // Marks hidden by the highlight setting (all markers off, or e.g. green
    // ones filtered out) neither animate nor take a place in the sequence.
    const visible = el => !el.classList.contains('is-marker-filtered');
    const moving = document.body.classList.contains('consensus-markers-hidden') ? []
      : [...body.querySelectorAll(`${MARKS}, .claim-badge`)].filter(visible);
    const marks = moving.filter(el => el.matches(MARKS));
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
    for (const el of moving) {
      const mark = el.matches(MARKS);
      if (mark) delay = Math.round(index++ * step);
      el.style.setProperty('--cx-reveal-delay', `${Math.round((mark ? delay : delay + 260) - elapsed)}ms`);
    }
    body._revealTotal = delay + 900;
    body.classList.add('is-marks-revealing');
    clearTimeout(body._revealTimer);
    body._revealTimer = setTimeout(() => {
      // The stroke ends in the mark's own colour. Handing over to the plain
      // background must not run the marks' hover transition: every mark
      // blinked out and faded in again at once, like a second, faster reveal.
      body.classList.add('is-marks-settling');
      settleHandOver(body);
      body.classList.remove('is-marks-revealing');
      for (const el of body.querySelectorAll('[style*="--cx-reveal-delay"]')) el.style.removeProperty('--cx-reveal-delay');
      void body.offsetWidth;
      body.classList.remove('is-marks-settling');
    }, Math.max(0, body._revealTotal - elapsed));
  }
  // Every source of the turn: search, the answer's links, comparison citations.
  function sourcesOf(body, review, evidence, raw) {
    // A source pill carries a favicon and may stand for several sources.
    return safeSources([evidence, ...(evidence.events || []), {text: raw}, { sources: [...body.querySelectorAll('a[href]')]
      .filter(a => !a.closest('code, pre') && (a.matches('.src-ref') || !a.querySelector('img, svg')))
      .flatMap(a => a.sourceGroup?.length ? a.sourceGroup.map(entry => entry.src).filter(Boolean)
        : [a.sourceData || {url: a.getAttribute('href'), title: a.textContent}]) },
      ...(review?.comparisons || []).flatMap(c => c.answers || []), ...(review?.versions || [])]);
  }
  // Marks are laid over the text the reader sees, never a new copy of it:
  // the answer is morphed back to its plain render (markdown-stream.js),
  // marked and turned into pills inside the nodes on screen, and a selection
  // the reader holds comes back where it was. Each check update replaced the
  // whole answer before, two to five times a run (Apple audit A6).
  function overText(body, raw, change) {
    const apply = () => {
      // The marks are redrawn: a hover card of one of them goes with it.
      App.claimPopover?.hidePreview?.(body);
      if (typeof raw === 'string' && !window.isPlainMarkdown?.(body, raw)) {
        if (window.morphMarkdown) window.morphMarkdown(body, raw); else window.injectMarkdown?.(body, raw, []);
      }
      change?.();
    };
    return window.keepTextSelection ? window.keepTextSelection(body, apply) : apply();
  }
  // Provisional marks (since 2026-10-18): while the judges check the fixed
  // answer, the Coverage windows that are done send their verdicts
  // (coverage_preview, never saved). Since 2026-10-21 they show only THAT a
  // sentence was compared: one quiet neutral line under every such sentence,
  // no colour, no count, a hover card without a verdict (Max: a sentence
  // turned amber, the amber went, then another one turned red). They appear
  // only on the exact answer they were checked on and fade in, each once.
  // The final review replaces them in the same frame (render, context.mark):
  // each sentence keeps its line until its colour strokes on (handOver).
  // Anything else (no preview, another answer, a check that ended without a
  // result) takes them off again. `previews` holds the newest preview of
  // each comparison; the marks belong to the comparison the evidence row
  // will show.
  const PROVISIONAL = '.cx-claim.is-provisional';
  // The hand-over takes at most the reveal (900 ms plus the stroke of the
  // last mark); afterwards the class leaves no trace.
  const HAND_OVER_MS = 2400;
  function handOver(body, texts) {
    if (!texts?.size) return;
    for (const el of body.querySelectorAll('.cx-claim')) {
      if (texts.has(el.textContent)) el.classList.add('was-provisional');
    }
    clearTimeout(body._handOverTimer);
    body._handOverTimer = setTimeout(() => settleHandOver(body), HAND_OVER_MS);
  }
  function settleHandOver(body) {
    clearTimeout(body._handOverTimer);
    for (const el of body.querySelectorAll('.was-provisional')) el.classList.remove('was-provisional');
  }
  function preview(body, review, previews, evidence = {}) {
    if (!body?.parentElement) return;
    const applied = body._previewMarks;
    // A render since took the marks with it: a morphed one keeps the first
    // node but counts as a write (markdown-stream.js), any other replaces it.
    const intact = Boolean(applied) && applied.writes === body._markdownWrites && body.firstChild === applied.first;
    const version = review?.versions?.find(v => v.id === review.answer_version);
    const raw = body.dataset.markdown;
    const comparisons = review?.comparisons || [];
    const comparison = comparisons.find(c => `agent-evidence:${c.id}` === body._agentReview?._selectedBasis) || comparisons[0];
    const data = comparison && previews?.[comparison.id];
    const claims = (Array.isArray(data?.claims) ? data.claims : [])
      .filter(c => c && c.anchor && Array.isArray(c.agree) && Array.isArray(c.dissent));
    const usable = claims.length > 0 && typeof raw === 'string' && Boolean(version) && raw === version.text
      && version.hash === review.answer_hash && data.answer_hash === review.answer_hash
      && ['required', 'running'].includes(review.status);
    if (!usable) {
      if (intact) {
        const sources = sourcesOf(body, review, evidence, raw);
        overText(body, raw, () => window.linkifyAgentSources?.(body, sources));
      }
      if (applied) { body._previewMarks = null; body.classList.remove('has-provisional-marks'); }
      return;
    }
    const signature = JSON.stringify([review.answer_hash, comparison.id, claims, data.models_compared]);
    if (intact && applied.signature === signature) return;
    const sources = sourcesOf(body, review, evidence, raw);
    overText(body, raw, () => {
      // Coverage only: no contradictions and no score yet, and no "Key claims"
      // list for sentences without an anchor while the check is incomplete.
      window.renderStoredConsensusClaims?.(body, { claims, differences: [],
        models_compared: Array.isArray(data.models_compared) ? data.models_compared : [] },
      document.createElement('div'), sources, { answerNavigation: { canOpen: () => false, open() {} }, focusDifference() {},
        provisional: true });
      window.linkifyAgentSources?.(body, sources);
    });
    // The sentences the reader has seen marked; one not seen before fades in, once.
    const shown = review.answer_hash && body._shownMarks?.hash === review.answer_hash ? body._shownMarks.keys : new Set();
    for (const el of body.querySelectorAll(PROVISIONAL)) {
      el.classList.toggle('is-mark-arriving', !shown.has(el.textContent));
      shown.add(el.textContent);
    }
    body._shownMarks = { hash: review.answer_hash, keys: shown };
    // The final review draws its marks anew (context.mark).
    body._markSignature = null;
    body._previewMarks = { signature, writes: body._markdownWrites, first: body.firstChild };
    body.classList.add('has-provisional-marks');
  }
  // --- Audit instead of comparison (admins, since 2026-10-25) ----------------
  // The comparison models followed the agent's work log and reviewed the
  // fixed answer (agent_audit.py): their marks show once every reviewer is
  // done, through the shared markers (renderStoredAuditMarks), and "Notes"
  // opens their reviews in the reader, with their notes on the work (log
  // entries). No score and no Differences: unmarked text means no objection.
  // Done: every reviewer ended, the notes can be read. Ended: also stopped
  // or never started; nothing is reviewing any more.
  const AUDIT_DONE = new Set(['succeeded', 'partial', 'failed']);
  const AUDIT_ENDED = new Set([...AUDIT_DONE, 'cancelled', 'missing']);
  const AUDIT_KINDS = { wrong: 'Wrong', doubtful: 'Doubtful', incomplete: 'Incomplete' };
  const auditReasons = { review_unreadable: 'its review could not be read', no_time: 'it ran out of time',
    audit_unavailable: 'the review could not be completed', stopped: 'the review was stopped',
    context_limit: 'the work did not fit its context' };
  function auditReason(failure) {
    return auditReasons[failure?.code] || failureReason(failure);
  }
  function isAudit(review) {
    return review?.mode === 'audit' && Boolean(review.audit);
  }
  // Every mark once, in the order of the answer, then those whose passage
  // the answer does not hold. A mark over several sentences sits on each
  // (same ``mark`` number): its quote is their quoted words together.
  function auditMarks(audit) {
    const marks = new Map();
    for (const claim of audit?.claims || []) {
      for (const item of claim.dissent || []) {
        if (!item) continue;
        const key = item.mark ?? `${item.model}|${item.kind}|${item.note}`;
        const words = item.target || claim.anchor;
        const known = marks.get(key);
        if (known) known.quote = `${known.quote} ${words}`;
        else marks.set(key, { ...item, quote: words });
      }
    }
    for (const item of audit?.unplaced || []) {
      if (item) marks.set(item.mark ?? `${item.model}|${item.kind}|${item.note}|${item.quote}`, item);
    }
    return [...marks.values()];
  }
  function auditNotes(audit, reviewer) {
    const label = reviewer.provider_label || reviewer.provider;
    return auditMarks(audit).filter(item => item.model === label);
  }
  // The notes on the agent's work (``process``): the log entry each concerns;
  // ``live``: from a round while the agent worked (its final round failed).
  function auditWork(audit, reviewer) {
    const label = reviewer?.provider_label || reviewer?.provider;
    return (audit?.process || []).filter(item => item && (!reviewer || item.model === label));
  }
  function auditNote(item) {
    const entry = node('li', 'agent-audit-note');
    entry.dataset.kind = item.kind;
    entry.append(node('span', 'agent-audit-kind', AUDIT_KINDS[item.kind] || 'Doubtful'));
    if (item.entry) {
      // Which entry of the work log: its number, kind and name.
      const ref = node('span', 'agent-audit-entry');
      const kind = App.agentWorkLog?.KINDS?.[item.entry_kind] || item.entry_kind;
      ref.append(node('span', 'agent-audit-entry-seq', `#${item.entry}`));
      if (kind) ref.append(node('span', '', kind));
      if (item.entry_name) {
        const name = node('code', '', String(item.entry_name));
        name.setAttribute('data-i18n-skip', '');
        ref.append(name);
      }
      if (item.live) ref.append(node('span', 'agent-audit-live', 'During the run'));
      entry.append(ref);
    }
    if (item.quote) {
      const quote = node('q', 'agent-audit-quote', String(item.quote));
      quote.setAttribute('data-i18n-skip', '');
      entry.append(quote);
    }
    const text = node('p', 'agent-audit-text', String(item.note || ''));
    text.setAttribute('data-i18n-skip', '');
    entry.append(text);
    try {
      const url = new URL(String(item.source || ''));
      if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) {
        const link = node('a', 'agent-audit-source', url.hostname.replace(/^www\./, ''));
        link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
        link.setAttribute('data-i18n-skip', '');
        entry.append(link);
      }
    } catch (_) { /* No source. */ }
    return entry;
  }
  function auditList(items) {
    const list = node('ul', 'agent-audit-notes');
    for (const item of items) list.append(auditNote(item));
    return list;
  }
  function auditStatus(review) {
    const reviewers = review.audit.reviewers || [];
    const done = reviewers.filter(r => r.status === 'completed').length;
    if (review.status === 'partial') return window.App.t('{done} of {total} models reviewed the answer', { done, total: reviewers.length });
    return { failed: 'The review could not be completed', cancelled: 'Review stopped', missing: 'Not reviewed' }[review.status] || '';
  }
  function auditPanel(review) {
    const panel = node('div', 'agent-evidence-panel agent-audit-panel');
    const audit = review.audit;
    const reviewers = audit.reviewers || [];
    const missing = reviewers.filter(r => r.status !== 'completed');
    const status = auditStatus(review);
    if (status) panel.append(node('p', 'agent-evidence-status', status));
    if (AUDIT_DONE.has(review.status) && reviewers.length > missing.length) {
      panel.append(node('p', 'agent-review-note', 'Unmarked text means no objection, not confirmed.'));
    }
    for (const reviewer of reviewers) {
      const section = node('section', 'agent-audit-reviewer');
      const name = reviewer.model?.label || reviewer.provider_label || reviewer.provider;
      const head = node('h4', 'agent-audit-reviewer-name');
      head.append(App.createModelMark?.({ provider: reviewer.provider_label, model: reviewer.model?.model, label: name })
        || node('span', 'model-mark-fallback', String(name).slice(0, 1)), node('span', '', name));
      head.lastChild.setAttribute('data-i18n-skip', '');
      section.append(head);
      const work = auditWork(audit, reviewer);
      if (reviewer.status !== 'completed') {
        // Its final round failed: the notes of its rounds during the run stand.
        section.append(node('p', 'agent-review-note', work.length
          ? `No final review: ${auditReason(reviewer.failure)}.` : `No review: ${auditReason(reviewer.failure)}.`));
        if (work.length) section.append(auditList(work));
        panel.append(section);
        continue;
      }
      const notes = auditNotes(audit, reviewer);
      if (!notes.length && !work.length) section.append(node('p', 'agent-review-note', 'No objections.'));
      if (notes.length) section.append(auditList(notes));
      if (work.length) {
        section.append(node('h5', 'agent-audit-work-head', 'On the work'), auditList(work));
      }
      panel.append(section);
    }
    return panel;
  }
  // The reader context of a reviewed answer: its notes ("Notes") and sources.
  function auditContext(review, evidence = {}, turnSources = []) {
    const context = { key: `agent-audit:${review.answer_hash}`, question: evidence.question || 'Answer review',
      answers: [], sections: ['differences', 'sources'], labels: { differences: 'Notes' },
      renderPanel: kind => kind === 'sources' ? sourcePanel(turnSources, readUrls(review)) : auditPanel(review) };
    // One review per answer: the reader offers no other basis to switch to.
    context.contextGroup = () => [context];
    contextsByKey.delete(context.key); contextsByKey.set(context.key, context);
    while (contextsByKey.size > 64) contextsByKey.delete(contextsByKey.keys().next().value);
    return context;
  }
  // The review in the duration disclosure: who reviewed, what came of it.
  function renderAuditActivity(host, review) {
    const audit = review.audit, reviewers = audit.reviewers || [];
    host.hidden = !reviewers.length;
    host._activityReview = review;
    const marks = auditMarks(audit).length, work = auditWork(audit).length;
    const signature = JSON.stringify(['audit', review.status, review.answer_hash, reviewers, marks, work]);
    if (host._activitySignature === signature) return;
    host._activitySignature = signature;
    host.replaceChildren();
    if (!reviewers.length) return;
    host.append(node('h3', 'visually-hidden', 'Review details'));
    const card = node('section', 'agent-activity-insight');
    const done = AUDIT_DONE.has(review.status), ended = AUDIT_ENDED.has(review.status);
    const count = reviewers.length;
    card.append(node('h4', '', !ended ? 'Review · Reviewing the answer…'
      : count === 1 ? 'Review · 1 model' : `Review · ${count} models`));
    const names = reviewers.map(r => r.model?.label || r.provider_label || r.provider).filter(Boolean);
    if (names.length) card.append(node('p', 'agent-activity-models', `Models: ${names.join(', ')}`));
    const missing = reviewers.filter(r => done && r.status !== 'completed').map(r => r.model?.label || r.provider_label);
    if (missing.length) card.append(node('p', '', `No review: ${missing.join(', ')}`));
    const found = [marks === 1 ? '1 marked passage' : marks ? `${marks} marked passages` : '',
      work === 1 ? '1 note on the work' : work ? `${work} notes on the work` : ''].filter(Boolean);
    const outcome = review.status !== 'succeeded' && review.status !== 'partial' ? auditStatus(review)
      : found.length ? '' : 'No objections.';
    const check = node('p', 'agent-activity-check', !ended ? 'Waiting for the reviews.' : outcome);
    // Each count its own element: one phrase per element for the translation.
    if (ended && !outcome) for (const [index, text] of found.entries()) {
      if (index) check.append(document.createTextNode(' · '));
      check.append(node('span', '', text));
    }
    card.append(check);
    if (done) {
      const actions = node('div', 'agent-activity-insight-actions');
      const button = node('button', 'consensus-tab', 'Read the notes'); button.type = 'button';
      button.addEventListener('click', () => {
        const current = host._activityReview;
        const context = contextsByKey.get(`agent-audit:${current.answer_hash}`) || auditContext(current);
        App.answerReader?.openContext(context, { section: 'differences', trigger: button });
      });
      actions.append(button); card.append(actions);
    }
    host.append(card);
  }
  function renderAudit(body, review, evidence, host, raw, turnSources) {
    const version = review.versions?.find(v => v.id === review.answer_version);
    const exact = Boolean(version) && raw === version.text && version.hash === review.answer_hash;
    const done = AUDIT_DONE.has(review.status);
    if (!host?.isConnected) {
      host = node('section', 'agent-review'); (App.answerTail?.(body) || body).after(host); body._agentReview = host;
      host.setAttribute('aria-label', 'Answer evidence');
    }
    body._agentModels?.remove(); body._agentModels = null;
    const signature = JSON.stringify(['audit', review, raw, exact, turnSources, body._agentRenderSerial || 0]);
    if (host.dataset.signature === signature) { window.linkifyAgentSources?.(body, turnSources); return; }
    host.dataset.signature = signature; host._hasReview = true;
    // Until every reviewer is done the row waits (the answer shows the check).
    host.hidden = !exact || !AUDIT_ENDED.has(review.status);
    host.replaceChildren();
    const summary = node('div', 'agent-review-summary');
    const status = node('span', 'agent-review-status', exact ? auditStatus(review) : states.required);
    status.setAttribute('role', 'status'); status.dataset.state = review.status;
    status.hidden = !status.textContent;
    summary.append(status); summary.hidden = status.hidden; host.append(summary);
    const tabs = node('nav', 'consensus-footer-tabs agent-evidence-links agent-evidence-grid');
    tabs.setAttribute('aria-label', 'Explore answer evidence'); host.append(tabs);
    const fallback = node('div', 'consensus-claims-fallback'); fallback.hidden = true; host.append(fallback);
    const context = auditContext(review, evidence, turnSources);
    const open = (section, options = {}) => App.answerReader?.openContext(context, { section, ...options });
    // The marks of exactly this answer, once the review is done.
    overText(body, raw, () => {
      if (exact && done) window.renderStoredAuditMarks?.(body, review.audit, fallback, turnSources, {
        openNotes: () => open('differences', { trigger: document.activeElement }) });
      window.linkifyAgentSources?.(body, turnSources);
    });
    body._markSignature = null;
    const marks = auditMarks(review.audit).length + auditWork(review.audit).length;
    const links = [...(done ? [['differences', 'Notes', marks]] : []), ...(turnSources.length ? [['sources', 'Sources', turnSources.length]] : [])];
    for (const [section, label, count] of links) {
      const button = evidenceButton(section, label, count);
      button.addEventListener('click', () => open(section, { trigger: button }));
      tabs.append(button);
    }
    App.answerReader?.refreshContext(context);
    if (evidence.reveal || body._revealedMarks === review.answer_hash) revealMarks(body, review.answer_hash);
  }
  function render(body, review, evidence = {}) {
    if (!body?.parentElement) return;
    const version = review?.versions?.find(v => v.id === review.answer_version);
    const raw = body.dataset.markdown ?? version?.text;
    const turnSources = sourcesOf(body, review, evidence, raw);
    let host = body._agentReview;
    if (isAudit(review) && review.versions?.length) {
      renderAudit(body, review, evidence, host, raw, turnSources);
      return;
    }
    if (!review?.comparisons?.length) {
      const unmark = host?._hasReview && typeof body.dataset.markdown === "string";
      overText(body, unmark ? body.dataset.markdown : null, () => window.linkifyAgentSources?.(body, turnSources));
      body._agentModels?.remove(); body._agentModels = null;
      if (!turnSources.length) {
        host?.remove(); body._agentReview = null; return;
      }
      if (!host?.isConnected) { host = node('section', 'agent-review'); (App.answerTail?.(body) || body).after(host); body._agentReview = host; }
      // An answer without a comparison may still rest on pages the agent read.
      const read = readUrls(review);
      const signature = JSON.stringify([evidence.key, evidence.question, turnSources, [...read]]);
      if (host.dataset.signature === signature) return;
      host.dataset.signature = signature; host._hasReview = false; host.hidden = false;
      const context = { key: `agent-sources:${evidence.key || body.id || evidence.question}`, question: evidence.question || 'Answer sources',
        answers: [], sections: ['sources'], renderPanel: () => sourcePanel(turnSources, read) };
      const nav = node('nav', 'consensus-footer-tabs agent-evidence-links');
      nav.setAttribute('aria-label', 'Explore answer evidence');
      const button = evidenceButton('sources', 'Sources', turnSources.length);
      button.addEventListener('click', () => App.answerReader?.openContext(context, {section: 'sources', trigger: button}));
      nav.append(button); host.replaceChildren(nav); App.answerReader?.refreshContext(context); return;
    }
    if (!host?.isConnected) {
      host = node("section", "agent-review"); (App.answerTail?.(body) || body).after(host); body._agentReview = host;
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
      // With the answer check off the reader has no review tab.
      const off = check?.status === 'off';
      const context = { key: `agent-evidence:${comparison.id}`, question: comparison.question, scopeLabel: "Comparison focus",
        check, modelCount: answers.length, ...(off ? { sections: ['answers', 'sources'] } : {}),
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
          return sourcePanel(sources, readUrls(review));
        }
        const localIssues = checkIssues(comparison, check);
        const status = evidenceStatus(comparison, answers, check, state, localIssues);
        if (status) panel.append(status);
        for (const issue of localIssues.filter(i => decisive.has(i.code))) {
          // These change how the panel reads (no marks at all), so they stay visible.
          panel.append(node('p', 'agent-review-note agent-evidence-limit', issueText(issue) + '.'));
        }
        // Everything after the cards is supporting detail: one quiet footer
        // below a hairline instead of notes and reports above the findings.
        const footer = node("div", "agent-evidence-footer");
        if (check?.skipped === PASSAGE_CHECKED) {
          panel.append(node("p", "agent-review-note", PASSAGE_NOTE));
        } else if (off) {
          panel.append(node("p", "agent-review-note", OFF_NOTE));
        } else if (!check || !check.differences_data) {
          panel.append(node("p", "agent-review-note", exact ? "This answer has no finished answer check yet."
            : "The text changed. This version needs a new answer check."));
        } else {
          const cards = node("div", "agent-evidence-differences");
          window.renderStoredDifferenceCards?.(cards, check.differences_data, {
            modelLabel: name => findAnswer(name)?.model?.label || name, answerNavigation: navigation
          });
          panel.append(cards);
        }
        if ((review.versions || []).length > 1) {
          const history = node("details", "agent-evidence-context"); history.append(node("summary", "", "Earlier answer version"));
          for (const prior of review.versions.slice(0, -1)) {
            history.append(node("p", "agent-review-note", `Version ${prior.id} · ${App.t(states[prior.status] || "Not reviewed")}`));
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
        // Without claims to mark, the first node tells whether the body was
        // redrawn since; a morphed render keeps it but counts as a write.
        const intact = body._markedWrites === body._markdownWrites && (check?.differences_data?.claims?.length
          ? Boolean(body.querySelector('.cx-claim')) : !!body.firstChild && body._markedFirst === body.firstChild);
        if (body._markSignature === markSignature && intact) {
          // The evidence row was rebuilt: its key-claims list moves along.
          const previous = body._markFallback;
          if (previous && previous !== fallback) { fallback.replaceChildren(...previous.childNodes); fallback.hidden = previous.hidden; }
          body._markFallback = fallback;
          return;
        }
        body._markSignature = markSignature;
        body._markFallback = fallback;
        fallback.replaceChildren(); fallback.hidden = true;
        // The sentences that carry a provisional line now hand it over to
        // their final mark, in this same frame (no moment without marks).
        const provisional = body._previewMarks
          ? new Set([...body.querySelectorAll(PROVISIONAL)].map(el => el.textContent)) : null;
        // A body that already shows exactly this text, unmarked (a saved turn
        // just rendered), is marked as it is: rendering it a second time cost
        // every opened chat a second Markdown pass per turn (Apple audit D5).
        overText(body, raw, () => {
          if (check?.differences_data) window.renderStoredConsensusClaims?.(body, check.differences_data, fallback, sources, {
            answerNavigation: navigation,
            focusDifference: differenceIndex => open("differences", { index: differenceIndex, trigger: document.activeElement })
          });
          window.linkifyAgentSources?.(body, sources);
        });
        // Provisional marks went with the old render.
        body._previewMarks = null; body.classList.remove('has-provisional-marks');
        handOver(body, provisional);
        body._markedWrites = body._markdownWrites;
        body._markedFirst = body.firstChild;
      };
      context.links = () => {
        const differences = check?.differences_data?.differences || [];
        const contradictions = differences.filter(d => d.type === "contradiction").length;
        // "Sources 0" would lead to an empty list.
        return [...(off ? [] : [["differences", contradictions ? "Contradictions" : differences.length ? "Differences" : "Review", contradictions || differences.length || null]]),
          ["answers", "Answers", answers.length], ...(sources.length ? [["sources", "Sources", sources.length]] : [])];
      };
      return context;
    });
    host._contexts = contexts;
    // Keys are comparison ids, so earlier turns stay findable (the agent
    // panel opens a model's answer from any turn); the oldest drop out.
    for (const context of contexts) { contextsByKey.delete(context.key); contextsByKey.set(context.key, context); }
    while (contextsByKey.size > 64) contextsByKey.delete(contextsByKey.keys().next().value);
    activityContexts.set(review, contexts);
    // Turns saved with a skipped answer check open on a comparison with marks.
    let chosen = contexts.find(c => c.key === host._selectedBasis)
      || contexts.find(c => c.check?.skipped !== PASSAGE_CHECKED) || contexts[0];
    function select(context) {
      chosen = context; host._selectedBasis = context.key;
      context.mark(); tabs.replaceChildren();
      // The score belongs to the comparison the row shows.
      host.querySelector(':scope > .agent-agreement')?.remove();
      const agreement = agreementNode(context.check, context.modelCount);
      if (agreement) host.append(agreement);
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
    // A later render of the same answer (e.g. the end of the run) may rebuild the marks while they still stroke on; it carries
    // the stroke on instead of dropping every mark in at once.
    if (evidence.reveal || body._revealedMarks === review.answer_hash) revealMarks(body, review.answer_hash);
    summary.hidden = [...summary.children].every(child => child.hidden);
    if (body.classList.contains('thread-history-answer-body')) {
      body._agentModels?.remove();
      // Beside "Thought for …", where the live turn shows them
      // (agent-delegation.js); a row of their own only without that line.
      const activity = body.parentElement?.querySelector(':scope > * > .agent-activity > summary');
      const models = node(activity ? 'span' : 'div', 'agent-inline-models agent-history-models');
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
      if (activity) {
        // A click on a mark opens its answer, not the activity.
        models.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); });
        activity.append(models);
      } else {
        // Above the result card of a checked text, if the answer has one.
        (body._passageCard?.parentNode === body.parentNode ? body._passageCard : body).before(models);
      }
      body._agentModels = models;
    }
    contexts.forEach(c => App.answerReader?.refreshContext(c));
  }
  // The reader context of one comparison of a rendered review, e.g. for the
  // "View answer" link of a checked sentence in the passage card.
  function contextFor(review, comparisonId) {
    const key = `agent-evidence:${comparisonId}`;
    // While a run is live the review row may not be built yet for this exact
    // review object; the last built context of the comparison still opens.
    return (review && activityContexts.get(review) || []).find(c => c.key === key) || contextsByKey.get(key) || null;
  }
  App.agentReview = { render, preview, renderActivity, failureNote, failureReason, contextFor };
})();
