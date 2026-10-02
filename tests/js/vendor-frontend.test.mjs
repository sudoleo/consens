import { afterEach, describe, expect, it } from 'vitest';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { vendorFrontend } from '../../scripts/vendor_frontend.mjs';

const dirs = [];
afterEach(async () => { for (const dir of dirs.splice(0)) await fs.rm(dir, { recursive: true, force: true }); });
const files = {
  marked: ['marked.min.js', 'LICENSE.md'], dompurify: ['dist/purify.min.js', 'LICENSE'],
  katex: ['dist/katex.min.js', 'dist/katex.min.css', 'dist/contrib/auto-render.min.js', 'LICENSE', 'dist/fonts/Z.woff2', 'dist/fonts/A.ttf'],
};
async function put(root, relative, content) { const full = path.join(root, relative); await fs.mkdir(path.dirname(full), { recursive: true }); await fs.writeFile(full, content); }
async function fixture() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'consensio-vendor-')); dirs.push(root);
  await put(root, 'package.json', JSON.stringify({ devDependencies: { marked: '1.0.0', dompurify: '1.0.0', katex: '1.0.0' } }));
  for (const [name, paths] of Object.entries(files)) {
    await put(root, `node_modules/${name}/package.json`, '{"version":"1.0.0"}');
    for (const file of paths) await put(root, `node_modules/${name}/${file}`, Buffer.from(`${name}/${file}\0binary`));
  }
  return root;
}

describe('Vendoring pinned frontend libraries on disk', () => {
  it('copies every pinned library, license and font byte and retains unrelated old versions', async () => {
    const root = await fixture();
    await put(root, 'static/vendor/marked/0.9.0/keep.js', 'old');
    const inputs = await vendorFrontend(root, false);
    expect(inputs).toHaveLength(10);
    expect(inputs.slice(-2)).toEqual(['static/vendor/katex/1.0.0/dist/fonts/A.ttf', 'static/vendor/katex/1.0.0/dist/fonts/Z.woff2']);
    for (const [name, paths] of Object.entries(files)) for (const file of paths) {
      expect(await fs.readFile(path.join(root, `static/vendor/${name}/1.0.0/${file}`))).toEqual(await fs.readFile(path.join(root, `node_modules/${name}/${file}`)));
    }
    expect(await fs.readFile(path.join(root, 'static/vendor/marked/0.9.0/keep.js'), 'utf8')).toBe('old');
    const old = new Date('2020-01-01Z');
    for (const relative of inputs) await fs.utimes(path.join(root, relative), old, old);
    await vendorFrontend(root, true); await vendorFrontend(root, false);
    for (const relative of inputs) expect((await fs.stat(path.join(root, relative))).mtimeMs).toBe(old.getTime());
  });

  it.each(['stale', 'missing'])('rejects %s target bytes without writing in check-only mode', async kind => {
    const root = await fixture(); await vendorFrontend(root, false);
    const relative = 'static/vendor/katex/1.0.0/dist/fonts/Z.woff2';
    if (kind === 'missing') await fs.unlink(path.join(root, relative)); else await put(root, relative, 'wrong');
    await expect(vendorFrontend(root, true)).rejects.toThrow(`${relative} is stale`);
    if (kind === 'missing') await expect(fs.access(path.join(root, relative))).rejects.toThrow();
    else expect(await fs.readFile(path.join(root, relative), 'utf8')).toBe('wrong');
  });

  it('rejects version drift before creating any output', async () => {
    const root = await fixture(); await put(root, 'node_modules/marked/package.json', '{"version":"2.0.0"}');
    await expect(vendorFrontend(root, false)).rejects.toThrow('Unexpected marked version: 2.0.0');
    await expect(fs.access(path.join(root, 'static'))).rejects.toThrow();
  });
});
