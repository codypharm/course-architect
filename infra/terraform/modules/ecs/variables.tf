variable "project" { type = string }
variable "env" { type = string }
variable "vpc_id" { type = string }
variable "vpc_cidr" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "alb_security_group_id" { type = string }
variable "alb_target_group_arn" { type = string }
variable "execution_role_arn" { type = string }
variable "task_role_arn" { type = string }
variable "ecr_repository_url" { type = string }
variable "image_tag" {
  type    = string
  default = "latest"
}
variable "redis_endpoint" { type = string }
variable "db_endpoint" { type = string }
variable "db_name" { type = string }
variable "db_username" { type = string }
variable "uploads_bucket" { type = string }
variable "vectors_bucket" { type = string }
variable "allowed_origins" { type = string }
variable "secret_arns" { type = map(string) }
variable "api_desired_count" {
  type    = number
  default = 1
}
variable "worker_desired_count" {
  type    = number
  default = 1
}
