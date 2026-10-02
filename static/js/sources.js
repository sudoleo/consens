// =====================================================================
// sources.js
// Evidence-/Quellen-Tags: Chips, [S1]-Linkifizierung, Merge & Rewrite der
// Quell-IDs ueber alle Modellantworten hinweg.
// Extrahiert aus templates/index.html (initApp-Closure).
// Exporte: window.linkifySourceTags, window.mergeEvidenceSources,
// window.rewriteSourceTags, window.registerResponseSources,
// window.prepareResponseSources, window.renderModelResponseWithSources.
// Call-time-Abhaengigkeiten: window.injectMarkdown, window.renderEvidenceSources,
// window.currentEvidenceSources (geteilter State).
// =====================================================================

function getSourceSiteName(src) {
  const rawUrl = src && src.url ? String(src.url) : "";
  if (!rawUrl && !(src && src.title)) return "";
  try {
    const url = new URL(rawUrl);
    const hostParts = url.hostname
      .toLowerCase()
      .replace(/^(www|m|amp)\./, "")
      .split(".");
    const sldSuffixes = new Set(["co", "com", "org", "net", "ac", "gov"]);
    const nameIndex = hostParts.length >= 3 && sldSuffixes.has(hostParts[hostParts.length - 2])
      ? hostParts.length - 3
      : hostParts.length - 2;
    return hostParts[Math.max(0, nameIndex)] || rawUrl;
  } catch (e) {
    return (src && (src.title || src.url)) ? String(src.title || src.url) : "source";
  }
}

function getSafeSourceHref(src) {
  if (!src || !src.url) return "";
  try {
    const url = new URL(String(src.url));
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (e) {
    return "";
  }
}

function getSourceTitle(src, fallbackLabel) {
  return (src && (src.title || src.url)) ? String(src.title || src.url) : fallbackLabel;
}

function getSourceHost(src) {
  if (!src || !src.url) return "";
  try {
    return new URL(String(src.url)).hostname.replace(/^www\./, "");
  } catch (e) {
    return "";
  }
}

// Mirror the public Topic/Share pages: prepend a real site favicon (fetched
// through our privacy-preserving proxy) so inline citation chips carry the
// source's identity, not just its name. The icon is decorative; if it fails to
// load we drop it and the chip falls back to text only.
function prependSourceFavicon(el, src) {
  const host = getSourceHost(src);
  if (!host) return;
  const fav = document.createElement("img");
  fav.className = "source-favicon";
  fav.src = "/api/topics/favicon?d=" + encodeURIComponent(host);
  fav.alt = "";
  fav.setAttribute("aria-hidden", "true");
  fav.setAttribute("referrerpolicy", "no-referrer");
  fav.loading = "lazy";
  fav.width = 13;
  fav.height = 13;
  fav.addEventListener("error", function () {
    fav.remove();
    el.classList.remove("has-favicon");
  });
  el.insertBefore(fav, el.firstChild);
  el.classList.add("has-favicon");
}

function createSourceChip(src, fallbackLabel) {
  const href = getSafeSourceHref(src);
  const el = href ? document.createElement("a") : document.createElement("span");
  el.className = "source-link";
  el.textContent = getSourceSiteName(src) || fallbackLabel;
  el.title = getSourceTitle(src, fallbackLabel);
  el.setAttribute("aria-label", `Source: ${el.title}`);

  if (href) {
    el.href = href;
    el.target = "_blank";
    el.rel = "noopener noreferrer";
  }

  prependSourceFavicon(el, src);

  return el;
}

function getSourceRefs(sourceText, sources) {
  const refs = [];
  const sourceTagRegex = /\[((?:S?\d+)(?:,\s*S?\d+)*)\]/g;
  const sourceList = Array.isArray(sources) ? sources : [];
  const normalizeId = value => {
    const match = String(value ?? '').trim().match(/^S?(\d+)$/i);
    return match ? Number(match[1]) : null;
  };

  String(sourceText || "").replace(sourceTagRegex, (match, innerContent) => {
    innerContent.split(",").forEach(part => {
      const token = part.trim();
      const idNum = parseInt(token.replace(/^S/i, ""), 10);
      const matches = sourceList.filter(source => source && normalizeId(source.id ?? source.source_id) === idNum);
      const legacy = sourceList[idNum - 1];
      refs.push({
        token,
        // Explicit IDs are authoritative, including sparse catalogs. Duplicate
        // IDs stay unresolved; a reserved missing ID must not borrow its neighbor.
        src: matches.length === 1 ? matches[0] : matches.length ? null
          : legacy && legacy.id == null && legacy.source_id == null ? legacy : null
      });
    });
    return match;
  });

  return refs;
}

function appendInlineSourceRefs(fragment, refs) {
  refs.forEach((ref, idx) => {
    if (idx > 0) fragment.appendChild(document.createTextNode(" "));
    fragment.appendChild(createSourceChip(ref.src, ref.token));
  });
}

// --- Source pills in chat prose ---------------------------------------------
// Consensus and Agent answers are prose. A citation there is a quiet inline
// pill: favicon + short domain, baseline-aligned, so the reader sees WHICH
// source backs a sentence without decoding a footnote number. Adjacent
// citations collapse into one pill ("njaped.no +2"); the hover/focus teaser
// lists all of them. The display number stays on the element
// (data-source-number / data-source-numbers) — the sources drawer, source
// verification and the teaser index still address sources by it.
// Model answers keep their own `.source-link` chips (scannable evidence).

function sourceNumberFromToken(token) {
  const num = parseInt(String(token || "").replace(/^S/i, ""), 10);
  return Number.isFinite(num) && num > 0 ? num : null;
}

// Short, readable domain for the pill: the host without "www.".
function getSourcePillLabel(src, token) {
  const host = getSourceHost(src);
  if (host) return host;
  if (src && src.title) return String(src.title);
  const number = sourceNumberFromToken(token);
  return number ? `Source ${number}` : String(token || "Source");
}

// Neutral monogram for sources without (or with a failed) favicon: never a
// broken-image icon. The proxy itself answers unknown hosts with a globe.
function createSourceGlyph(label) {
  const glyph = document.createElement("span");
  glyph.className = "src-ref-glyph";
  glyph.setAttribute("aria-hidden", "true");
  const letter = String(label || "").match(/[\p{L}\p{N}]/u);
  glyph.textContent = letter ? letter[0].toUpperCase() : "·";
  return glyph;
}

function createSourceRefIcon(src, label) {
  const host = getSourceHost(src);
  if (!host) return createSourceGlyph(label);
  // Same privacy-preserving proxy as the model-answer chips and the public
  // pages: the browser only ever talks to consens.io.
  const fav = document.createElement("img");
  fav.className = "src-ref-favicon";
  fav.src = "/api/topics/favicon?d=" + encodeURIComponent(host);
  fav.alt = "";
  fav.setAttribute("aria-hidden", "true");
  fav.setAttribute("referrerpolicy", "no-referrer");
  fav.loading = "lazy";
  fav.decoding = "async";
  fav.width = 14;
  fav.height = 14;
  fav.addEventListener("error", () => {
    if (fav.isConnected || fav.parentNode) fav.replaceWith(createSourceGlyph(label));
  });
  return fav;
}

// Entries: [{src, number, token}] in citation order, unique by number/token.
function sourceRefEntries(refs) {
  const entries = [];
  const seen = new Set();
  (refs || []).forEach(ref => {
    if (!ref) return;
    const number = ref.number != null ? sourceNumberFromToken(ref.number) : sourceNumberFromToken(ref.token);
    const key = number || String(ref.token || "");
    if (seen.has(key)) return;
    seen.add(key);
    entries.push({ src: ref.src || null, number, token: ref.token != null ? String(ref.token) : String(number || "") });
  });
  return entries;
}

function sourceRefAriaLabel(entries) {
  const first = entries[0] || {};
  const label = getSourcePillLabel(first.src, first.token);
  const more = entries.length - 1;
  return more > 0 ? `Source: ${label} (and ${more} more)` : `Source: ${label}`;
}

// (Re)builds the pill's content in place. Keeping the element lets a focused
// or hovered pill survive streamed re-renders.
function fillSourceRef(el, refs, options = {}) {
  const entries = sourceRefEntries(refs);
  if (!entries.length) return el;
  const first = entries[0];
  const label = getSourcePillLabel(first.src, first.token);
  const href = getSafeSourceHref(first.src);
  el.replaceChildren();
  el.append(createSourceRefIcon(first.src, label));
  const text = document.createElement("span");
  text.className = "src-ref-label";
  text.textContent = label;
  el.append(text);
  if (entries.length > 1) {
    const more = document.createElement("span");
    more.className = "src-ref-more";
    more.textContent = `+${entries.length - 1}`;
    el.append(more);
  }
  const compact = options.compact ?? el.classList.contains("is-compact");
  el.classList.toggle("is-compact", Boolean(compact));
  el.classList.toggle("is-group", entries.length > 1);
  el.dataset.sourceNumber = first.number ? String(first.number) : "";
  if (entries.length > 1) el.dataset.sourceNumbers = entries.map(entry => entry.number || entry.token).join(" ");
  else delete el.dataset.sourceNumbers;
  // The styled teaser also opens on keyboard focus. A title would produce a
  // second browser tooltip after a long hover.
  el.removeAttribute("title");
  el.setAttribute("aria-label", sourceRefAriaLabel(entries));
  // Die Nummer allein ist keine Identitaet: ein archivierter Turn nummeriert
  // seine EIGENE Quellenliste, waehrend window.currentEvidenceSources schon
  // dem naechsten Lauf gehoert. Der Teaser liest deshalb die aufgeloesten
  // Quellen vom Element und nicht noch einmal die Nummer nach.
  el.sourceData = first.src || null;
  el.sourceGroup = entries;
  if (href && el.tagName === "A") {
    el.href = href;
    el.target = "_blank";
    el.rel = "noopener noreferrer";
  }
  return el;
}

function createSourceRef(refs, options = {}) {
  const list = Array.isArray(refs) ? refs : [refs];
  const entries = sourceRefEntries(list);
  const href = getSafeSourceHref(entries[0]?.src);
  const el = href ? document.createElement("a") : document.createElement("span");
  el.className = "src-ref";
  if (!href) el.tabIndex = 0;
  return fillSourceRef(el, entries, options);
}

function appendNumberedSourceRefs(fragment, refs, options = {}) {
  if (!refs || !refs.length) return;
  // An unresolved ID does not get a domain of its own inside a pill that has
  // real sources; alone it still shows where the model cited something.
  const resolved = refs.filter(ref => ref && ref.src);
  fragment.appendChild(createSourceRef(resolved.length ? resolved : refs, options));
}

// Plain-text form for copy paths: "(njaped.no, uci.org)". A compact pill's
// first domain is already written in the sentence before it.
function sourceRefPlainText(ref) {
  const entries = ref?.sourceGroup?.length ? ref.sourceGroup
    : [{ src: ref?.sourceData || null, token: ref?.dataset?.sourceNumber || ref?.textContent || "" }];
  const labels = entries.map(entry => getSourcePillLabel(entry.src, entry.token));
  const shown = ref?.classList?.contains("is-compact") ? labels.slice(1) : labels;
  const unique = [...new Set(shown.filter(Boolean))];
  return unique.length ? ` (${unique.join(", ")})` : "";
}

function sourceRefUrls(ref) {
  const entries = ref?.sourceGroup?.length ? ref.sourceGroup : [{ src: ref?.sourceData || null }];
  return entries.map(entry => getSafeSourceHref(entry.src)).filter(Boolean);
}

// Is the cited domain already written right before the citation ("über
// njaped.no [S1]")? Then the pill shows only the favicon: no duplicate, and
// the model's prose stays untouched (anchors and claim marks still match).
function textEndsWithSourceHost(text, src) {
  const host = getSourceHost(src);
  if (!host || !text) return false;
  const escaped = host.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?:^|[\\s(\\[{"'„“«/])(?:https?://)?(?:www\\.)?${escaped}/?[.,;:!?]*\\s*$`, "i").test(text);
}

// Does a link's visible label just repeat its own domain ("[njaped.no](https://njaped.no/)")?
function labelIsSourceHost(label, src) {
  const host = getSourceHost(src);
  if (!host) return false;
  const value = String(label || "").trim().toLowerCase()
    .replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/$/, "");
  return value === host.toLowerCase();
}

// Agent prose: separate links/tags that end up side by side ("[S1][S2]",
// "url1, url2") become one pill. Only whitespace, commas and semicolons may
// stand between them — anything else is prose and keeps them apart.
function mergeAdjacentSourceRefs(containerEl) {
  const refs = Array.from(containerEl.querySelectorAll(".src-ref"));
  const removed = new Set();
  refs.forEach(ref => {
    if (removed.has(ref) || !ref.isConnected) return;
    let group = ref.sourceGroup || [];
    const between = [];
    let node = ref.nextSibling;
    let merged = false;
    while (node) {
      if (node.nodeType === Node.TEXT_NODE && /^[\s,;]*$/.test(node.nodeValue)) {
        between.push(node);
        node = node.nextSibling;
        continue;
      }
      if (node.nodeType === Node.ELEMENT_NODE && node.classList.contains("src-ref-sep")) {
        between.push(node);
        node = node.nextSibling;
        continue;
      }
      if (node.nodeType === Node.ELEMENT_NODE && node.classList.contains("src-ref") && !removed.has(node)) {
        group = group.concat(node.sourceGroup || []);
        between.forEach(item => item.remove());
        between.length = 0;
        removed.add(node);
        const next = node.nextSibling;
        node.remove();
        merged = true;
        node = next;
        continue;
      }
      break;
    }
    if (merged) fillSourceRef(ref, group);
    unwrapCitationParens(ref);
  });
}

// "(url1, url2)" ended as "(pill)": brackets that hold nothing but the
// citation go, and a terminal citation follows the sentence punctuation —
// the same rule a single bracketed URL already gets.
function unwrapCitationParens(ref) {
  const before = ref.previousSibling;
  const after = ref.nextSibling;
  if (before?.nodeType !== Node.TEXT_NODE || after?.nodeType !== Node.TEXT_NODE) return;
  if (!/\(\s*$/.test(before.nodeValue) || !/^\s*\)/.test(after.nodeValue)) return;
  before.nodeValue = before.nodeValue.replace(/[ \t]*\(\s*$/, "");
  after.nodeValue = after.nodeValue.replace(/^\s*\)/, "");
  const punctuation = after.nodeValue.match(/^([.!?]+)(?=\s|$)/);
  if (punctuation) {
    before.nodeValue += punctuation[1];
    after.nodeValue = after.nodeValue.slice(punctuation[1].length);
  }
}

// Die Quellen-Pille gehoert dem Konsens-Fliesstext — und der hat mehr
// als eine Adresse: die ID gibt es nur einmal (der Live-Lauf), die Klasse
// tragen auch die archivierten Turns im Thread. Die Kernaussagen-Liste
// darunter zitiert woertlich denselben Text und muss deshalb dieselbe Form
// sprechen; ein `.source-link`-Chip mitten in einer Claim-Zeile waere ein
// zweites Vokabular fuer dieselbe Quelle.
const NUMBERED_REF_SELECTOR =
  "#consensusAnswerBody, .consensus-answer-body, .consensus-claims-fallback";

function wantsNumberedRefs(containerEl) {
  if (!containerEl || typeof containerEl.closest !== "function") return false;
  return Boolean(
    containerEl.matches?.(NUMBERED_REF_SELECTOR)
    || containerEl.closest(NUMBERED_REF_SELECTOR)
    || containerEl.querySelector?.(NUMBERED_REF_SELECTOR)
  );
}

// Modelle setzen Quellen-Tags nicht immer typografisch korrekt: häufig kommt
// `[S1].`, obwohl eine Fussnote am Satzende hinter Punkt/Frage-/Ausrufezeichen
// steht. Normalisiert nur echte Satzendzeichen und lässt Code sowie
// satzinterne Referenzen unangetastet.
function normalizeTerminalSourceTagOrder(markdown) {
  const sourceRun = String.raw`\[((?:S?\d+)(?:,\s*S?\d+)*)\]`;
  const pattern = new RegExp(
    String.raw`[ \t]*(${sourceRun})([.!?]+(?:["'”’)\]}]+)?)(?=\s|$)`,
    "gi"
  );
  return String(markdown || "").replace(pattern, "$3$1");
}

function createSourceListCluster(refs) {
  const uniqueRefs = [];
  const seen = new Set();

  refs.forEach(ref => {
    const key = normalizeEvidenceUrl(ref.src && ref.src.url) || String(ref.src?.title || ref.token || "").trim().toLowerCase();
    if (key && seen.has(key)) return;
    if (key) seen.add(key);
    uniqueRefs.push(ref);
  });

  const details = document.createElement("details");
  details.className = "source-list-cluster";
  details.open = true;

  const summary = document.createElement("summary");
  summary.className = "source-list-summary";
  summary.textContent = `${uniqueRefs.length} sources`;
  details.appendChild(summary);

  const list = document.createElement("ol");
  list.className = "source-list";

  uniqueRefs.forEach(ref => {
    const item = document.createElement("li");
    item.className = "source-list-item";

    const href = getSafeSourceHref(ref.src);
    const title = getSourceTitle(ref.src, ref.token);
    const link = href ? document.createElement("a") : document.createElement("span");
    link.className = "source-list-link";
    link.textContent = title;
    link.title = title;

    if (href) {
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }

    item.appendChild(link);

    const siteName = getSourceSiteName(ref.src);
    if (siteName && siteName !== title) {
      const meta = document.createElement("span");
      meta.className = "source-list-meta";
      meta.textContent = siteName;
      item.appendChild(meta);
    }

    list.appendChild(item);
  });

  details.appendChild(list);
  return details;
}

function linkifySourceTags(containerEl, sources) {
  if (!containerEl || !sources || !sources.length) return;
  // New consensus prose has no source-reference syntax. In particular, a
  // mathematical/numeric [1] must not acquire a citation from the model catalogue.
  // Original model answers and saved legacy consensus keep their own links.
  if (containerEl.closest?.('[data-source-references="none"]')) return;

  const numbered = wantsNumberedRefs(containerEl);
  const ignoredParents = new Set(["A", "CODE", "PRE", "SCRIPT", "STYLE", "TEXTAREA"]);
  const sourceRunRegex = /(?:\[((?:S?\d+)(?:,\s*S?\d+)*)\](?:[\s,;:]*(?=\[S?\d))?)+/gi;
  const sourceGroupThreshold = 6;
  const walker = document.createTreeWalker(containerEl, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!sourceRunRegex.test(node.nodeValue || "")) {
        sourceRunRegex.lastIndex = 0;
        return NodeFilter.FILTER_REJECT;
      }
      sourceRunRegex.lastIndex = 0;
      let parent = node.parentElement;
      while (parent && parent !== containerEl) {
        if (ignoredParents.has(parent.tagName)) return NodeFilter.FILTER_REJECT;
        parent = parent.parentElement;
      }
      return NodeFilter.FILTER_ACCEPT;
    }
  });

  const textNodes = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode);

  textNodes.forEach(node => {
    const text = node.nodeValue || "";
    const fragment = document.createDocumentFragment();
    let lastIndex = 0;

    text.replace(sourceRunRegex, (match, innerContent, offset) => {
      if (offset > lastIndex) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex, offset)));
      }

      const refs = getSourceRefs(match, sources);
      if (numbered) {
        // Steht die Domain schon direkt davor ("procyclingstats.com [S2]"),
        // zeigt die Pille nur das Favicon. Der Text selbst bleibt unberuehrt:
        // Anker und Claim-Marken suchen ihn woertlich.
        const before = offset > 0 ? text.slice(0, offset) : (node.previousSibling?.textContent || "");
        const compact = textEndsWithSourceHost(before, refs[0]?.src);
        // Fallback fuer alte Bookmarks/Snapshots, deren Markdown noch
        // `Aussage [S1].` enthaelt: Satzzeichen im selben Textknoten vor die
        // Quellen-Pille ziehen und den Leerraum davor entfernen. Eine
        // Favicon-Pille bleibt dagegen an ihrer Domain stehen.
        const tail = text.slice(offset + match.length);
        const punctuation = compact ? null : tail.match(/^([.!?]+(?:["'”’)\]}]+)?)(?=\s|$)/);
        if (punctuation) {
          const previous = fragment.lastChild;
          if (previous?.nodeType === Node.TEXT_NODE) {
            previous.nodeValue = previous.nodeValue.replace(/[ \t]+$/, "");
          }
          fragment.appendChild(document.createTextNode(punctuation[1]));
        }
        // A pill never needs a cluster: one run of tags is one pill with
        // "+N", and the teaser lists every source behind it.
        appendNumberedSourceRefs(fragment, refs, { compact });
        if (punctuation) {
          lastIndex = offset + match.length + punctuation[1].length;
          return match;
        }
      } else if (refs.length >= sourceGroupThreshold) {
        fragment.appendChild(createSourceListCluster(refs));
      } else {
        appendInlineSourceRefs(fragment, refs);
      }

      lastIndex = offset + match.length;
      return match;
    });

    if (lastIndex < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
    }

    node.parentNode.replaceChild(fragment, node);
  });
}
window.linkifySourceTags = linkifySourceTags;

// Agent prose cites URLs across independent model catalogs. Display numbers
// belong to this answer's deduplicated list, never to the currently active run.
// This is a DOM projection: the original Markdown and its review hash stay intact.
function linkifyAgentSources(containerEl, sources) {
  if (!containerEl || !sources?.length) return;
  const canonical = value => {
    try {
      const url = new URL(value);
      if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) return '';
      url.hash = '';
      return url.href;
    } catch (_) { return ''; }
  };
  const refs = new Map(sources.map((src, index) => [canonical(src.url), {src, token: String(index + 1)}]));
  refs.delete('');
  const skip = 'a, code, pre, script, style, textarea, .katex, mjx-container';
  const walker = document.createTreeWalker(containerEl, NodeFilter.SHOW_TEXT, {
    acceptNode: node => /\[S\d+(?:,\s*S?\d+)*\]/i.test(node.nodeValue || '') && !node.parentElement?.closest(skip)
      ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const text = node.nodeValue;
    const fragment = document.createDocumentFragment();
    let offset = 0;
    // A run of tags ("[S1][S2], [S3]") is one citation: one pill, and the
    // sentence punctuation moves in front of the whole run.
    for (const match of text.matchAll(/(?:\[S\d+(?:,\s*S?\d+)*\](?:[\s,;]*(?=\[S\d))?)+/gi)) {
      fragment.append(document.createTextNode(text.slice(offset, match.index)));
      const resolved = getSourceRefs(match[0].toUpperCase(), sources).map(ref => refs.get(canonical(ref.src?.url)));
      const before = match.index > 0 ? text.slice(0, match.index) : (node.previousSibling?.textContent || '');
      offset = match.index + match[0].length;
      if (resolved.length && resolved.every(Boolean)) {
        // "über njaped.no [S1]": the domain is already in the sentence, so
        // the pill shows only its favicon and stays next to it.
        const compact = textEndsWithSourceHost(before, resolved[0].src);
        const punctuation = !compact && text.slice(offset).match(/^([.!?]+)(?=\s|$)/);
        if (punctuation) {
          fragment.lastChild.nodeValue = fragment.lastChild.nodeValue.replace(/[ \t]+$/, '');
          fragment.append(document.createTextNode(punctuation[1]));
          offset += punctuation[1].length;
        }
        appendNumberedSourceRefs(fragment, resolved, { compact });
      } else fragment.append(document.createTextNode(match[0]));
    }
    fragment.append(document.createTextNode(text.slice(offset)));
    node.replaceWith(fragment);
  }
  for (const link of containerEl.querySelectorAll('a[href]')) {
    if (link.classList.contains('src-ref')) {
      // Keep focused/hovered references alive during streamed activity updates.
      const group = link.sourceGroup?.length ? link.sourceGroup : [{src: {url: link.getAttribute('href')}}];
      const mapped = group.map(entry => refs.get(canonical(entry.src?.url)));
      if (mapped.some(Boolean)) fillSourceRef(link, mapped.map((entry, index) => entry || group[index]));
      continue;
    }
    if (link.closest('code, pre, .katex, mjx-container') || link.querySelector('img, svg')) continue;
    const ref = refs.get(canonical(link.getAttribute('href')));
    if (!ref) continue;
    const label = link.textContent.trim();
    const rawUrl = canonical(label) === canonical(link.getAttribute('href'));
    const existingCitation = link.classList.contains('source-link');
    // "[njaped.no](https://njaped.no/)": the label only repeats the domain the
    // pill shows anyway. The pill takes the label's place instead of
    // following it, so the domain is not written twice.
    const hostLabel = !rawUrl && !existingCitation && labelIsSourceHost(label, ref.src);
    const before = link.previousSibling;
    const after = link.nextSibling;
    const parenthesized = before?.nodeType === Node.TEXT_NODE && after?.nodeType === Node.TEXT_NODE
      && /\($/.test(before.nodeValue) && /^\)/.test(after.nodeValue);
    if ((rawUrl || hostLabel) && parenthesized) {
      before.nodeValue = before.nodeValue.replace(/[ \t]*\($/, '');
      after.nodeValue = after.nodeValue.slice(1);
    } else if (rawUrl && before?.nodeType === Node.TEXT_NODE) {
      before.nodeValue = before.nodeValue.replace(/[ \t]+$/, '');
    }
    const fragment = document.createDocumentFragment();
    if (!rawUrl && !existingCitation && !hostLabel) fragment.append(...link.childNodes);
    // As in Consensus, a terminal citation follows the sentence punctuation.
    // A domain that stands in the sentence itself keeps its place.
    const punctuation = !(hostLabel && !parenthesized) && after?.nodeType === Node.TEXT_NODE
      && after.nodeValue.match(/^([.!?]+)(?=\s|$)/);
    if (punctuation) {
      fragment.append(document.createTextNode(punctuation[1]));
      after.nodeValue = after.nodeValue.slice(punctuation[1].length);
    }
    fragment.append(createSourceRef(ref));
    link.replaceWith(fragment);
  }
  mergeAdjacentSourceRefs(containerEl);
}
window.linkifyAgentSources = linkifyAgentSources;

// Identity key for merging sources across runs. Same contract as the backend's
// canonical_source_url (app/services/source_catalog.py): only the parts that
// carry no meaning are normalized. The URL parser lowercases scheme and host
// and supplies "/" for an empty path; the fragment is dropped. Path, trailing
// slash and query stay exactly as given, because /Report?key=AbC and
// /report?key=abc can be different documents.
function normalizeEvidenceUrl(url) {
  if (!url) return "";
  try {
    const u = new URL(String(url).trim());
    u.hash = "";
    return u.href;
  } catch (e) {
    return String(url).trim();
  }
}

// Pure run-local merge. Parallel callbacks pass the Evidence list from their
// RunContext; only the visible-view adapter writes the compatibility global.
function mergeEvidenceSourcesInto(existingSources, incomingSources) {
  const evidenceSources = Array.isArray(existingSources)
    ? existingSources.map(source => ({ ...source }))
    : [];
  const idMap = {};
  (incomingSources || []).forEach((src, idx) => {
    const localId = String(src.id || `S${idx + 1}`);
    const key = normalizeEvidenceUrl(src.url) || String(src.title || "").trim().toLowerCase();
    let existingIndex = evidenceSources.findIndex(existing => {
      const existingKey = normalizeEvidenceUrl(existing.url) || String(existing.title || "").trim().toLowerCase();
      return existingKey && existingKey === key;
    });

    if (existingIndex === -1) {
      existingIndex = evidenceSources.length;
      evidenceSources.push({
        ...src,
        id: `S${existingIndex + 1}`
      });
    }

    const globalNumber = existingIndex + 1;
    idMap[localId] = globalNumber;
    idMap[localId.replace(/^S/i, "")] = globalNumber;
    idMap[`S${idx + 1}`] = globalNumber;
    idMap[String(idx + 1)] = globalNumber;
  });

  return { evidenceSources, idMap };
}

function mergeEvidenceSources(incomingSources) {
  const merged = mergeEvidenceSourcesInto(window.currentEvidenceSources, incomingSources);
  window.App.state.set("currentEvidenceSources", merged.evidenceSources, "evidence");
  if (window.renderEvidenceSources) {
    window.renderEvidenceSources(merged.evidenceSources);
  }
  return merged.idMap;
}

// Alte OpenRouter-Snapshots koennen einen reinen Block aus Quellenmarken vor
// dem ersten Wort enthalten, weil ein Provider fuer alle Annotationen 0/0 als
// Position geliefert hat. Diese Texte sind bereits in Bookmarks gespeichert
// und laufen nicht noch einmal durch citations.py. Nur dieser eindeutige
// Legacy-Fall wird repariert: hinter die erste vollstaendige Aussage, niemals
// in den Consensus-Pfad (der diese Modellantwort-Hilfe nicht aufruft).
function normalizeLeadingModelSourceTags(markdown) {
  const source = String(markdown || "");
  const leading = source.match(
    /^(?:[ \t]*\[(?:S?\d+)(?:,\s*S?\d+)*\])+(?:[ \t]*\r?\n[ \t]*)?/i
  );
  if (!leading) return source;

  const tags = (leading[0].match(/\[(?:S?\d+)(?:,\s*S?\d+)*\]/gi) || []).join(" ");
  const body = source.slice(leading[0].length).replace(/^[ \t]+/, "");
  if (!body || !tags) return source;

  const sentence = /[.!?\u2026](?:["'\u201d\u2019)\]}]+)?(?=\s|$)/.exec(body);
  const paragraph = /\r?\n\s*\r?\n/.exec(body);
  const end = sentence
    ? sentence.index + sentence[0].length
    : (paragraph ? paragraph.index : body.length);
  return `${body.slice(0, end).replace(/[ \t]+$/, "")} ${tags}${body.slice(end)}`;
}

function rewriteSourceTags(markdown, idMap) {
  if (!markdown || !idMap || !Object.keys(idMap).length) {
    return normalizeTerminalSourceTagOrder(normalizeLeadingModelSourceTags(markdown));
  }
  const rewritten = markdown.replace(/\[((?:S?\d+)(?:,\s*S?\d+)*)\]/g, (match, inner) => {
    const mapped = inner.split(",").map(part => {
      const token = part.trim();
      const numeric = token.replace(/^S/i, "");
      return idMap[token] || idMap[numeric] || null;
    }).filter(Boolean);
    return mapped.length ? `[${mapped.join(", ")}]` : match;
  });
  return normalizeTerminalSourceTagOrder(normalizeLeadingModelSourceTags(rewritten));
}

function registerResponseSources(markdown, incomingSources) {
  const idMap = mergeEvidenceSources(incomingSources || []);
  return rewriteSourceTags(markdown || "", idMap);
}

function prepareResponseSourcesForEvidence(markdown, incomingSources, existingSources) {
  const sources = Array.isArray(incomingSources) ? incomingSources : [];
  const merged = mergeEvidenceSourcesInto(existingSources, sources);
  const idMap = merged.idMap;
  const mappedSources = [];
  const seen = new Set();

  sources.forEach((src, idx) => {
    if (!src || typeof src !== "object") return;
    const localId = String(src.id || `S${idx + 1}`);
    const numericId = localId.replace(/^S/i, "");
    const globalNumber =
      idMap[localId] ||
      idMap[numericId] ||
      idMap[`S${idx + 1}`] ||
      idMap[String(idx + 1)];
    const mapped = {
      id: globalNumber ? `S${globalNumber}` : localId,
      title: src.title || src.url || "",
      url: src.url || "",
      provider: src.provider || ""
    };
    const key = normalizeEvidenceUrl(mapped.url) || String(mapped.title || mapped.id || "").trim().toLowerCase();
    if (!key || seen.has(key)) return;
    seen.add(key);
    mappedSources.push(mapped);
  });

  return {
    markdown: rewriteSourceTags(markdown || "", idMap),
    sources: mappedSources,
    evidenceSources: merged.evidenceSources
  };
}

function prepareResponseSources(markdown, incomingSources) {
  const prepared = prepareResponseSourcesForEvidence(
    markdown,
    incomingSources,
    window.currentEvidenceSources
  );
  window.App.state.set("currentEvidenceSources", prepared.evidenceSources, "evidence");
  window.renderEvidenceSources?.(prepared.evidenceSources);
  return prepared;
}

window.App = window.App || {};
window.App.prepareResponseSourcesForEvidence = prepareResponseSourcesForEvidence;

function renderModelResponseWithSources(outputEl, markdown, incomingSources) {
  const prepared = prepareResponseSources(markdown, incomingSources || []);
  const box = outputEl?.closest?.(".response-box");
  if (box) {
    box.dataset.consensusAnswer = prepared.markdown || "";
    box.dataset.consensusSources = JSON.stringify(prepared.sources || []);
  }
  window.injectMarkdown(outputEl, prepared.markdown);
  return prepared.markdown;
}

// --- Teaser on hover ------------------------------------------------------
// A pill names the domain, not the page. Hovering it answers "which page,
// saying what" without leaving the sentence — the same bargain the marked
// passages in the consensus already make: look closer, stay in place. For a
// grouped pill ("+2") the teaser lists every source behind it. Click still
// opens the (first) source; keyboard focus opens the same accessible teaser.

const sourceTeaser = (function () {
  let el = null;
  let anchor = null;
  let hideTimer = null;

  function ensure() {
    if (el) return el;
    el = document.createElement("div");
    el.id = "sourceTeaser";
    el.className = "source-teaser";
    el.setAttribute("role", "tooltip");
    el.hidden = true;
    document.body.appendChild(el);
    return el;
  }

  function lookup(number) {
    const list = Array.isArray(window.currentEvidenceSources) ? window.currentEvidenceSources : [];
    return getSourceRefs(`[S${number}]`, list)[0]?.src || null;
  }

  function fill(node, src, number, target) {
    node.innerHTML = "";

    const head = document.createElement("div");
    head.className = "source-teaser-head";

    const index = document.createElement("span");
    index.className = "source-teaser-index";
    index.textContent = String(number);
    head.appendChild(index);

    const host = getSourceHost(src);
    if (host) {
      const fav = document.createElement("img");
      fav.className = "source-teaser-favicon";
      fav.src = "/api/topics/favicon?d=" + encodeURIComponent(host);
      fav.alt = "";
      fav.setAttribute("aria-hidden", "true");
      fav.setAttribute("referrerpolicy", "no-referrer");
      fav.width = 14;
      fav.height = 14;
      fav.addEventListener("error", () => fav.remove());
      head.appendChild(fav);

      const hostEl = document.createElement("span");
      hostEl.className = "source-teaser-host";
      hostEl.textContent = host;
      head.appendChild(hostEl);
    }

    node.appendChild(head);

    const title = document.createElement("div");
    title.className = "source-teaser-title";
    title.textContent = getSourceTitle(src, "Source " + number);
    node.appendChild(title);

    const snippet = src && (src.snippet || src.text);
    if (snippet) {
      const body = document.createElement("div");
      body.className = "source-teaser-snippet";
      body.textContent = String(snippet);
      node.appendChild(body);
    }
    const check = window.App.sourceVerification?.getCitationCheck(target);
    appendCheck(node, check, 'This citation has not been checked.');
  }

  function appendCheck(node, check, fallback) {
    const note = document.createElement("div");
    note.className = "source-teaser-check";
    note.dataset.state = check?.state || 'unchecked';
    note.textContent = check?.summary || fallback;
    node.appendChild(note);
    if (check?.detail) {
      const detail = document.createElement("div");
      detail.className = "source-teaser-check-detail";
      detail.textContent = check.detail;
      node.appendChild(detail);
    }
  }

  // One pill, several sources: the teaser is where they are all named.
  function fillGroup(node, entries, target) {
    node.innerHTML = "";
    const head = document.createElement("div");
    head.className = "source-teaser-head";
    head.textContent = `${entries.length} sources`;
    node.appendChild(head);

    const list = document.createElement("ol");
    list.className = "source-teaser-list";
    const verification = window.App.sourceVerification;
    let checked = false;
    entries.forEach(entry => {
      const src = entry.src;
      const item = document.createElement("li");
      item.className = "source-teaser-item";
      const meta = document.createElement("div");
      meta.className = "source-teaser-item-head";
      if (entry.number) {
        const index = document.createElement("span");
        index.className = "source-teaser-index";
        index.textContent = String(entry.number);
        meta.appendChild(index);
      }
      const label = getSourcePillLabel(src, entry.token);
      const icon = createSourceRefIcon(src, label);
      icon.classList.add("source-teaser-favicon");
      meta.appendChild(icon);
      const hostEl = document.createElement("span");
      hostEl.className = "source-teaser-host";
      hostEl.textContent = label;
      meta.appendChild(hostEl);
      item.appendChild(meta);
      const title = document.createElement("div");
      title.className = "source-teaser-title is-single-line";
      title.textContent = getSourceTitle(src, label);
      item.appendChild(title);
      // Only a verdict bound to exactly this source number; never the
      // group's worst state copied onto every row.
      const own = entry.number ? verification?.getCitationCheck(target, String(entry.number)) : null;
      if (own) {
        checked = true;
        appendCheck(item, own, '');
      }
      list.appendChild(item);
    });
    node.appendChild(list);
    if (!checked) {
      appendCheck(node, verification?.getCitationCheck(target), 'These citations have not been checked.');
    }
  }

  function place(node, target) {
    const rect = target.getBoundingClientRect();
    node.style.visibility = "hidden";
    node.hidden = false;
    const width = node.offsetWidth;
    const height = node.offsetHeight;
    const margin = 8;

    let left = rect.left + rect.width / 2 - width / 2;
    left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));

    // Above the citation by default; below it when the top of the viewport
    // is closer than the popup is tall.
    let top = rect.top - height - 8;
    node.classList.toggle("is-below", top < margin);
    if (top < margin) top = rect.bottom + 8;

    node.style.left = Math.round(left + window.scrollX) + "px";
    node.style.top = Math.round(top + window.scrollY) + "px";
    node.style.visibility = "";
  }

  function show(target) {
    const number = parseInt(target.dataset.sourceNumber || "", 10);
    if (!Number.isFinite(number)) return;
    const src = Object.prototype.hasOwnProperty.call(target, 'sourceData') ? target.sourceData : lookup(number);
    if (!src) { hide(); return; }

    // Also repair restored/legacy refs whose HTML still carries a title.
    target.removeAttribute('title');

    window.clearTimeout(hideTimer);
    hideTimer = null;
    if (anchor && anchor !== target) unlinkDescription(anchor);
    anchor = target;
    const node = ensure();
    const group = (target.sourceGroup || []).filter(entry => entry && entry.src);
    if (group.length > 1) fillGroup(node, group, target);
    else fill(node, src, number, target);
    const descriptions = new Set((target.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    descriptions.add(node.id);
    target.setAttribute('aria-describedby', [...descriptions].join(' '));
    place(node, target);
    node.classList.add("is-visible");
  }

  function unlinkDescription(target) {
    const descriptions = (target.getAttribute('aria-describedby') || '').split(/\s+/).filter(id => id && id !== 'sourceTeaser');
    if (descriptions.length) target.setAttribute('aria-describedby', descriptions.join(' '));
    else target.removeAttribute('aria-describedby');
  }

  function hide() {
    if (!el) return;
    if (anchor) unlinkDescription(anchor);
    anchor = null;
    el.classList.remove("is-visible");
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => {
      if (el && !el.classList.contains("is-visible")) el.hidden = true;
    }, 160);
  }

  document.addEventListener("pointerover", event => {
    const ref = event.target.closest?.(".src-ref");
    if (ref) {
      if (ref !== anchor) show(ref);
      return;
    }
    if (anchor && !event.target.closest?.("#sourceTeaser")) hide();
  });

  document.addEventListener("pointerdown", () => hide());
  document.addEventListener('focusin', event => {
    const ref = event.target.closest?.('.src-ref');
    if (ref) show(ref);
  });
  document.addEventListener('focusout', event => {
    if (anchor === event.target) hide();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && anchor) hide();
  });
  document.addEventListener('source-check-updated', event => {
    if (anchor && !anchor.isConnected) hide();
    else if (anchor && event.target.contains(anchor)) show(anchor);
  });
  window.addEventListener("scroll", () => { if (anchor) hide(); }, { passive: true });
  window.addEventListener("resize", () => { if (anchor) hide(); });

  return { hide };
})();

window.mergeEvidenceSources = mergeEvidenceSources;
window.rewriteSourceTags = rewriteSourceTags;
window.registerResponseSources = registerResponseSources;
window.prepareResponseSources = prepareResponseSources;
window.renderModelResponseWithSources = renderModelResponseWithSources;
window.hideSourceTeaser = sourceTeaser.hide;
window.App.sourceTeaser = sourceTeaser;
// Copy paths (Copy consensus, citation) read pills through these helpers:
// a pill's text in the DOM is "domain +2", which is no plain-text citation.
window.App.sourceRefs = Object.freeze({ plainText: sourceRefPlainText, urls: sourceRefUrls });
