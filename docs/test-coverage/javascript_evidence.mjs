// Parse test registrations and assertion anchors without importing test code.
// Uses Acorn already supplied by the locked frontend dependencies (npm ci).
import {readFileSync} from 'node:fs';
import {parse} from 'acorn';

function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  if (typeof node.type === 'string') visit(node);
  for (const [key, value] of Object.entries(node)) {
    if (key === 'loc') continue;
    if (Array.isArray(value)) value.forEach(child => walk(child, visit));
    else if (value && typeof value === 'object') walk(value, visit);
  }
}

const result = {};
for (const path of process.argv.slice(2)) {
  const source = readFileSync(path, 'utf8');
  const tree = parse(source, {ecmaVersion: 'latest', sourceType: 'module', locations: true});
  const definitions = [];
  walk(tree, node => {
    if (node.type !== 'CallExpression') return;
    const registration = source.slice(node.callee.start, node.callee.end);
    if (!/^(?:it|test)(?:\.|$)/.test(registration)) return;
    const [title, callback] = node.arguments;
    if (!(typeof title?.value === 'string' || title?.type === 'TemplateLiteral') || !['ArrowFunctionExpression', 'FunctionExpression'].includes(callback?.type)) return;
    const assertions = new Set();
    const evidence = [];
    walk(callback.body, child => {
      if (child.type === 'CallExpression' && child.callee.type === 'Identifier' && child.callee.name === 'expect') {
        assertions.add(child.loc.start.line);
        evidence.push({line: child.loc.start.line, kind: 'expect'});
      } else if (child.type === 'CallExpression') {
        const callee = source.slice(child.callee.start, child.callee.end);
        if (/^assert(?:\.|Fails$|Succeeds$)/.test(callee)) {
          evidence.push({line: child.loc.start.line, kind: 'assertion_or_helper_call'});
        }
      }
    });
    // Template registrations inside a loop are one static definition, even
    // when the runner expands them into several differently named cases.
    const name = typeof title.value === 'string' ? title.value : source.slice(title.start, title.end);
    definitions.push({name, line: node.loc.start.line, end_line: node.loc.end.line,
                      registration, assertion_lines: [...assertions].sort((a, b) => a - b),
                      assertion_evidence: [...new Map(evidence.map(a => [`${a.line}:${a.kind}`, a])).values()].sort((a, b) => a.line - b.line)});
  });
  result[path] = definitions;
}
process.stdout.write(JSON.stringify(result));
