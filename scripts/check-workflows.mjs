import { readdir, readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { parseDocument } from 'yaml';
for (const name of await readdir('.github/workflows')) {
  const doc = parseDocument(await readFile(`.github/workflows/${name}`, 'utf8'), { uniqueKeys: true });
  assert.equal(doc.errors.length, 0, `${name}: ${doc.errors}`);
  const config = doc.toJS();
  assert(!('pull_request_target' in config.on), 'No privileged PR code execution');
  assert.equal(config.permissions.contents, 'read');
  assert(!config.permissions['id-token'], 'OIDC must be job-scoped');
  for (const job of Object.values(config.jobs)) {
    for (const step of job.steps ?? []) {
      if (step.uses) assert(/@[0-9a-f]{40}$/.test(step.uses), `Unpinned action: ${step.uses}`);
      assert(!/upload-artifact/.test(step.uses ?? ''), 'No public infrastructure artifacts');
    }
  }
}
console.log('Workflow YAML, action pins and baseline permission boundaries valid.');
