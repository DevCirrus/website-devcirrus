locals {
  pipelines = {
    content = {
      account = "website-deploy", environment = "production", workflow = "deploy.yml", event = "push"
      roles   = ["roles/firebasehosting.admin", "roles/serviceusage.apiKeysViewer", "roles/serviceusage.serviceUsageConsumer"]
    }
    plan = {
      account = "website-infra-plan", environment = "infrastructure-plan", workflow = "infra.yml", event = "workflow_dispatch"
      roles   = ["roles/firebasehosting.viewer", "roles/dns.reader", "roles/serviceusage.serviceUsageConsumer"]
    }
    apply = {
      account = "website-infra-apply", environment = "infrastructure", workflow = "infra.yml", event = "workflow_dispatch"
      roles   = ["roles/firebasehosting.admin", "roles/dns.admin", "roles/serviceusage.serviceUsageConsumer"]
    }
  }
  project_roles = merge([for pipeline, config in local.pipelines : {
    for role in config.roles : "${pipeline}:${role}" => { pipeline = pipeline, role = role }
  }]...)
}
resource "google_service_account" "pipeline" {
  for_each     = local.pipelines
  project      = google_project.website.project_id
  account_id   = each.value.account
  display_name = "DevCirrus ${each.key} pipeline"
  depends_on   = [google_project_service.api]
}
resource "google_project_iam_member" "pipeline" {
  for_each = local.project_roles
  project  = google_project.website.project_id
  role     = each.value.role
  member   = "serviceAccount:${google_service_account.pipeline[each.value.pipeline].email}"
}
resource "google_project_iam_custom_role" "project_read" {
  project     = google_project.website.project_id
  role_id     = "websiteProjectRead"
  title       = "Website project metadata read"
  permissions = ["resourcemanager.projects.get"]
  depends_on  = [google_project_service.api]
}
resource "google_project_iam_member" "project_read" {
  for_each = toset(["plan", "apply"])
  project  = google_project.website.project_id
  role     = google_project_iam_custom_role.project_read.name
  member   = "serviceAccount:${google_service_account.pipeline[each.key].email}"
}
resource "google_storage_bucket_iam_member" "site_state" {
  for_each = toset(["plan", "apply"])
  bucket   = google_storage_bucket.state["site"].name
  role     = "roles/storage.objectAdmin"
  member   = "serviceAccount:${google_service_account.pipeline[each.key].email}"
}
resource "google_iam_workload_identity_pool" "github" {
  project                   = google_project.website.project_id
  workload_identity_pool_id = "website-github"
  display_name              = "DevCirrus website GitHub"
  depends_on                = [google_project_service.api]
}
resource "google_iam_workload_identity_pool_provider" "pipeline" {
  for_each                           = local.pipelines
  project                            = google_project.website.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = each.key
  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
    "attribute.ref"                 = "assertion.ref"
    "attribute.workflow_ref"        = "assertion.workflow_ref"
    "attribute.event_name"          = "assertion.event_name"
    "attribute.pipeline"            = "'${each.key}'"
  }
  attribute_condition = join(" && ", [
    "assertion.repository_id == '1424246574'",
    "assertion.repository_owner_id == '92319814'",
    "assertion.ref == 'refs/heads/main'",
    "assertion.workflow_ref == 'DevCirrus/website-devcirrus/.github/workflows/${each.value.workflow}@refs/heads/main'",
    "assertion.event_name == '${each.value.event}'",
    "assertion.sub == 'repo:DevCirrus/website-devcirrus:environment:${each.value.environment}'"
  ])
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}
resource "google_service_account_iam_member" "federation" {
  for_each           = local.pipelines
  service_account_id = google_service_account.pipeline[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.pipeline/${each.key}"
}
