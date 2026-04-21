output "alb_dns_name" {
  value = module.alb.alb_dns_name
}

output "cloudfront_domain" {
  value = module.cloudfront.domain_name
}

output "cloudfront_distribution_id" {
  value = module.cloudfront.distribution_id
}

output "frontend_bucket" {
  value = module.s3.frontend_bucket
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "cicd_access_key_id" {
  value     = module.iam.cicd_access_key_id
  sensitive = true
}

output "cicd_secret_access_key" {
  value     = module.iam.cicd_secret_access_key
  sensitive = true
}
