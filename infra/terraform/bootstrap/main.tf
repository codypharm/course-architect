# Bootstrap — run once before any other Terraform environment.
# Creates the S3 bucket and DynamoDB table used as the remote state backend.
#
# Usage:
#   cd infra/terraform/bootstrap
#   terraform init
#   terraform apply
#
# After apply, copy the outputs into envs/staging/backend.tf and envs/prod/backend.tf.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "eu-north-1"
}

variable "project" {
  type    = string
  default = "ai-course-architect"
}

# ── S3 state bucket ─────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "tf_state" {
  bucket = "${var.project}-tf-state"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project   = var.project
    ManagedBy = "terraform-bootstrap"
  }
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── DynamoDB lock table ──────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "tf_locks" {
  name         = "${var.project}-tf-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Project   = var.project
    ManagedBy = "terraform-bootstrap"
  }
}

# ── Outputs ──────────────────────────────────────────────────────────────────────

output "state_bucket" {
  value       = aws_s3_bucket.tf_state.bucket
  description = "S3 bucket name for Terraform state"
}

output "lock_table" {
  value       = aws_dynamodb_table.tf_locks.name
  description = "DynamoDB table name for state locking"
}
