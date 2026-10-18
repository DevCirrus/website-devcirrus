mock_provider "google" {
  mock_resource "google_service_account" {
    defaults = {
      name  = "projects/devcirrus-test-only/serviceAccounts/website-mock@devcirrus-test-only.iam.gserviceaccount.com"
      email = "website-mock@devcirrus-test-only.iam.gserviceaccount.com"
    }
  }
}
mock_provider "google-beta" {}
variables {
  project_id             = "devcirrus-test-only"
  bootstrap_state_bucket = "devcirrus-test-bootstrap"
  site_state_bucket      = "devcirrus-test-site"
}
run "identity_boundaries" {
  command = apply
  assert {
    condition = alltrue([for k, p in google_iam_workload_identity_pool_provider.pipeline :
      strcontains(p.attribute_condition, "assertion.repository_id == '1424246574'") &&
      strcontains(p.attribute_condition, "assertion.repository_owner_id == '92319814'") &&
      strcontains(p.attribute_condition, "assertion.ref == 'refs/heads/main'") &&
      strcontains(p.attribute_condition, "assertion.workflow_ref == 'DevCirrus/website-devcirrus/.github/workflows/${local.pipelines[k].workflow}@refs/heads/main'") &&
      strcontains(p.attribute_condition, "assertion.event_name == '${local.pipelines[k].event}'") &&
      strcontains(p.attribute_condition, "assertion.sub == 'repo:DevCirrus/website-devcirrus:environment:${local.pipelines[k].environment}'")
    ])
    error_message = "Federation must bind immutable repository/owner IDs, main, workflow, event and environment."
  }
  assert {
    condition = alltrue([for k, b in google_service_account_iam_member.federation :
      endswith(b.member, "/attribute.pipeline/${k}")
    ])
    error_message = "Each identity must trust only its pipeline, not every provider in the pool."
  }
  assert {
    condition     = toset(keys(google_storage_bucket_iam_member.site_state)) == toset(["plan", "apply"])
    error_message = "Content identity must not access Terraform state."
  }
  assert {
    condition = alltrue([for p in google_project_iam_member.pipeline :
      !contains(["roles/owner", "roles/editor", "roles/resourcemanager.projectIamAdmin", "roles/iam.serviceAccountAdmin"], p.role)
    ])
    error_message = "CI must not receive broad administrative roles."
  }
}
