# DNS cutover approval record (F5)

This is a procedure/template, not a completed migration. No real DNS values,
account export or approved cutover plan are stored here. Keep the completed
record, inventories and evidence private. Never infer complete DNS from a few
public lookups.

Before requesting authorization, prepare a reviewable record containing:

1. Existing and proposed authority, zone/state ownership and nameservers;
   registrar access verified read-only, complete zone export and current DS,
   DNSSEC, TTLs, mail/verification/subdomain records saved privately.
2. Actual Hosting `required_dns_updates` for apex and www, including certificate
   state and ownership challenges. No sample IP address is an approved value.
3. Exact old/new RRsets, full merged TXT/CAA values, TTL schedule and imports.
   DNSSEC state in inputs must agree with the reviewed sequence; do not turn it
   off by default. Do not point www at a service that cannot terminate its TLS.
4. Private Terraform plan and source/lock hashes; no unexpected replacements,
   deletes or changes outside adopted records. A private normalized comparison
   of the complete old/new zones, with every expected difference reviewed.
5. Current official DNS, Hosting and GCS pricing, account-specific transfer quota,
   incremental monthly estimate, budget/alerts and expected retention overhead.
   Earlier price research is not a fresh quote or a spending approval. In a
   shared project, separate existing costs from this site's incremental costs.
6. Exact proposed operation for Pedro to authorize: resources first, DNS records
   next, NS/DS at registrar only when required. Record each approval once and
   execute/verify the authorized operation without asking the same approval again.
7. Previous RRsets/NS/DS, old provider retained and reachable, rollback triggers,
   cache/propagation delay and a DNSSEC-compatible restoration sequence.

## Sequence after explicit authorization

- Provision/import the selected Hosting site and associations without waiting
  for DNS; release and verify content on its `web.app` hostname.
- Create/import Cloud DNS zone only as approved. Copy every legacy record before
  delegating, including records that remain outside Terraform ownership.
- Lower appropriate TTLs with enough lead time for their previous values. Query
  old/new authoritative servers directly; compare complete normalized exports.
- For DS-enabled domains, coordinate the specific signed migration with both
  providers. If the approved path removes old DS, wait its TTL before changing
  authority, then verify and introduce new DS only with matching new keys. Never
  delegate different keys under stale DS. Retain mail and verification records.
- Apply the reviewed Hosting challenges and routing RRsets; switch registrar NS
  only after the complete new zone is verified. A CNAME alone is not HTTP 301.
- Wait for ownership and both certificates, then run the acceptance procedure.
  Up to 24 hours may be required for DNS/certificates; pending is not accepted.
- Preserve ownership TXT and merge any required CAA issuers into the existing
  policy. Confirm email and services with the owner. Record old/new authority,
  DNSSEC validation, plan/apply/run/release references and observed costs privately.

## Zone comparison helper

`scripts/compare-dns.py OLD.json NEW.json APPROVED-DIFFERENCES.json` compares
normalized complete exports shaped like Cloud DNS record-set list JSON
(`name`, `type`, `ttl`, `rrdatas`). Convert a registrar export privately first.
The third JSON file is an exact list of allowed `FQDN|TYPE` differences, including
NS/SOA/DS or TTL changes when appropriate. The helper rejects duplicates and
reports both unapproved changes and expected changes that did not occur.

This detects omitted/changed known records, not unknown records missing from
both exports. It is a private operator command, never a public CI step. Successful
comparison is one check alongside direct authority, resolver, DNSSEC and mail
verification.
