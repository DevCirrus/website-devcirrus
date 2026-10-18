resource "google_dns_managed_zone" "website" {
  project     = var.project_id
  name        = var.zone_name
  dns_name    = "devcirrus.com."
  description = "DevCirrus authoritative zone; delegation requires separate approval."
  visibility  = "public"
  dnssec_config { state = var.dnssec_state }
  lifecycle { prevent_destroy = true }
}
resource "google_dns_record_set" "approved" {
  for_each     = var.rrsets
  project      = var.project_id
  managed_zone = google_dns_managed_zone.website.name
  name         = each.value.name
  type         = each.value.type
  ttl          = each.value.ttl
  rrdatas      = each.value.rrdatas
}
