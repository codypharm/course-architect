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

locals {
  project = "ai-course-architect"
  env     = "prod"
}

module "cloudfront" {
  source                          = "../../modules/cloudfront"
  project                         = local.project
  env                             = local.env
  frontend_bucket_regional_domain = module.s3.frontend_bucket_regional_domain
  frontend_oac_id                 = module.s3.frontend_oac_id
  alb_dns_name                    = module.alb.alb_dns_name
}

module "vpc" {
  source   = "../../modules/vpc"
  project  = local.project
  env      = local.env
  vpc_cidr = "10.1.0.0/16"
}

module "ecr" {
  source  = "../../modules/ecr"
  project = local.project
  env     = local.env
}

module "iam" {
  source  = "../../modules/iam"
  project = local.project
  env     = local.env
}

module "secrets" {
  source  = "../../modules/secrets"
  project = local.project
  env     = local.env
}

module "alb" {
  source            = "../../modules/alb"
  project           = local.project
  env               = local.env
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
}

module "s3" {
  source                      = "../../modules/s3"
  project                     = local.project
  env                         = local.env
  cloudfront_distribution_arn = module.cloudfront.distribution_arn
}

module "rds" {
  source                = "../../modules/rds"
  project               = local.project
  env                   = local.env
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  ecs_security_group_id = module.ecs.ecs_security_group_id
  db_password           = var.db_password
  max_acu               = 16
}

module "elasticache" {
  source                = "../../modules/elasticache"
  project               = local.project
  env                   = local.env
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  ecs_security_group_id = module.ecs.ecs_security_group_id
  node_type             = "cache.t3.small"
}

module "ecs" {
  source                = "../../modules/ecs"
  project               = local.project
  env                   = local.env
  vpc_id                = module.vpc.vpc_id
  vpc_cidr              = "10.1.0.0/16"
  private_subnet_ids    = module.vpc.private_subnet_ids
  alb_security_group_id = module.alb.security_group_id
  alb_target_group_arn  = module.alb.target_group_arn
  execution_role_arn    = module.iam.execution_role_arn
  task_role_arn         = module.iam.task_role_arn
  ecr_repository_url    = module.ecr.repository_url
  image_tag             = var.image_tag
  redis_endpoint        = module.elasticache.primary_endpoint
  db_endpoint           = module.rds.cluster_endpoint
  db_name               = module.rds.db_name
  db_username           = module.rds.db_username
  uploads_bucket        = module.s3.uploads_bucket
  vectors_bucket        = module.s3.vectors_bucket
  allowed_origins       = "https://${module.cloudfront.domain_name}"
  secret_arns           = module.secrets.secret_arns
  api_desired_count     = 2
  worker_desired_count  = 2
}
