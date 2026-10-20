// A small CSS reader for stylesheet lint tests: rules with their position,
// selector, declarations and enclosing at-rules (@media, @supports,
// @container, @layer). No nesting syntax is used in static/css, so a rule body
// holds declarations only; @keyframes / @font-face are kept as opaque blocks.

const GROUPING = /^@(media|supports|container|layer|document|scope)\b/i;

function skipString(text, i) {
  const quote = text[i];
  for (let j = i + 1; j < text.length; j++) {
    if (text[j] === "\\") j++;
    else if (text[j] === quote) return j + 1;
  }
  return text.length;
}

function skipComment(text, i) {
  const end = text.indexOf("*/", i + 2);
  return end < 0 ? text.length : end + 2;
}

export function stripComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, "");
}

// Index of the first character that is neither whitespace nor comment.
function contentStart(text, from, to) {
  let i = from;
  while (i < to) {
    if (/\s/.test(text[i])) i++;
    else if (text[i] === "/" && text[i + 1] === "*") i = skipComment(text, i);
    else break;
  }
  return i;
}

function matchingBrace(text, open) {
  let depth = 1;
  let j = open + 1;
  while (j < text.length && depth) {
    const c = text[j];
    if (c === "/" && text[j + 1] === "*") { j = skipComment(text, j); continue; }
    if (c === '"' || c === "'") { j = skipString(text, j); continue; }
    if (c === "{") depth++;
    else if (c === "}") depth--;
    j++;
  }
  return j;
}

/**
 * Parse `text` into a tree. Every node has `start` (first selector/prelude
 * character, comments before it excluded) and `end` (just after its `}`).
 *   {type: "root", children}
 *   {type: "at", prelude, open, children, parent}
 *   {type: "rule", selector, open, body, parent}
 *   {type: "opaque", prelude, open, body, parent}   (@keyframes, @font-face …)
 */
export function parseCss(text) {
  const root = { type: "root", start: 0, end: text.length, children: [], parent: null };
  const stack = [root];
  let preludeStart = 0;
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (c === "/" && text[i + 1] === "*") { i = skipComment(text, i); continue; }
    if (c === '"' || c === "'") { i = skipString(text, i); continue; }
    if (c === ";") { i += 1; preludeStart = i; continue; }
    if (c === "}") {
      const node = stack.pop();
      node.end = i + 1;
      i += 1;
      preludeStart = i;
      continue;
    }
    if (c !== "{") { i += 1; continue; }
    const parent = stack[stack.length - 1];
    const start = contentStart(text, preludeStart, i);
    const prelude = stripComments(text.slice(start, i)).replace(/\s+/g, " ").trim();
    if (GROUPING.test(prelude)) {
      const node = { type: "at", prelude, start, open: i, children: [], parent };
      parent.children.push(node);
      stack.push(node);
      i += 1;
      preludeStart = i;
      continue;
    }
    const end = matchingBrace(text, i);
    const body = text.slice(i + 1, end - 1);
    const node = prelude.startsWith("@")
      ? { type: "opaque", prelude, start, open: i, end, body, parent }
      : { type: "rule", selector: prelude, start, open: i, end, body, parent };
    parent.children.push(node);
    i = end;
    preludeStart = i;
  }
  return root;
}

export function* walkRules(node) {
  for (const child of node.children || []) {
    if (child.type === "rule") yield child;
    else if (child.type === "at") yield* walkRules(child);
  }
}

export function ancestors(node) {
  const list = [];
  for (let at = node.parent; at && at.type !== "root"; at = at.parent) list.push(at);
  return list;
}

/** Split a selector list at its top-level commas. */
export function splitSelectors(selector) {
  const parts = [];
  let depth = 0;
  let from = 0;
  for (let i = 0; i < selector.length; i++) {
    const c = selector[i];
    if (c === "(" || c === "[") depth++;
    else if (c === ")" || c === "]") depth--;
    else if (c === "," && depth === 0) {
      parts.push(selector.slice(from, i).trim());
      from = i + 1;
    }
  }
  parts.push(selector.slice(from).trim());
  return parts.filter(Boolean);
}

/** Property names declared in a rule body (lowercase, comments removed). */
export function declaredProperties(body) {
  return stripComments(body)
    .split(";")
    .map(part => part.split(":")[0].trim().toLowerCase())
    .filter(name => /^-?[a-z][\w-]*$/.test(name));
}

export function lineOf(text, index) {
  let line = 1;
  for (let i = 0; i < index; i++) if (text.charCodeAt(i) === 10) line++;
  return line;
}
