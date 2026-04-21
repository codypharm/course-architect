terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

locals {
  secret_names = [
    "openai-api-key",
    "langsmith-api-key",
    "clerk-jwks-url",
    "clerk-secret-key",
    "serper-api-key",
    "tavily-api-key",
    "valyu-api-key",
    "db-password",
  ]
}

resource "aws_secretsmanager_secret" "app" {
  for_each = toset(local.secret_names)

  name        = "${var.project}/${var.env}/${each.key}"
  description = "${each.key} for ${var.project} ${var.env}"

  recovery_window_in_days = var.env == "prod" ? 7 : 0

  tags = { Project = var.project, Env = var.env }
}

resource "aws_secretsmanager_secret_version" "app" {
  for_each = aws_secretsmanager_secret.app

  secret_id     = each.value.id
  secret_string = "PLACEHOLDER - set this before deploying"

  lifecycle {
    ignore_changes = [secret_string]
  }
}
