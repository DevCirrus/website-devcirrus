variable "project_id" {
  type        = string
  description = "Approved globally available ID for the new dedicated project. Preferred candidate: website-devcirrus; availability is not assumed."
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

variable "billing_account" {
  type        = string
  sensitive   = true
  description = "Approved billing account supplied privately; association requires explicit plan approval."
  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account))
    error_message = "Supply a valid billing account ID privately."
  }
}
variable "org_id" {
  type        = string
  default     = null
  description = "Approved organisation ID. Set exactly one of org_id or folder_id."
  validation {
    condition     = var.org_id == null || can(regex("^[0-9]+$", var.org_id))
    error_message = "Use a numeric organisation ID or null."
  }
}
variable "folder_id" {
  type        = string
  default     = null
  description = "Approved folder ID. Set exactly one of org_id or folder_id."
  validation {
    condition     = var.folder_id == null || can(regex("^[0-9]+$", var.folder_id))
    error_message = "Use a numeric folder ID or null."
  }
}
