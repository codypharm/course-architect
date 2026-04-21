terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_role" "execution" {
  name = "${var.project}-${var.env}-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Project = var.project, Env = var.env }
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "read-secrets"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.project}/${var.env}/*"
    }]
  })
}

resource "aws_iam_role" "task" {
  name = "${var.project}-${var.env}-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Project = var.project, Env = var.env }
}

resource "aws_iam_role_policy" "task_s3" {
  name = "s3-access"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.project}-${var.env}-uploads",
          "arn:aws:s3:::${var.project}-${var.env}-uploads/*",
        ]
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket",
                  "s3vectors:PutVectors", "s3vectors:GetVectors", "s3vectors:DeleteVectors",
                  "s3vectors:QueryVectors", "s3vectors:CreateIndex", "s3vectors:DescribeIndex"]
        Resource = [
          "arn:aws:s3:::${var.project}-${var.env}-vectors",
          "arn:aws:s3:::${var.project}-${var.env}-vectors/*",
        ]
      }
    ]
  })
}

resource "aws_iam_user" "cicd" {
  name = "${var.project}-cicd"
  tags = { Project = var.project }
}

resource "aws_iam_access_key" "cicd" {
  user = aws_iam_user.cicd.name
}

resource "aws_iam_user_policy" "cicd" {
  name = "cicd-deploy"
  user = aws_iam_user.cicd.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
          "ecr:DescribeRepositories",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeClusters",
          "ecs:RegisterTaskDefinition",
          "ecs:DescribeTaskDefinition",
          "iam:PassRole",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetObject"]
        Resource = [
          "arn:aws:s3:::${var.project}-staging-frontend",
          "arn:aws:s3:::${var.project}-staging-frontend/*",
          "arn:aws:s3:::${var.project}-prod-frontend",
          "arn:aws:s3:::${var.project}-prod-frontend/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject", "s3:PutObject", "s3:ListBucket",
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem",
        ]
        Resource = [
          "arn:aws:s3:::${var.project}-tf-state",
          "arn:aws:s3:::${var.project}-tf-state/*",
          "arn:aws:dynamodb:*:*:table/${var.project}-tf-locks",
        ]
      },
    ]
  })
}
