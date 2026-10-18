import assert from 'node:assert/strict';
import { readdir, readFile, lstat } from 'node:fs/promises';
import path from 'node:path';
const root = path.resolve('public');
let bytes = 0;
for (const name of await readdir(root)) {
  const filename = path.join(root, name);
  const stat = await lstat(filename);
  assert(stat.isFile() && !stat.isSymbolicLink(), `Only regular files allowed: ${name}`);
  assert(/\.(html|css)$/.test(name), `Unexpected published file: ${name}`);
  bytes += stat.size;
  if (name.endsWith('.html')) {
    const html = await readFile(filename, 'utf8');
    for (const [, url] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
      if (url === 'https://devcirrus.com/') continue;
      assert(url.startsWith('/') && !url.startsWith('//'), `Remote or invalid reference: ${url}`);
      const target = path.resolve(root, `.${url === '/' ? '/index.html' : url}`);
      assert(target.startsWith(`${root}/`));
      assert((await lstat(target)).isFile(), `Missing local reference: ${url}`);
    }
  }
}
assert(bytes <= 30_000, `Published content exceeds 30 KB: ${bytes}`);
const html = await readFile('public/index.html', 'utf8');
for (const text of ['Hello world', 'DevCirrus', 'A brand by Augmen', 'lang="pt-PT"', 'lang="en-GB"']) assert(html.includes(text), `Missing ${text}`);
const { hosting } = JSON.parse(await readFile('firebase.json', 'utf8'));
assert.equal(hosting.public, 'public');
assert.equal(hosting.target, 'website');
assert.equal(hosting.rewrites, undefined, 'No SPA fallback');
assert.equal(hosting.redirects, undefined, 'Domain redirects belong to Terraform');
console.log(`HTML, local references and Hosting config valid; ${bytes} bytes published.`);
