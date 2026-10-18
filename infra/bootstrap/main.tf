resource "google_project" "website" {
  project_id          = var.project_id
  name                = "website-devcirrus"
  org_id              = var.org_id
  folder_id           = var.folder_id
  billing_account     = var.billing_account
  deletion_policy     = "PREVENT"
  auto_create_network = false
  labels = {
    application = "devcirrus-website"
    environment = "production"
    firebase    = "enabled"
  }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = (var.org_id != null) != (var.folder_id != null)
      error_message = "Explicitly approve exactly one organisation or folder parent."
    }
  }
}
locals {
  apis = toset([
    "cloudresourcemanager.googleapis.com", "serviceusage.googleapis.com",
    "cloudbilling.googleapis.com", "iam.googleapis.com", "iamcredentials.googleapis.com",
    "sts.googleapis.com", "storage.googleapis.com", "dns.googleapis.com",
    "firebase.googleapis.com", "firebasehosting.googleapis.com"
  ])
}
resource "google_project_service" "api" {
  for_each           = local.apis
  project            = google_project.website.project_id
  service            = each.value
  disable_on_destroy = false
}
resource "google_firebase_project" "website" {
  provider   = google-beta
  project    = google_project.website.project_id
  depends_on = [google_project_service.api]
  lifecycle { prevent_destroy = true }
}
resource "google_storage_bucket" "state" {
  for_each                    = { bootstrap = var.bootstrap_state_bucket, site = var.site_state_bucket }
  project                     = google_project.website.project_id
  name                        = each.value
  location                    = "europe-west1"
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning { enabled = true }
  soft_delete_policy { retention_duration_seconds = 604800 }
  lifecycle_rule {
    action { type = "Delete" }
    condition {
      days_since_noncurrent_time = 30
      num_newer_versions         = 10
      matches_prefix             = ["bootstrap/", "site/"]
    }
  }
  dynamic "lifecycle_rule" {
    for_each = each.key == "site" ? [1] : []
    content {
      action { type = "Delete" }
      condition {
        age            = 7
        matches_prefix = ["plans/"]
      }
    }
  }
  depends_on = [google_project_service.api]
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.bootstrap_state_bucket != var.site_state_bucket
      error_message = "Bootstrap and site state must use different buckets."
    }
  }
}
