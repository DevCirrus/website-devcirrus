# website-devcirrus
DevCirrus — an Augmen brand sharing cloud/DevOps knowledge, projects and experiments.

## First release

A small bilingual HTML/CSS page for `https://devcirrus.com`, with classic Firebase
Hosting and a managed `www` redirect. Infrastructure is prepared separately;
publication and domain verification require the approved bootstrap and DNS work.

Use Node from `.node-version`, then `npm ci` and `npm run check`. For a local
preview run `npm run serve` and open <http://127.0.0.1:8080>.

Only `public/` is deployed. After the approved site exists, set `SITE_PROJECT_ID`
and `SITE_ID`, run `node scripts/hosting-target.mjs`, then deploy using the explicit
project and `hosting:website` target. `.firebaserc` is generated locally rather
than committing an unverified project ID.

See [operations and prerequisites](docs/operations.md). Blog, wiki and technology
demonstrations are outside this release.

Infrastructure roots: [bootstrap num Codespace descartável — visão geral e passo a passo](infra/bootstrap/README.md) and
[Hosting/DNS](infra/site/README.md). CI remains gated by activation variables
until approved provisioning and environment protection are verified. After
activation, content publishes automatically after merge; infrastructure needs a
separate private plan and environment approval. See the [DNS cutover
procedure](docs/dns-cutover.md) and [acceptance/rollback checklist](docs/operations.md#launch-acceptance-and-evidence-f6).
