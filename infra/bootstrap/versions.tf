terraform {
  required_version = "= 1.16.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.7.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "8.7.0"
    }
  }
  # Intentionally local for the FIRST approved bootstrap. After the buckets
  # exist, add backend "gcs" {} via the documented migration, never init -reconfigure.
}
