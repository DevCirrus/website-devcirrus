resource "google_firebase_hosting_site" "website" {
  provider        = google-beta
  project         = var.project_id
  site_id         = var.site_id
  deletion_policy = "PREVENT"
  lifecycle { prevent_destroy = true }
}
resource "google_firebase_hosting_custom_domain" "apex" {
  provider              = google-beta
  project               = var.project_id
  site_id               = google_firebase_hosting_site.website.site_id
  custom_domain         = "devcirrus.com"
  wait_dns_verification = false
  deletion_policy       = "PREVENT"
  lifecycle { prevent_destroy = true }
}
resource "google_firebase_hosting_custom_domain" "www" {
  provider              = google-beta
  project               = var.project_id
  site_id               = google_firebase_hosting_site.website.site_id
  custom_domain         = "www.devcirrus.com"
  redirect_target       = "devcirrus.com"
  wait_dns_verification = false
  deletion_policy       = "PREVENT"
  lifecycle { prevent_destroy = true }
}
