output "project_id" { value = data.google_project.website.project_id }
output "state_buckets" { value = { for k, v in google_storage_bucket.state : k => v.name } }
output "workload_identity_providers" { value = { for k, v in google_iam_workload_identity_pool_provider.pipeline : k => v.name } }
output "service_accounts" { value = { for k, v in google_service_account.pipeline : k => v.email } }
