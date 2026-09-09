// Advisory evidence only. State belongs to the run/turn, never a global result.
(function () {
  window.App = window.App || {};
  // Local transport state is presentation-only; it never changes a saved
  // source verdict, job status, or agreement result.
  const refreshStates = new Map();
  function applyRefreshNotice(box, state) {
    box.classList.toggle('source-check-refresh-stopped', state?.terminal === true);
    box.querySelector('.source-check-refresh-notice')?.remove();
    if (state) {
      const notice = element('p', 'source-check-refresh-notice', state.message);
      notice.setAttribute('role', 'status');
      const intro = box.querySelector('.source-check-coverage');
      if (intro) intro.after(notice); else box.prepend(notice);
    }
    if (box.dataset.sourcePending === 'true') {
      if (state?.terminal) box.parentElement?.removeAttribute('aria-busy');
      else box.parentElement?.setAttribute('aria-busy', 'true');
    }
  }
  function applyRefreshLabel(jobId, state) {
    if (document.getElementById('consensusAnswerBody')?.dataset.sourceCheckJob !== jobId) return;
    const label = document.getElementById('consensusSourceCheckStatus');
    const copy = label?.querySelector('.source-check-status-copy');
    if (copy) copy.textContent = state?.label ? ' · ' + state.label : label.dataset.sourceStatusText || '';
    if (label) {
      label.title = state?.message || label.dataset.sourceStatusTitle || '';
      label.setAttribute('aria-label', label.title);
    }
    document.querySelector('#consensusSourcesTab .consensus-tab-label')?.classList.toggle('source-check-loading',
      label?.dataset.sourcePending === 'true' && !state?.terminal);
  }
  function setRefreshState(jobId, state) {
    if (!jobId) return;
    if (state) {
      refreshStates.delete(jobId); refreshStates.set(jobId, state);
      if (refreshStates.size > 100) refreshStates.delete(refreshStates.keys().next().value);
    } else refreshStates.delete(jobId);
    document.querySelectorAll('.source-verification[data-source-check-job]').forEach(box => {
      if (box.dataset.sourceCheckJob === jobId) applyRefreshNotice(box, state);
    });
    applyRefreshLabel(jobId, state);
  }
  function noteRefreshError(jobId, error, failures) {
    const terminal = [401, 403, 404, 410].includes(error?.status);
    if (!terminal && failures < 3) return;
    setRefreshState(jobId, {terminal, label: terminal ? 'Updates unavailable' : 'Reconnecting…',
      message: terminal
        ? ([404, 410].includes(error.status)
          ? 'Source-check updates are no longer available. The last received results are shown.'
          : 'Source-check updates could not be accessed. Reopen this saved comparison after signing in. The last received results are shown.')
        : 'Source-check updates are temporarily unavailable. Retrying automatically; the last received results are shown.'});
  }
  function topic(item) { return item.topical || "unknown"; }
  function notable(item) {
    return !item.checked || ['partial', 'contradicted', 'unknown'].includes(item.support) || topic(item) !== "relevant"
      || !["suitable", "not_relevant"].includes(item.temporal);
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text) node.textContent = text;
    return node;
  }
  function skeleton(className) {
    const node = element("span", "skeleton " + className);
    node.setAttribute("aria-hidden", "true");
    return node;
  }
  function coverage(verification) {
    const findings = (verification?.findings || []).filter(Boolean);
    const total = Math.max(0, verification?.scope?.pairs ?? findings.length);
    const checked = Math.min(total, Math.max(0, verification?.scope?.checked_pairs ?? findings.filter(item => item.checked).length));
    return { total, checked, remaining: total - checked };
  }
  function coverageText(verification) {
    const { total, checked, remaining } = coverage(verification);
    const scope = verification.scope || {};
    const sourceCount = scope.sources ?? scope.source_count;
    const sources = Number.isFinite(sourceCount) ? `${scope.checked_sources || 0} of ${sourceCount} sources checked · ` : '';
    const pending = isPending(verification) ? Math.max(0, total - (scope.processed_pairs ?? checked)) : 0;
    const unavailable = Math.max(0, remaining - pending);
    return sources + `${checked} of ${total} citation checks completed`
      + (pending ? ` · ${pending} pending` : '') + (unavailable ? ` · ${unavailable} not checked` : '');
  }
  function isPending(verification) { return ['pending', 'queued', 'running'].includes(verification?.status); }
  function assessment(verification) {
    const findings = (verification?.findings || []).filter(Boolean);
    const issues = findings.filter(item => item.checked && (['partial', 'contradicted'].includes(item.support)
      || item.topical === 'off_topic' || item.temporal === 'outdated')).length;
    const unknown = findings.filter(item => item.checked && !(['partial', 'contradicted'].includes(item.support)
      || item.topical === 'off_topic' || item.temporal === 'outdated') && (item.support === 'unknown'
      || item.topical !== 'relevant' || !['suitable', 'not_relevant'].includes(item.temporal))).length;
    return { issues: Number.isFinite(verification?.scope?.issues) ? verification.scope.issues : issues,
      unknown: Number.isFinite(verification?.scope?.unknown_pairs) ? verification.scope.unknown_pairs : unknown };
  }
  function renderClaim(target, value) {
    const source = String(value || '');
    if (window.marked?.parse && window.DOMPurify?.sanitize) {
      const prepared = window.ConsensusMath?.prepareMarkdown?.(source) || source;
      target.innerHTML = window.DOMPurify.sanitize(window.marked.parse(prepared), {
        ALLOWED_TAGS: ['p', 'strong', 'em', 'del', 's', 'code', 'pre', 'br', 'a', 'ul', 'ol', 'li',
          'blockquote', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'sup', 'sub'],
        ALLOWED_ATTR: ['href', 'title', 'start', 'colspan', 'rowspan']
      });
      target.querySelectorAll('a').forEach(link => {
        link.target = '_blank'; link.rel = 'noopener noreferrer';
      });
    } else {
      target.textContent = source.replace(/\*\*|__|~~/g, '');
    }
    const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.parentElement.closest('code, pre')) continue;
      node.nodeValue = node.nodeValue.replace(/\[S?\d+(?:\s*,\s*S?\d+)*\]/gi, '')
        .replace(/\s+([.,;:!?])/g, '$1');
      // Legacy sentence boundaries sometimes leave half a bold delimiter.
      if (!/\\\*/.test(source)) node.nodeValue = node.nodeValue.replace(/\*{2,3}/g, '');
    }
    window.ConsensusMath?.render?.(target);
  }
  const bindings = new WeakMap();
  const presentations = new WeakMap();
  const navigationHighlights = new WeakMap();
  function highlightRow(target, row, identity) {
    const previous = navigationHighlights.get(target);
    if (previous?.timer) window.clearTimeout(previous.timer);
    target.querySelectorAll('.source-check-navigation-target').forEach(node => node.classList.remove('source-check-navigation-target'));
    const state = {pair: row.dataset.pair, identity, until: Date.now() + 2400};
    row.classList.add('source-check-navigation-target');
    state.timer = window.setTimeout(() => {
      target.querySelectorAll('.source-check-navigation-target').forEach(node => node.classList.remove('source-check-navigation-target'));
      navigationHighlights.delete(target);
    }, 2400);
    navigationHighlights.set(target, state);
  }
  function citationCheck(item, verification) {
    const state = findingState(item, verification);
    let summary;
    if (!item.checked) summary = state === 'pending' ? 'This citation is waiting to be checked.' : 'This citation could not be checked.';
    else if (Number(verification.schema_version) < 3) summary = 'Source checked for topic and time; statement support was not assessed.';
    else summary = {supported: 'Source checked: supports this statement.', contradicted: 'Source checked: contradicts this statement.',
      issue: item.support === 'partial' ? 'Source checked: only partly supports this statement.' : 'Source checked: topic or time needs attention.',
      unknown: 'Source checked: support for this statement is unclear.'}[state];
    const detail = item.reason ? String(item.reason) : item.reason_code && !['pending', 'queued'].includes(item.reason_code)
      ? reasonLabel(item.reason_code) : '';
    return Object.freeze({state, summary, detail: Number(verification.schema_version) >= 3 ? detail : ''});
  }
  function getCitationCheck(ref) {
    const check = bindings.get(ref)?.check;
    if (check) return check;
    // Never look up a global/latest run or borrow another statement's verdict
    // just because it cites the same source number.
    for (let parent = ref?.parentElement; parent; parent = parent.parentElement) {
      const verification = presentations.get(parent)?.verification;
      if (!verification) continue;
      if (isPending(verification)) return Object.freeze({state: 'pending', summary: 'This citation is waiting to be checked.', detail: ''});
      return Object.freeze({state: 'unchecked', summary: 'No check result is available for this citation.', detail: ''});
    }
    return null;
  }
  function customTeaser(ref) { return Boolean(window.App.sourceTeaser && ref.matches('.src-ref')); }
  function findingState(item, verification) {
    if (!item.checked) return isPending(verification) && (!item.reason_code || ['pending', 'queued'].includes(item.reason_code)) ? 'pending' : 'unknown';
    if (item.support === 'contradicted') return 'contradicted';
    if (item.support === 'partial' || item.topical === 'off_topic' || item.temporal === 'outdated') return 'issue';
    return Number(verification.schema_version) >= 3 && item.support === 'supported' && item.topical === 'relevant'
      && ['suitable', 'not_relevant'].includes(item.temporal) ? 'supported' : 'unknown';
  }
  const stateLabels = {supported: 'Verified support', contradicted: 'Contradicted', issue: 'Needs attention', unknown: 'Unclear or unavailable', pending: 'Check pending',
    uncited: 'Not cited in consensus', awaiting_details: 'Awaiting check details'};
  function sourceState(items, verification) {
    const states = items.map(item => findingState(item, verification));
    return ['contradicted', 'issue', 'unknown', 'pending'].find(state => states.includes(state))
      || (states.length ? 'supported' : isPending(verification) ? 'pending' : 'unknown');
  }
  function applySourceList(list, body) {
    if (!list || !body) return;
    const presentation = presentations.get(body);
    const verification = presentation?.verification;
    if (presentation) presentation.lists.add(list);
    list.querySelectorAll('.source-check-card-status').forEach(node => node.remove());
    list.querySelectorAll('[data-source-card-check]').forEach(node => delete node.dataset.sourceCardCheck);
    if (!verification || Number(verification.schema_version) < 3) return;
    const grouped = new Map();
    const findings = (verification.findings || []).filter(Boolean);
    const sources = verification.sources || [];
    const expectedSources = verification.scope?.sources ?? verification.scope?.source_count;
    const sourceIds = new Set(sources.map(source => source.id));
    // A compact job stub may omit the entire plan. Absence from that stub does
    // not establish that a catalogue source was not cited in the answer.
    const catalogComplete = Number.isFinite(expectedSources) && sources.length >= expectedSources
      || findings.length >= coverage(verification).total && findings.length > 0;
    findings.forEach(item => {
      if (!grouped.has(item.source_id)) grouped.set(item.source_id, []);
      grouped.get(item.source_id).push(item);
    });
    list.querySelectorAll('.consensus-source-item, .thread-history-sources > li, [id^="src-"]').forEach(card => {
      let id = card.dataset.sourceId || (card.id.match(/^src-(\d+)$/)?.[1] ? 'S' + card.id.slice(4) : '');
      if (!id) {
        const href = card.querySelector('a[href]')?.href;
        const matches = (verification.sources || []).filter(source => {
          try { return href && new URL(source.url).href === href; } catch (_) { return false; }
        });
        if (matches.length === 1) id = matches[0].id;
      }
      if (!id) return;
      const items = grouped.get(id) || [];
      const state = items.length ? sourceState(items, verification)
        : !sourceIds.has(id) && catalogComplete ? 'uncited' : 'awaiting_details';
      card.dataset.sourceCardCheck = state;
      const checked = items.filter(item => item.checked).length;
      const badge = element('span', 'source-check-card-status', (state === 'supported' ? '✓ ' : '') + stateLabels[state]);
      badge.title = items.length
        ? `${id}: ${checked} of ${items.length} citation checks completed. Green means all checked statements have source support, matching topic and time.`
        : `${id}: ${stateLabels[state]}.`;
      (card.querySelector('.consensus-source-body, .src-embed-body') || card).append(badge);
    });
  }
  function clear(body, target, preserveNavigation = false) {
    if (!preserveNavigation && target) {
      window.clearTimeout(navigationHighlights.get(target)?.timer);
      navigationHighlights.delete(target);
    }
    const previous = presentations.get(body);
    presentations.delete(body);
    previous?.lists.forEach(list => applySourceList(list, body));
    if (body) delete body.dataset.sourceCheckJob;
    target?.querySelectorAll(".source-verification").forEach(el => el.remove());
    target?.removeAttribute("aria-busy");
    body?.querySelectorAll("[data-source-check]").forEach(ref => {
      const old = bindings.get(ref);
      if (old) {
        ref.removeEventListener("click", old.click, true);
        if (old.title === null || customTeaser(ref)) ref.removeAttribute("title"); else ref.setAttribute("title", old.title);
        if (old.ariaLabel === null) ref.removeAttribute('aria-label'); else ref.setAttribute('aria-label', old.ariaLabel);
        bindings.delete(ref);
      }
      ref.classList.remove("source-check-issue", "source-check-neutral", "source-check-supported");
      delete ref.dataset.sourceCheck;
    });
    body?.dispatchEvent(new CustomEvent('source-check-updated', {bubbles: true}));
  }
  function status(verification) {
    if (!verification) return "";
    if (verification.status === 'queued') return 'Source check queued';
    if (isPending(verification)) return "Checking sources…";
    if (verification.status === 'awaiting_credentials') return 'Source check needs an API key';
    if (verification.status === "failed") {
      const code = verification.runtime?.error_code
        || (verification.runtime?.error_type === "AnalysisBudgetExceeded" ? "timeout" : "");
      return {timeout: "Source check timed out", output_limit: "Source check response incomplete",
        invalid_output: "Source check response invalid", missing_credential: "Source check needs an API key",
        provider_error: "Source service unavailable"}[code] || "Source check unavailable";
    }
    if (verification.status === "skipped") return "No cited statements";
    const { issues, unknown } = assessment(verification);
    if (issues || unknown) return [issues ? `${issues} source ${issues === 1 ? 'issue' : 'issues'}` : '', unknown ? `${unknown} unclear` : ''].filter(Boolean).join(' · ');
    return coverage(verification).remaining ? 'Source check incomplete' : coverage(verification).checked ? 'Source check complete' : 'No sources checked';
  }
  function compactStatus(verification) {
    const {total, checked, remaining} = coverage(verification);
    if (!total || ['failed', 'awaiting_credentials', 'skipped'].includes(verification.status)) return status(verification);
    const {issues, unknown} = assessment(verification);
    const pending = isPending(verification) ? Math.max(0, total - (verification.scope?.processed_pairs ?? checked)) : 0;
    return `${checked}/${total} checked` + (pending ? ` · ${pending} pending` : '')
      + (remaining > pending ? ` · ${remaining - pending} unavailable` : '')
      + (issues ? ` · ${issues} ${issues === 1 ? 'issue' : 'issues'}` : '')
      + (unknown ? ` · ${unknown} unclear` : '');
  }
  function renderCurrent(verification, options) {
    const rendered = renderSafe(document.getElementById("consensusAnswerBody"), document.getElementById("sourceVerificationReport"), verification, options);
    const label = document.getElementById("consensusSourceCheckStatus");
    const pending = rendered && isPending(verification);
    const tabLabel = document.querySelector("#consensusSourcesTab .consensus-tab-label");
    if (verification?.job_id || verification?.scope?.pairs > 0) {
      const tab = document.getElementById('consensusSourcesTab');
      if (tab) tab.hidden = false;
    }
    tabLabel?.classList.toggle("source-check-loading", pending);
    if (label) {
      const message = rendered && verification ? compactStatus(verification) : "Source check unavailable";
      label.replaceChildren();
      label.classList.remove('source-check-status-reviewed');
      label.classList.toggle('source-check-status-attention', !pending && Boolean(verification) && (assessment(verification).issues > 0 || coverage(verification).remaining > 0));
      label.title = verification ? `${message}. ${coverageText(verification)}.` : message;
      label.setAttribute('aria-label', label.title);
      label.dataset.sourceStatusText = verification ? ' · ' + message : '';
      label.dataset.sourceStatusTitle = label.title;
      label.dataset.sourcePending = String(isPending(verification));
      label.append(element('span', 'source-check-status-copy', verification ? ' · ' + message : ''));
      label.classList.toggle("source-check-status-pending", pending);
      if (verification?.job_id) applyRefreshLabel(verification.job_id, refreshStates.get(verification.job_id));
    }
  }
  function renderSafe(body, target, verification, options) {
    try { render(body, target, verification, options); return true; }
    catch (_) {
      clear(body, target);
      if (target) {
        const error = document.createElement("p");
        error.className = "source-verification";
        error.textContent = "Source check unavailable. Claims and differences are unchanged.";
        target.append(error);
      }
      return false;
    }
    finally { body?.dispatchEvent(new CustomEvent('source-check-updated', {bubbles: true})); }
  }
  function render(body, target, verification, options = {}) {
    if (!body || !target) return;
    const openRows = new Set([...target.querySelectorAll('.source-check-row[open]')].map(row => row.dataset.pair));
    const openDisclosures = new Set([...target.querySelectorAll('details[data-disclosure][open]')].map(node => node.dataset.disclosure));
    const focusedRow = document.activeElement?.closest?.('.source-check-row, details[data-disclosure]');
    const focusKey = focusedRow && target.contains(focusedRow) ? focusedRow.dataset.pair || focusedRow.dataset.disclosure : null;
    const focusOnLink = document.activeElement?.classList.contains('source-check-link');
    clear(body, target, true);
    if (!verification) return;
    const list = body.id === 'consensusAnswerBody' ? document.getElementById('consensusSourcesList')
      : body.closest('.thread-history-turn') ? target.parentElement : (body.matches('.share-md') ? document : null);
    presentations.set(body, {verification, lists: new Set()});
    applySourceList(list, body);
    if (verification.job_id) body.dataset.sourceCheckJob = verification.job_id;
    const box = element("section", "source-verification");
    if (verification.job_id) box.dataset.sourceCheckJob = verification.job_id;
    box.dataset.sourcePending = String(isPending(verification));
    const summary = element("p", "source-verification-status", status(verification));
    summary.setAttribute("role", "status");
    const modern = Number(verification.schema_version) >= 3;
    const scope = coverage(verification);
    const pendingPairs = isPending(verification) ? Math.max(0, scope.total - (verification.scope?.processed_pairs ?? scope.checked)) : 0;
    const unavailablePairs = Math.max(0, scope.remaining - pendingPairs);
    box.append(summary, element('p', 'source-check-coverage', `${scope.checked}/${scope.total} citation checks completed`
      + (pendingPairs ? ` · ${pendingPairs} pending` : '') + (unavailablePairs ? ` · ${unavailablePairs} unavailable` : '')));
    const diagnostics = element('details', 'source-check-diagnostics');
    diagnostics.dataset.disclosure = 'check-details';
    diagnostics.open = openDisclosures.has('check-details');
    diagnostics.append(element('summary', '', 'Check details'), element("p", "source-verification-explanation", modern
      ? 'Evidence for each cited statement · topic & time period. Model agreement is shown separately.'
      : 'Topic relevance & time period · saved check; statement support was not assessed.'));
    diagnostics.append(element('p', 'source-check-coverage-detail', coverageText(verification)));
    box.append(diagnostics);
    target.prepend(box);
    if (focusKey === 'check-details') diagnostics.querySelector('summary').focus({preventScroll: true});
    if (Number(verification.schema_version) >= 3) {
      const reasons = new Map();
      (verification.findings || []).filter(item => item && !item.checked && item.reason_code && !['pending', 'queued'].includes(item.reason_code))
        .forEach(item => reasons.set(item.reason_code, (reasons.get(item.reason_code) || 0) + 1));
      const dominant = [...reasons].sort((a, b) => b[1] - a[1]).slice(0, 3);
      if (dominant.length) diagnostics.append(element('p', 'source-check-failure-summary', dominant.map(([code, count]) => `${reasonLabel(code)} (${count})`).join(' · ')));
    }
    applyRefreshNotice(box, refreshStates.get(verification.job_id));
    if (isPending(verification)) {
      if (!refreshStates.get(verification.job_id)?.terminal) target.setAttribute("aria-busy", "true");
    }
    if (isPending(verification) && !(verification.findings || []).length) {
      const loading = element("div", "source-check-skeleton skeleton-group");
      loading.setAttribute("aria-hidden", "true");
      for (let i = 0; i < 3; i++) {
        const row = element("div", "source-check-skeleton-row");
        row.append(skeleton("source-check-skeleton-title"), skeleton("source-check-skeleton-badge"), skeleton("source-check-skeleton-badge"));
        loading.append(row);
      }
      box.append(loading);
      return;
    }
    if (verification.status === 'skipped') return;
    const findings = Array.isArray(verification.findings) ? verification.findings : [];
    const ids = new Set(findings.map(item => item.sentence_id));
    const panel = element("div", "source-verification-panel");
    box.append(panel);
    if (isPending(verification)) {
      const {issues, unknown} = assessment(verification);
      if (issues || unknown) diagnostics.append(element('p', 'source-check-progress-findings', `${issues} source issues · ${unknown} unclear so far`));
    }
    ids.forEach(id => {
      const group = findings.filter(item => item.sentence_id === id);
      const section = element("section", "source-check-group");
      const claim = element("div", "source-check-claim");
      renderClaim(claim, group[0].claim);
      const statement = element('details', 'source-check-statement');
      statement.dataset.disclosure = `claim:${id}`;
      statement.open = openDisclosures.has(statement.dataset.disclosure);
      const claimSummary = element('summary', 'source-check-statement-summary');
      claimSummary.append(element('span', 'source-check-statement-label', 'Statement'),
        element('span', 'source-check-statement-preview', claim.textContent.replace(/\s+/g, ' ').trim()));
      statement.append(claimSummary, claim);
      section.append(statement);
      const matches = (options.differencesData?.claims || []).filter(item => item
        && item.sentence_id != null && String(item.sentence_id) === String(id));
      if (matches.length === 1 && Array.isArray(matches[0].agree) && Array.isArray(matches[0].dissent)) {
        const evidence = matches[0];
        const dissent = new Set(evidence.dissent.map(item => typeof item === 'string' ? item : item.model).filter(Boolean)).size;
        statement.append(element('p', 'source-check-model-evidence', `Models: ${new Set(evidence.agree).size} agree · ${dissent} dissent. Model agreement does not establish source support.`));
      }
      panel.append(section);
      if (focusKey === statement.dataset.disclosure) claimSummary.focus({preventScroll: true});
      group.forEach(item => {
        const documentData = (verification.documents || []).find(doc => doc.source_id === item.source_id)
          || (verification.sources || []).find(source => source.id === item.source_id);
        const row = element("details", "source-check-row");
        if (modern) row.dataset.sourceCardCheck = findingState(item, verification);
        row.dataset.pair = `${item.sentence_id}:${item.source_id}`;
        row.open = openRows.has(row.dataset.pair);
        const navigation = navigationHighlights.get(target);
        const navigationIdentity = JSON.stringify([verification.job_id || '', verification.answer_version || '', item.claim]);
        if (navigation?.pair === row.dataset.pair && navigation.identity === navigationIdentity && navigation.until > Date.now()) row.classList.add('source-check-navigation-target');
        const heading = element("summary", "source-check-row-summary");
        const source = element("span", "source-check-source");
        source.append(element('span', 'source-check-reference', item.source_id));
        let url;
        try {
          const parsed = new URL(documentData?.source_url || documentData?.url);
          if (["https:", "http:"].includes(parsed.protocol)) url = parsed;
        } catch (_) { /* malformed legacy source */ }
        const domain = element("span", "source-check-domain", url ? url.hostname.replace(/^www\./, "") : 'Source unavailable');
        domain.title = documentData?.title || domain.textContent;
        source.append(domain);
        heading.append(source);
        const topical = item.checked && item.topical;
        const temporal = item.checked && item.temporal;
        const topicLabel = {relevant: "Topic matches", off_topic: "Off topic", unknown: "Topic unclear"}[topical] || "Topic unchecked";
        const timeLabel = {suitable: "Time matches", outdated: "Wrong time period", unknown: "Time unclear", not_relevant: "Timeless"}[temporal] || "Time unchecked";
        const badges = element("span", "source-check-badges");
        if (!item.checked) {
          badges.append(element('span', 'source-check-badge is-unchecked', isPending(verification) && (!item.reason_code || ['queued', 'pending'].includes(item.reason_code)) ? 'Pending' : 'Not checked'));
        } else {
          if (modern) {
            const contextIssue = item.support === 'supported' && (topical === 'off_topic' || temporal === 'outdated');
            const contextUnknown = item.support === 'supported' && findingState(item, verification) === 'unknown';
            const verdict = contextIssue ? (topical === 'off_topic' ? 'Off topic' : 'Wrong time period') : contextUnknown ? 'Context unclear'
              : {supported: 'Statement supported', partial: 'Partly supported', contradicted: 'Statement contradicted', unknown: 'Support unclear'}[item.support] || 'Support unclear';
            badges.append(element('span', 'source-check-badge ' + (contextIssue ? 'is-issue' : contextUnknown ? 'is-unclear'
              : {supported: 'is-match', partial: 'is-issue', contradicted: 'is-issue'}[item.support] || 'is-unclear'), verdict));
          }
          else badges.append(element('span', 'source-check-badge is-unclear', 'Saved topic check'));
        }
        heading.append(badges);
        row.append(heading);
        const detail = element("div", "source-check-detail");
        if (item.checked) {
          const context = element('div', 'source-check-context');
          context.append(element("span", "source-check-badge" + (topical === "off_topic" ? " is-issue" : topical === 'relevant' ? ' is-match' : ' is-unclear'), topicLabel),
            element("span", "source-check-badge" + (temporal === "outdated" ? " is-issue" : ['suitable', 'not_relevant'].includes(temporal) ? ' is-match' : ' is-unclear'), timeLabel));
          detail.append(context);
        }
        const sourceRecord = (verification.sources || []).find(source => source.id === item.source_id);
        const providers = [...new Set((sourceRecord?.providers || documentData?.providers || []).filter(name => typeof name === 'string'))];
        if (providers.length) detail.append(element('p', 'source-check-model-evidence',
          `Cited by: ${providers.join(', ')}${providers.length > 1 ? ' · Shared source; these are not independent documents.' : ''}`));
        // Old support verdicts are not topical-fit results. Never relabel an
        // old disagreement as an off-topic source or display its fact-check prose.
        const reason = item.topical || modern ? String(item.reason || "").slice(0, 1000)
          : "No topic check is available for this saved source.";
        if (reason) detail.append(element("p", "source-check-reason", reason));
        if (item.reason_code && reason !== reasonLabel(item.reason_code)) detail.append(element('p', 'source-check-reason-category', reasonLabel(item.reason_code)));
        else if (!item.reason_code && !item.checked && !isPending(verification)) detail.append(element("p", "source-check-reason", modern ? 'This source could not be checked.' : 'Saved check incomplete; no specific failure reason was recorded.'));
        if ((item.topical || modern) && (item.quotes || []).length) detail.append(element('p', 'source-check-passage-label', 'Original source passage'));
        if (item.topical || modern) (item.quotes || []).slice(0, 4).forEach(quote => {
          detail.append(element("blockquote", "source-check-quote", String(quote).slice(0, 2000)));
        });
        const checkedAt = item.checked ? item.checked_at || verification.checked_at : documentData?.fetched_at;
        if (checkedAt && Number.isFinite(new Date(checkedAt).getTime())) {
          const stamp = element('time', 'source-check-date', `${item.checked ? 'Checked' : 'Retrieved'}: ${new Date(checkedAt).toLocaleString()}`);
          stamp.dateTime = new Date(checkedAt).toISOString(); detail.append(stamp);
        }
        const date = documentData?.dates?.[0];
        if (date?.value) detail.append(element("p", "source-check-date", `Document date: ${date.value}`));
        if (url) {
          const link = element("a", "source-check-link", "Open source ↗");
          link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
          detail.append(link);
        }
        row.append(detail);
        section.append(row);
        if (focusKey === row.dataset.pair) (focusOnLink ? row.querySelector('.source-check-link') || heading : heading).focus({preventScroll: true});
        if (modern || notable(item)) mark(body, item, verification, () => {
          const turn = body.closest(".thread-history-turn");
          if (!body.closest(".share-md") && window.App.answerReader?.openPanel) {
            window.App.answerReader.openPanel("sources", null, turn);
          } else {
            const drawer = target.closest("[hidden]");
            if (drawer) drawer.hidden = false;
          }
          row.open = true;
          highlightRow(target, row, navigationIdentity);
          heading.scrollIntoView?.({ block: "nearest", behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
        });
      });
    });
  }
  function mark(body, item, verification, open) {
    const strip = text => {
      const el = document.createElement("div");
      if (window.marked && window.DOMPurify) {
        el.innerHTML = window.DOMPurify.sanitize(window.marked.parse(String(text)));
        return el.textContent;
      }
      return String(text).replace(/[*_`~]/g, "");
    };
    const anchor = window.App.consensusAnchor?.create(strip);
    const text = strip(item.claim).replace(/\[S?\d+(?:\s*,\s*S?\d+)*\]/gi, " ").replace(/\s+([.,;:!?])/g, "$1").trim();
    const hit = anchor?.locateAnchor(body, text, item.anchor_occurrence || 0);
    if (!hit || anchor.normalizeForSearch(hit.flat.slice(hit.start, hit.end)) !== anchor.normalizeForSearch(text)) return;
    const slices = hit.slices.filter(slice => slice.end > hit.start && slice.start < hit.end);
    if (!slices.length) return;
    const first = slices[0], last = slices[slices.length - 1];
    const range = document.createRange();
    range.setStart(first.node, Math.max(0, hit.start - first.start));
    range.setEnd(last.node, Math.min(last.node.length, hit.end - last.start));
    const refSelector = '.src-ref, .source-link, a[href^="#src-"]';
    const refs = new Set(Array.from(body.querySelectorAll(refSelector)).filter(ref => range.intersectsNode(ref)));
    // Include terminal citations after the sentence, stopping before any new prose.
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    walker.currentNode = last.node;
    if (!last.node.nodeValue.slice(Math.min(last.node.length, hit.end - last.start)).trim()) {
      let node;
      while ((node = walker.nextNode())) {
        if (node.nodeType === 1 && node.matches(refSelector)) refs.add(node);
        if (node.nodeType === 3 && node.nodeValue.trim()
          && !node.parentElement.closest(`${refSelector}, .src-ref-sep, .claim-badge`)) break;
      }
    }
    const number = String(item.source_id).replace(/^S/i, "");
    refs.forEach(ref => {
      const refNumber = ref.dataset.sourceNumber || ref.getAttribute("href")?.match(/^#src-(\d+)$/)?.[1]
        || ref.textContent.trim().replace(/^S/i, "");
      if (refNumber !== number || bindings.has(ref)) return;
      const state = findingState(item, verification);
      const issue = ['issue', 'contradicted'].includes(state);
      const click = event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button > 0) return;
        event.preventDefault(); event.stopImmediatePropagation(); open();
      };
      const check = citationCheck(item, verification);
      bindings.set(ref, { title: ref.getAttribute("title"), ariaLabel: ref.getAttribute('aria-label'), click, check });
      ref.dataset.sourceCheck = state;
      ref.classList.add(issue ? "source-check-issue" : state === 'supported' ? 'source-check-supported' : "source-check-neutral");
      const label = ref.getAttribute('aria-label') || ref.title || item.source_id;
      ref.setAttribute('aria-label', `${label}. ${check.summary}`);
      if (customTeaser(ref)) ref.removeAttribute('title');
      else ref.title = `${ref.title || item.source_id} — ${stateLabels[state]}. See Verify sources for details.`;
      ref.addEventListener("click", click, true);
    });
  }
  function reasonLabel(code) {
    return { pending: 'Waiting for a check', queued: 'Waiting for capacity', fetch_failed: 'Source could not be retrieved',
      fetch_error: 'Source could not be retrieved', unavailable: 'Source unavailable', robots_denied: 'Website disallows access',
      timeout: 'Request timed out', blocked_url: 'Source URL cannot be accessed', unsafe_url: 'Source URL cannot be accessed',
      unsupported_content: 'Document format unavailable', empty_document: 'No readable source text',
      missing_source: 'Citation has no source URL', ambiguous_source: 'Citation refers to multiple sources',
      missing_credential: 'An API key is required', provider_error: 'Checking service unavailable',
      invalid_output: 'The checking service returned an invalid result', output_limit: 'The checking service returned an incomplete result',
      fetch_timeout: 'Source retrieval timed out', access_denied: 'Website denied access', not_found: 'Source was not found',
      rate_limited: 'Website temporarily limits requests', upstream_error: 'Website returned an error',
      unsafe_address: 'Source address cannot be accessed', dns_busy: 'Source address lookup temporarily unavailable',
      unsupported_document: 'Document format unavailable', unsupported_encoding: 'Document encoding unavailable',
      incomplete_document: 'The retrieved document is incomplete', redirect_limit: 'Too many website redirects',
      network_error: 'Source retrieval failed', claim_limit: 'Statement exceeds the supported check size',
      input_limit: 'Document and statement exceed the supported check size',
      evidence_not_found: 'No matching evidence found', quote_not_found: 'Source passage could not be verified',
      evidence_mismatch: 'Evidence quotes could not be verified',
      unknown: 'Evidence is inconclusive' }[code] || 'Check could not be completed (' + String(code).replace(/[^a-zA-Z0-9_ -]/g, '').slice(0, 80).replace(/_/g, ' ') + ')';
  }

  // The caller owns the run/turn and credentials. This helper never reads App state.
  // Each cycle publishes only after reading a consistent, complete set of pages.
  function watch({ jobId, url, getToken, onUpdate, isActive, onError } = {}) {
    let endpoint;
    try { endpoint = new URL(url || `/api/source-checks/${encodeURIComponent(jobId || '')}`, window.location.origin); }
    catch (_) { throw new Error('Invalid source check URL'); }
    if (endpoint.origin !== window.location.origin || (!jobId && !url)) throw new Error('Invalid source check URL');
    if (typeof onUpdate !== 'function' || typeof isActive !== 'function') throw new Error('A bound source check callback is required');
    let stopped = false, timer = null, controller = null, running = false, failures = 0, unchanged = 0, previous = null;
    const active = () => !stopped && isActive();
    function stop() {
      stopped = true;
      window.clearTimeout(timer);
      controller?.abort();
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('pagehide', stop);
    }
    function schedule(delay) { if (active()) timer = window.setTimeout(poll, delay); else stop(); }
    function visibility() {
      window.clearTimeout(timer);
      if (!active()) return stop();
      if (!document.hidden && !running) schedule(0);
    }
    async function poll() {
      if (!active()) return stop();
      if (document.hidden) return;
      running = true;
      controller = new AbortController();
      const timeout = window.setTimeout(() => controller?.abort(), 45000);
      try {
        const headers = { Accept: 'application/json' };
        if (getToken) {
          const token = await getToken();
          if (!token) throw new Error('Source check authentication unavailable');
          headers.Authorization = `Bearer ${token}`;
        }
        let cursor = null, snapshot = null, revision = null, sameRevision = false;
        const seen = new Set(), findings = new Map(), documents = new Map(), sources = new Map();
        do {
          if (!active()) return stop();
          const requestUrl = new URL(endpoint.href);
          if (cursor != null) requestUrl.searchParams.set('cursor', String(cursor));
          else if (previous?.revision != null) requestUrl.searchParams.set('after_revision', String(previous.revision));
          if (revision != null) requestUrl.searchParams.set('revision', String(revision));
          const response = await window.fetch(requestUrl.href, { headers, cache: 'no-store', credentials: 'same-origin', signal: controller.signal });
          if (!response.ok) {
            const error = new Error('Source check refresh failed'); error.status = response.status; throw error;
          }
          const page = await response.json();
          let value = page.source_verification;
          if (!value || typeof value !== 'object' || (jobId && value.job_id && value.job_id !== jobId)) throw new Error('Invalid source check snapshot');
          if (snapshot && (value.revision !== revision || value.answer_version !== snapshot.answer_version)) {
            const error = new Error('Source check changed during refresh'); error.status = 409; throw error;
          }
          if (!snapshot) { snapshot = value; revision = value.revision ?? null; }
          // Revision covers the entire job. If it did not change, avoid reading
          // every persisted finding page again just to repaint the same result.
          sameRevision = previous && revision != null && previous.revision === revision
            && previous.answer_version === value.answer_version && previous.status === value.status;
          if (sameRevision) value = {...value, findings: previous.findings, documents: previous.documents, sources: previous.sources};
          for (const item of value.findings || []) if (item) findings.set(`${item.sentence_id}:${item.source_id}`, item);
          for (const item of value.documents || []) if (item) documents.set(item.source_id, item);
          for (const item of value.sources || []) if (item) sources.set(item.id || item.source_id, item);
          cursor = sameRevision ? null : page.next_cursor ?? null;
          if (cursor != null) {
            if (seen.has(String(cursor)) || seen.size >= 1000) throw new Error('Invalid source check pagination');
            seen.add(String(cursor));
          }
        } while (cursor != null);
        if (!active()) return stop();
        // Some in-progress summaries carry only updated findings. Keep completed
        // evidence for the same answer until the full terminal snapshot arrives.
        if (previous && isPending(snapshot) && previous.answer_version === snapshot.answer_version) {
          for (const item of previous.findings || []) {
            const key = `${item.sentence_id}:${item.source_id}`;
            if (!findings.has(key)) findings.set(key, item);
          }
          for (const item of previous.documents || []) if (!documents.has(item.source_id)) documents.set(item.source_id, item);
          for (const item of previous.sources || []) if (!sources.has(item.id || item.source_id)) sources.set(item.id || item.source_id, item);
        }
        previous = { ...snapshot, findings: [...findings.values()], documents: [...documents.values()], sources: [...sources.values()] };
        setRefreshState(jobId || snapshot.job_id, null);
        unchanged = sameRevision ? Math.min(unchanged + 1, 5) : 0;
        if (!sameRevision) onUpdate(previous);
        failures = 0;
        if (!isPending(snapshot)) return stop();
      } catch (error) {
        if (!active()) return stop();
        failures = error.status === 409 ? 0 : Math.min(failures + 1, 5);
        noteRefreshError(jobId || previous?.job_id, error, failures);
        onError?.(error);
        if ([401, 403, 404, 410].includes(error.status)) return stop();
      } finally {
        running = false;
        window.clearTimeout(timeout);
        controller = null;
      }
      if (!document.hidden) schedule(Math.min(30000, 1500 * Math.pow(2, Math.max(failures, unchanged))));
    }
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('pagehide', stop);
    schedule(0);
    return stop;
  }
  function observe({ snapshot, auth, isActive, onUpdate, useOwnKeys = false, getOwnKey, onError } = {}) {
    if (!snapshot?.job_id || !auth?.user || !auth.uid) return () => {};
    const jobId = snapshot.job_id;
    let stopped = false, stopWatch = null, resumeController = null, attemptedResume = false;
    const active = () => !stopped && window.auth?.currentUser === auth.user
      && window.auth?.currentUser?.uid === auth.uid
      && (auth.generation == null || window.App.authState?.generation === auth.generation)
      && isActive();
    function stop() {
      stopped = true; stopWatch?.(); resumeController?.abort();
      window.removeEventListener('consensio:auth-state', validate);
      window.removeEventListener('consensio:run-registry-change', validate);
      window.removeEventListener('pagehide', stop);
    }
    function validate() { if (!active()) stop(); }
    function begin() {
      if (!active()) return stop();
      stopWatch = watch({ jobId, getToken: () => auth.user.getIdToken(), isActive: active,
        onError(error) { onError?.(error); if ([401, 403, 404, 410].includes(error.status)) stop(); },
        onUpdate(value) {
          if (!active()) return stop();
          snapshot = value; onUpdate(value);
          if (value.status === 'awaiting_credentials' && !attemptedResume
            && (useOwnKeys || value.credential_mode === 'own')) {
            let key = '';
            try { key = String(getOwnKey?.() || '').trim(); } catch (_) {}
            if (!key) return stop();
            attemptedResume = true;
            // Keep the credential only in this short-lived request, never in a
            // run, bookmark, source snapshot, DOM attribute or persisted store.
            void resume(key);
          } else if (!isPending(value)) {
            stop();
          }
        }
      });
    }
    async function resume(key) {
      resumeController = new AbortController();
      const timeout = window.setTimeout(() => resumeController?.abort(), 15000);
      try {
        const token = await auth.user.getIdToken();
        if (!active()) return stop();
        const response = await window.fetch(`/api/source-checks/${encodeURIComponent(jobId)}/resume`, {
          method: 'POST', headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'},
          body: JSON.stringify({openrouter_key: key}), signal: resumeController.signal, cache: 'no-store'
        });
        if (!response.ok) throw new Error('Source check could not resume');
        if (active()) begin();
      } catch (error) {
        if (active()) {
          setRefreshState(jobId, {terminal: true, label: 'Resume unavailable',
            message: 'The source check could not resume. Check your API key and reopen this saved comparison. The last received results are shown.'});
          onError?.(error);
        }
      }
      finally { key = ''; window.clearTimeout(timeout); resumeController = null; }
    }
    window.addEventListener('consensio:auth-state', validate);
    window.addEventListener('consensio:run-registry-change', validate);
    window.addEventListener('pagehide', stop);
    begin();
    return stop;
  }
  window.App.sourceVerification = Object.freeze({ render: renderSafe, renderCurrent, clear, applySourceList, getCitationCheck, watch, observe });
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-source-verification]").forEach(root => {
      try {
        const body = root.querySelector('.share-md');
        const report = document.getElementById('shareSourceVerificationReport');
        const snapshot = JSON.parse(root.dataset.sourceVerification);
        const options = {differencesData: (() => { try { return JSON.parse(root.dataset.differencesData || '{}'); } catch (_) { return {}; } })()};
        render(body, report, snapshot, options);
        if (root.dataset.sourceCheckUrl) watch({jobId: snapshot?.job_id, url: root.dataset.sourceCheckUrl,
          isActive: () => root.isConnected && body?.isConnected && report?.isConnected,
          onUpdate: value => renderSafe(body, report, value, options)});
      } catch (_) { /* old or missing snapshot */ }
    });
  });
})();
