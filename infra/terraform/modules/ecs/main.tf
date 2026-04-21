terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

resource "aws_cloudwatch_log_group" "services" {
  for_each          = toset(["api", "worker", "beat", "flower"])
  name              = "/ecs/${var.project}-${var.env}/${each.key}"
  retention_in_days = 30
  tags              = { Project = var.project, Env = var.env }
}

resource "aws_security_group" "ecs" {
  name        = "${var.project}-${var.env}-ecs"
  description = "ECS tasks - allow all egress, inbound only from ALB on 8000"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  ingress {
    from_port   = 5555
    to_port     = 5555
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.env}-ecs" }
}

resource "aws_ecs_cluster" "main" {
  name = "${var.project}-${var.env}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Project = var.project, Env = var.env }
}

locals {
  common_env = [
    { name = "AWS_REGION",         value = data.aws_region.current.name },
    { name = "S3_UPLOADS_BUCKET",  value = var.uploads_bucket },
    { name = "S3_VECTORS_BUCKET",  value = var.vectors_bucket },
    { name = "S3_VECTORS_INDEX",   value = "course-chunks" },
    { name = "REDIS_URL",          value = "redis://${var.redis_endpoint}" },
    { name = "DB_HOST",            value = var.db_endpoint },
    { name = "DB_NAME",            value = var.db_name },
    { name = "DB_USER",            value = var.db_username },
    { name = "ALLOWED_ORIGINS",    value = var.allowed_origins },
    { name = "LANGSMITH_TRACING",  value = "true" },
    { name = "LANGSMITH_ENDPOINT", value = "https://api.smith.langchain.com" },
    { name = "LANGSMITH_PROJECT",  value = "${var.project}-${var.env}" },
  ]

  common_secrets = [
    { name = "OPENAI_API_KEY",    valueFrom = var.secret_arns["openai-api-key"] },
    { name = "LANGSMITH_API_KEY", valueFrom = var.secret_arns["langsmith-api-key"] },
    { name = "CLERK_JWKS_URL",    valueFrom = var.secret_arns["clerk-jwks-url"] },
    { name = "CLERK_SECRET_KEY",  valueFrom = var.secret_arns["clerk-secret-key"] },
    { name = "SERPER_API_KEY",    valueFrom = var.secret_arns["serper-api-key"] },
    { name = "TAVILY_API_KEY",    valueFrom = var.secret_arns["tavily-api-key"] },
    { name = "VALYU_API_KEY",     valueFrom = var.secret_arns["valyu-api-key"] },
    { name = "DB_PASSWORD",       valueFrom = var.secret_arns["db-password"] },
  ]

  services = {
    api = {
      cpu     = 512
      memory  = 1024
      command = ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
    }
    worker = {
      cpu     = 2048
      memory  = 4096
      command = ["celery", "-A", "celery_app.worker", "worker", "-Q", "high_priority,generation,retry", "--loglevel=info"]
    }
    beat = {
      cpu     = 256
      memory  = 512
      command = ["celery", "-A", "celery_app.worker", "beat", "--loglevel=info"]
    }
    flower = {
      cpu     = 256
      memory  = 512
      command = ["celery", "-A", "celery_app.worker", "flower", "--port=5555"]
    }
  }
}

resource "aws_ecs_task_definition" "services" {
  for_each = local.services

  family                   = "${var.project}-${var.env}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([{
    name      = each.key
    image     = "${var.ecr_repository_url}:${var.image_tag}"
    command   = each.value.command
    essential = true

    environment = local.common_env
    secrets     = local.common_secrets

    portMappings = each.key == "api" ? [{ containerPort = 8000, protocol = "tcp" }] : each.key == "flower" ? [{ containerPort = 5555, protocol = "tcp" }] : []

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/${var.project}-${var.env}/${each.key}"
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = { Project = var.project, Env = var.env }
}

resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services["api"].arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.ecs.id]
  }

  load_balancer {
    target_group_arn = var.alb_target_group_arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [aws_cloudwatch_log_group.services]
  tags       = { Project = var.project, Env = var.env }
}

resource "aws_ecs_service" "worker" {
  name            = "worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services["worker"].arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.ecs.id]
  }

  depends_on = [aws_cloudwatch_log_group.services]
  tags       = { Project = var.project, Env = var.env }
}

resource "aws_ecs_service" "beat" {
  name            = "beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services["beat"].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.ecs.id]
  }

  depends_on = [aws_cloudwatch_log_group.services]
  tags       = { Project = var.project, Env = var.env }
}

resource "aws_ecs_service" "flower" {
  name            = "flower"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services["flower"].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.ecs.id]
  }

  depends_on = [aws_cloudwatch_log_group.services]
  tags       = { Project = var.project, Env = var.env }
}

resource "aws_appautoscaling_target" "api" {
  max_capacity       = 5
  min_capacity       = var.api_desired_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/api"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
  depends_on         = [aws_ecs_service.api]
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.project}-${var.env}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 70
    scale_in_cooldown  = 300
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
