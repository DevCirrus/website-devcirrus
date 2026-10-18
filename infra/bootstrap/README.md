# Human-operated bootstrap

Run only after the private inventory, current costs and a concrete plan have been
approved. This root reads an existing approved project and prepares APIs, Firebase, two
private state buckets and three narrowly federated identities. It does not create
a project, associate billing, or own the existing project configuration. The
operator needs project-level permissions for these resources. Import Firebase
first if already enabled; confirm current billing without changing it. Use
approved ADC/federation, never a downloaded service account key. Firebase enabling
is irreversible; deleting the Terraform resource does not remove Firebase.

Use Terraform 1.16.6 and the committed provider locks. Keep all command output,
inputs, plans and initial state in a mode-0700 private directory outside Git:

```sh
umask 077
# Copy this root, including its lockfile, into $PRIVATE_BOOTSTRAP_DIR first.
terraform -chdir="$PRIVATE_BOOTSTRAP_DIR" init
terraform -chdir="$PRIVATE_BOOTSTRAP_DIR" plan -var-file="$PRIVATE_INPUTS" -out="$PRIVATE_PLAN"
# Review actual resources, costs, imports and rollback; obtain explicit approval.
terraform -chdir="$PRIVATE_BOOTSTRAP_DIR" apply "$PRIVATE_PLAN"
```

Never apply an example input file. Existing resources must be reconciled/imported
first. Bootstrap is intentionally not callable by Actions. The CI identities have
no billing, IAM, API enablement or bootstrap bucket permissions. The deploying
account has product-wide Hosting Admin across the selected project, not an
upload-only custom role; test the actual required permissions during activation.
Plan/apply Object Admin on the site bucket includes writes for state locks and
private plans. These identities are trusted and have no bootstrap-state access.

After creation, back up local state privately. Add `backend "gcs" {}` inside the
`terraform` block in the private bootstrap copy, then migrate exactly once:

```sh
terraform -chdir="$PRIVATE_BOOTSTRAP_DIR" init -migrate-state \
  -backend-config="bucket=$BOOTSTRAP_STATE_BUCKET" -backend-config=prefix=bootstrap
terraform -chdir="$PRIVATE_BOOTSTRAP_DIR" plan -var-file="$PRIVATE_INPUTS"
```

Verify remote lineage, serial, recovery/versioning and a plan with no unexpected
changes before retiring the local state. Retain the backend block in the private
operational copy (or add it by a follow-up public PR after successful migration).
Subsequent init must always select that remote backend. Never reuse the original
local-root checkout against a migrated deployment. Do not use `-reconfigure` to
replace migration or `force-unlock` without identifying the live lock holder.

State versions retain at least ten newer versions and thirty days since becoming
noncurrent. Plans expire after seven days, plus seven-day soft deletion. No Bucket
Lock. Budget alerts and initial spend review remain a separate human operation.
