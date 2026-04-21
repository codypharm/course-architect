output "secret_arns" {
  description = "Map of secret name to ARN, used in ECS task definitions"
  value       = { for k, v in aws_secretsmanager_secret.app : k => v.arn }
}
