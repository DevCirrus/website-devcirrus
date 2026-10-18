# Website operations

This repository owns the public DevCirrus website implementation. The first
release uses static HTML/CSS, classic Firebase Hosting, Cloud DNS, Terraform and
GitHub Actions. Terraform owns infrastructure; Firebase CLI owns content and
releases. Neither manages the other's resources.

## Execution prerequisites (F0)

Before bootstrap, record the following in private storage:

- Approved target GCP project ID and current billing status; authenticated
  read-only inventory of projects, APIs, Firebase sites, DNS zones and state.
- Existing state/resource ownership. Import approved existing objects before
  planning; never run two Terraform states against one resource.
- Registrar access and complete authoritative zone export, including mail,
  service verification, subdomains, TTLs, NS and DS/DNSSEC. Public DNS queries
  alone do not constitute a complete inventory.
- Current official prices, quotas, budget and the exact proposed changes,
  expected monthly cost and rollback for the operation being approved.

Creating resources, enabling billing and changing DNS/NS/DS each require explicit
approval of a concrete plan. A code review or merge alone is not that approval.
No infrastructure has been provisioned by these preparation commits. No legacy
experiments should be deleted as part of this website.

Keep account inventories, personal notes, credentials, tfvars, Terraform state,
binary plans and complete plan output outside this public repository and public
Actions logs/artifacts. Only `public/` is published by Firebase Hosting.

## References to revalidate before execution

- [Hosting and custom domains](https://firebase.google.com/docs/hosting/custom-domain)
- [Hosting quotas](https://firebase.google.com/docs/hosting/usage-quotas-pricing)
- [Firebase pricing](https://firebase.google.com/pricing)
- [Cloud DNS pricing](https://cloud.google.com/dns/pricing)
- [Cloud Storage pricing](https://cloud.google.com/storage/pricing)
- [GCS state backend](https://developer.hashicorp.com/terraform/language/backend/gcs)
- [GitHub federation](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)

Provider documentation and tool versions were checked on 2026-10-18. Direct
access to the pricing pages was unavailable in the preparation environment;
prices and effective account quotas must be rechecked before approval. Small-site
costs include a billable DNS zone and private state storage even with no visits.
Budget alerts are notifications, not spending caps.

## Activate CI only after approved provisioning (F4)

Checks run without GCP credentials on every PR, and as a reusable workflow for
the exact `main` commit before deploy/infra. No path filter can suppress the
required check. Actions are pinned to verified full SHAs; actionlint is pinned
and downloaded with a fixed SHA-256. Native Terraform tests use mock providers
only and do not test actual cloud authorization.

Before enabling either workflow, configure and verify GitHub settings:

| Environment | Deployment branches | Required reviewers |
|---|---|---|
| `production` | custom policy: branch `main` only, no tags | none, to keep content deploy automatic |
| `infrastructure-plan` | same | none; trusted manual dispatch only |
| `infrastructure` | same | PedroMatos; allow approval of his own manual run |

Disable administrator bypass where GitHub supports it. The preflight refuses
OIDC if the branch policies/reviewer gate do not match. The apply environment
approval authorizes only the exact private plan for that run, after inspecting
costs, all changes and rollback. It is not a general approval for later runs.
Repository/environment configuration has not been changed by these commits.

Protect `main` with PRs and the stable `checks` job, forbid force pushes and
branch deletion. Because Pedro can be both author and sole reviewer, do not
require an impossible self-approval. For his own PRs he records diff/checklist
review before his explicitly authorized merge; third-party PRs need his review.
CODEOWNERS documents ownership but does not itself enforce these settings.

Configure the technical variables after resources exist:

- Repository variables `WEBSITE_DEPLOY_ENABLED=true` and
  `INFRASTRUCTURE_ENABLED=true` are explicit one-time activation switches; absent
  switches keep cloud jobs disabled during preparation. Once enabled, every merge
  runs checks and automatic content deployment, with no per-deploy approval.
- `production`: `SITE_PROJECT_ID`, `SITE_ID`, `WIF_CONTENT_PROVIDER`,
  `CONTENT_SERVICE_ACCOUNT` from approved bootstrap/site outputs.
- `infrastructure-plan`: `SITE_PROJECT_ID`, `SITE_ID`, `SITE_STATE_BUCKET`,
  `SITE_INPUTS_GENERATION`, `WIF_PLAN_PROVIDER`, `PLAN_SERVICE_ACCOUNT`.
- `infrastructure`: the same `SITE_STATE_BUCKET`, plus `WIF_APPLY_PROVIDER`,
  `APPLY_SERVICE_ACCOUNT`.

Human operators put complete approved site inputs in the private site bucket at
`inputs/site.tfvars.json`, recording its exact object generation. Pin that in
`SITE_INPUTS_GENERATION`; never put the contents in a repository variable or an
Actions input. The plan validates project/site against environment variables.
Bootstrap is never managed by the infrastructure workflow.

The existing-project variant does not create a project, associate billing or
own existing project settings. Inventory Firebase/APIs and import existing
managed objects first. Product roles can affect other sites/zones in the project;
review that scope and validate service usage/API Keys permissions with the real
identity before enabling federation. Content has no DNS, IAM, billing or state
bucket grants in this configuration. Actual denial tests for PRs, forks, tags,
other workflows/branches and cross-pipeline impersonation remain required at
activation; mocks are not proof of real IAM isolation.

### Content release

`deploy.yml` serializes releases, checks current `main` immediately before
publishing and limits the CLI to `hosting:website` on the explicit project. It
records the commit/Hosting version in the job summary and compares published
`web.app` HTML with the checked-out file. Keep the run URL, live release/version
and SHA as private operational evidence. No Terraform apply runs here.

### Private infrastructure plan and apply

Dispatch `infra.yml` from `main` after reviewing the code. The plan identity
initializes only the site backend and saves its plan, human-readable output and
manifest under `plans/RUN/ATTEMPT/SHA.*` in private GCS. Full Terraform output and
failure logs never go to Actions artifacts or public logs. Review the exact
human-readable generation and digest reported in the summary before approval;
inspect the binary/manifest privately if needed. No-change plans do not apply.

Plan/manifest generations and SHA-256 digests pass directly between jobs. Apply
checks those immutable anchors, source SHA, run/attempt and provider lockfile,
rechecks `main`, and applies that saved plan with locking. It does not replan.
Expired, missing, replaced or stale plans fail closed; rerun the entire workflow
and approve the new plan. Re-running an old apply job is not a supported recovery.
GCS generation mismatch, a newer state serial or a new commit requires fresh
review. Serialize the complete workflow and keep `-lock-timeout=5m`; do not use
`-lock=false`. Do not print a private error log to diagnose a public CI failure.
