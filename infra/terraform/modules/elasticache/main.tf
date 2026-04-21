terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project}-${var.env}"
  subnet_ids = var.private_subnet_ids
  tags       = { Project = var.project, Env = var.env }
}

resource "aws_security_group" "redis" {
  name        = "${var.project}-${var.env}-redis"
  description = "Allow Redis from ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.ecs_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.env}-redis" }
}

resource "aws_elasticache_cluster" "main" {
  cluster_id           = "${var.project}-${var.env}"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = { Project = var.project, Env = var.env }
}
