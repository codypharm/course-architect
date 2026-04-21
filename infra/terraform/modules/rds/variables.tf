variable "project" { type = string }
variable "env" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "ecs_security_group_id" { type = string }
variable "db_password" {
  type      = string
  sensitive = true
}
variable "max_acu" {
  type    = number
  default = 4
}
