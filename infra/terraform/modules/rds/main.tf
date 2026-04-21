terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-${var.env}"
  subnet_ids = var.private_subnet_ids
  tags       = { Project = var.project, Env = var.env }
}

resource "aws_security_group" "rds" {
  name        = "${var.project}-${var.env}-rds"
  description = "Allow Postgres from ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.ecs_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.env}-rds" }
}

resource "aws_rds_cluster" "main" {
  cluster_identifier     = "${var.project}-${var.env}"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = "16.4"
  database_name          = "courses"
  master_username        = "courses_admin"
  master_password        = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = var.env != "prod"

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = var.max_acu
  }

  tags = { Project = var.project, Env = var.env }
}

resource "aws_rds_cluster_instance" "writer" {
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  tags = { Project = var.project, Env = var.env }
}
