output "default_url" { value = google_firebase_hosting_site.website.default_url }
output "name_servers" { value = google_dns_managed_zone.website.name_servers }
output "domain_status" {
  description = "Private evidence; successful apply does not prove HTTPS."
  value = { for key, domain in {
    apex = google_firebase_hosting_custom_domain.apex,
    www  = google_firebase_hosting_custom_domain.www
    } : key => {
    required_dns_updates = domain.required_dns_updates
    host_state           = domain.host_state
    ownership_state      = domain.ownership_state
    cert                 = domain.cert
    issues               = domain.issues
  } }
  sensitive = true
}
