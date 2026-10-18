import { readFile, appendFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const result = JSON.parse(await readFile(`${process.env.RUNNER_TEMP}/deploy.json`, 'utf8'));
assert.equal(result.status, 'success');
const version = result.result.hosting;
assert.equal(typeof version, 'string');
assert(version.includes(`sites/${process.env.SITE_ID}/versions/`));
assert(/^(?:projects\/[a-z0-9-]+\/)?sites\/[a-z0-9-]+\/versions\/[a-zA-Z0-9-]+$/.test(version));
await appendFile(process.env.GITHUB_STEP_SUMMARY,
  `Published commit \`${process.env.GITHUB_SHA}\`, Hosting version \`${version}\`, channel \`live\`. Release message records the commit.\n`);
