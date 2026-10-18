# Website operations

This repository owns the public DevCirrus website implementation. The first
release uses static HTML/CSS, classic Firebase Hosting, Cloud DNS, Terraform and
GitHub Actions. Terraform owns infrastructure; Firebase CLI owns content and
releases. Neither manages the other's resources.

## Execution prerequisites (F0)

Before bootstrap, record the following in private storage:

- Approved dedicated GCP project ID, parent and billing account; authenticated
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
