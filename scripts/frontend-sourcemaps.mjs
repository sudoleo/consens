// Source maps for the minified bundles in static/dist.
//
// Purpose: a browser error alert names `app.<hash>.js:1:<col>`, which is
// useless on its own. The server (app/core/sourcemaps.py) resolves that column
// through `<bundle>.map` back to `static/js/<file>.js:<line>:<col>`.
//
// The classic groups are minified as ONE concatenated script (see
// build_frontend.mjs), so esbuild's map points into that concatenation. This
// module rewrites it onto the real files. The bundles carry no
// sourceMappingURL comment: the filename hash stays a hash of exactly the
// served bytes, and the maps contain no sourcesContent (the sources under
// static/js are public anyway; the map only adds coordinates).

const BASE64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const BASE64_INDEX = new Map([...BASE64].map((char, index) => [char, index]));
// The same line terminators esbuild (and ECMAScript) count.
const LINE_BREAK = new RegExp("\\r\\n|[\\n\\r\\u2028\\u2029]", "g");

export function decodeVlq(segment) {
  const values = [];
  let value = 0;
  let shift = 0;
  for (const char of segment) {
    const digit = BASE64_INDEX.get(char);
    if (digit === undefined) throw new Error(`invalid VLQ character: ${char}`);
    value += (digit & 31) << shift;
    if (digit & 32) {
      shift += 5;
    } else {
      values.push(value & 1 ? -(value >>> 1) : value >>> 1);
      value = 0;
      shift = 0;
    }
  }
  if (shift) throw new Error("truncated VLQ segment");
  return values;
}

export function encodeVlq(values) {
  let out = "";
  for (const number of values) {
    let vlq = number < 0 ? ((-number) << 1) | 1 : number << 1;
    do {
      let digit = vlq & 31;
      vlq >>>= 5;
      if (vlq) digit |= 32;
      out += BASE64[digit];
    } while (vlq);
  }
  return out;
}

/** Decoded mappings: one array per generated line of [genCol, src, line, col]. */
export function decodeMappings(mappings) {
  const lines = [];
  let src = 0;
  let srcLine = 0;
  let srcCol = 0;
  for (const rawLine of mappings.split(";")) {
    const segments = [];
    let genCol = 0;
    for (const raw of rawLine ? rawLine.split(",") : []) {
      const values = decodeVlq(raw);
      genCol += values[0];
      if (values.length >= 4) {
        src += values[1];
        srcLine += values[2];
        srcCol += values[3];
        segments.push([genCol, src, srcLine, srcCol]);
      }
    }
    lines.push(segments);
  }
  return lines;
}

export function encodeMappings(lines) {
  let src = 0;
  let srcLine = 0;
  let srcCol = 0;
  return lines.map((segments) => {
    let genCol = 0;
    return segments.map(([col, source, line, column]) => {
      const encoded = encodeVlq([col - genCol, source - src, line - srcLine, column - srcCol]);
      genCol = col;
      src = source;
      srcLine = line;
      srcCol = column;
      return encoded;
    }).join(",");
  }).join(";");
}

function lineCount(text) {
  return (text.match(LINE_BREAK) || []).length + 1;
}

/**
 * Line layout of the classic-group concatenation built in build_frontend.mjs:
 * every part is `/* <file> *\/\n<content>\n;`, joined with "\n".
 * Returns [{ file, firstLine, lines }] with 0-based concatenation lines.
 */
export function concatenationLayout(parts) {
  const layout = [];
  let header = 0;
  for (const { file, content } of parts) {
    const lines = lineCount(content);
    layout.push({ file, firstLine: header + 1, lines });
    header += lines + 2;
  }
  return layout;
}

/** Rewrite esbuild's map of the concatenation onto the original files. */
export function remapConcatenated(map, layout, file) {
  const decoded = decodeMappings(map.mappings);
  const sources = layout.map((part) => part.file);
  const remapped = decoded.map((segments) => {
    const out = [];
    for (const [genCol, , line, col] of segments) {
      // Few parts; a linear scan keeps this obviously correct.
      const index = layout.findIndex((part) => line >= part.firstLine && line < part.firstLine + part.lines);
      if (index >= 0) out.push([genCol, index, line - layout[index].firstLine, col]);
    }
    return out;
  });
  return { version: 3, file, sources, names: [], mappings: encodeMappings(remapped) };
}

/** Normalize an esbuild bundle map: repo-relative POSIX sources, no names. */
export function normalizeBundleMap(map, outDirRelative, file) {
  const posix = (value) => value.replace(/\\/g, "/");
  const sources = (map.sources || []).map((source) => {
    const joined = `${posix(outDirRelative)}/${posix(source)}`.split("/");
    const stack = [];
    for (const part of joined) {
      if (part === "..") stack.pop();
      else if (part && part !== ".") stack.push(part);
    }
    return stack.join("/");
  });
  const lines = decodeMappings(map.mappings || "");
  return { version: 3, file, sources, names: [], mappings: encodeMappings(lines) };
}

export function serializeMap(map) {
  return `${JSON.stringify(map)}\n`;
}
