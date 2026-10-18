mock_provider "google" {}
mock_provider "google-beta" {}
variables {
  project_id   = "devcirrus-test-only"
  site_id      = "devcirrus-test-only"
  zone_name    = "devcirrus-test-only"
  dnssec_state = "on"
}
run "domains_without_cutover" {
  command = plan
  assert {
    condition     = google_firebase_hosting_custom_domain.www.redirect_target == "devcirrus.com" && !google_firebase_hosting_custom_domain.www.wait_dns_verification
    error_message = "www must redirect using Hosting, without waiting on a DNS cutover."
  }
  assert {
    condition     = length(google_dns_record_set.approved) == 0 && google_dns_managed_zone.website.dnssec_config[0].state == "on"
    error_message = "Initial plan must not invent DNS records or switch DNSSEC."
  }
}
run "reject_apex_cname" {
  command = plan
  variables {
    rrsets = {
      "devcirrus.com.|CNAME" = { name = "devcirrus.com.", type = "CNAME", ttl = 300, rrdatas = ["example.invalid."] }
    }
  }
  expect_failures = [var.rrsets]
}
run "reject_duplicate_rrset_identity" {
  command = plan
  variables {
    rrsets = {
      arbitrary = { name = "devcirrus.com.", type = "TXT", ttl = 300, rrdatas = ["\"example\""] }
    }
  }
  expect_failures = [var.rrsets]
}
