variable "project_id" {
  type        = string
  description = "Dedicated project created by the approved human bootstrap."
}
variable "site_id" {
  type        = string
  description = "Approved globally unique site ID; do not adopt another website's default site."
}
variable "zone_name" {
  type        = string
  description = "Approved new or imported Cloud DNS managed zone name."
}
variable "dnssec_state" {
  type        = string
  description = "Explicit approved DNSSEC state; registrar DS is handled separately."
  validation {
    condition     = contains(["on", "off"], var.dnssec_state)
    error_message = "Specify the reviewed DNSSEC state explicitly."
  }
}
variable "rrsets" {
  description = "Approved COMPLETE values for adopted RRsets, supplied privately. Key = FQDN|TYPE."
  type = map(object({
    name    = string
    type    = string
    ttl     = number
    rrdatas = list(string)
  }))
  default = {}
  validation {
    condition = alltrue([for k, r in var.rrsets :
      k == "${r.name}|${r.type}" &&
      (r.name == "devcirrus.com." || endswith(r.name, ".devcirrus.com.")) &&
      contains(["A", "AAAA", "CNAME", "MX", "TXT", "CAA", "SRV", "HTTPS", "SVCB"], r.type) &&
      r.ttl >= 30 && floor(r.ttl) == r.ttl && length(r.rrdatas) > 0
    ])
    error_message = "Use unique FQDN|TYPE keys in devcirrus.com, supported type, integer TTL >=30 and complete values. NS/SOA/DS are separate."
  }
  validation {
    condition = alltrue([for r in values(var.rrsets) : r.type != "CNAME" ||
      (r.name != "devcirrus.com." && length(r.rrdatas) == 1 &&
      length([for other in values(var.rrsets) : other if other.name == r.name]) == 1)
    ])
    error_message = "CNAME must have one value, cannot be at the apex, and cannot coexist with another RRset at that name."
  }
}
