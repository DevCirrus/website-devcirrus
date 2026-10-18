# Hosting and DNS

Run only after bootstrap and an explicit plan approval. This root owns one
specific Hosting site, two domain associations, a DNS zone and explicitly
adopted RRsets. It never owns Hosting content/releases, registrar NS/DS, billing,
IAM or legacy sites. Target the dedicated project from bootstrap outputs.
Firebase may create a default site when enabling the project: inventory it and
import it only if it is the approved DevCirrus site; do not create a second owner.

Import existing resources that this root will own, with reviewed ownership:

```sh
terraform -chdir=infra/site init -backend-config="$PRIVATE_BACKEND"
terraform -chdir=infra/site import -var-file="$PRIVATE_INPUTS" \
  google_firebase_hosting_site.website "projects/$SITE_PROJECT_ID/sites/$SITE_ID"
# Domain ID: projects/PROJECT/sites/SITE/customDomains/DOMAIN
# Zone ID: projects/PROJECT/managedZones/ZONE
```

Imports mutate state and require approval. Initially use `rrsets = {}` and do not
delegate NS. Domain creation does not wait for DNS. Save `terraform output -json
domain_status` privately and use actual required values, never a sample Hosting
IP. Empty rrsets leaves existing unmanaged records alone; removing an adopted
entry deletes it and needs review. NS/SOA are Cloud DNS managed; registrar DS is
outside this root.

For existing TXT/CAA RRsets, import and supply the union of current and new
approved values. Never replace mail or verifications with a single challenge.
Do not delegate an empty/incomplete zone. Copy and compare all legacy records,
even those outside Terraform management. Keep inputs and plans private.

CI DNS Admin/Hosting Admin roles span the selected project and can affect other
sites/zones. Inventory, approve this scope and evaluate narrower permissions
before activating CI. The dedicated project contains their scope; these grants
are not site-only IAM.
