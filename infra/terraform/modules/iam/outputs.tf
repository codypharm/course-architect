output "execution_role_arn" {
  value = aws_iam_role.execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "cicd_access_key_id" {
  value     = aws_iam_access_key.cicd.id
  sensitive = true
}

output "cicd_secret_access_key" {
  value     = aws_iam_access_key.cicd.secret
  sensitive = true
}
