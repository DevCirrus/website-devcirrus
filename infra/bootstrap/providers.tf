provider "google" {
  project               = var.project_id
  user_project_override = false
}
provider "google-beta" {
  project               = var.project_id
  billing_project       = var.project_id
  user_project_override = true
}
