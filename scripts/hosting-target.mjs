// Generate only from approved technical identifiers. No project ID is invented.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
const { SITE_PROJECT_ID: project, SITE_ID: site } = process.env;
assert(/^[a-z][a-z0-9-]{4,28}[a-z0-9]$/.test(project ?? ''), 'Set approved SITE_PROJECT_ID');
assert(/^[a-z0-9][a-z0-9-]{2,28}[a-z0-9]$/.test(site ?? ''), 'Set approved SITE_ID');
await writeFile('.firebaserc', JSON.stringify({ targets: { [project]: { hosting: { website: [site] } } } }, null, 2) + '\n');
