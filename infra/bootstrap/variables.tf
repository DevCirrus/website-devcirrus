variable "project_id" {
  type        = string
  description = "Existing approved project ID. This root does not create projects or manage billing."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use a valid GCP project ID."
  }
}
variable "bootstrap_state_bucket" {
  type        = string
  description = "Approved globally unique bucket name, accessible only to bootstrap operators."
}
variable "site_state_bucket" {
  type        = string
  description = "Distinct approved globally unique bucket name for site state, private inputs and plans."
}
