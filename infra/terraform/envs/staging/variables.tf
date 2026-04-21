variable "aws_region" {
  type    = string
  default = "eu-north-1"
}

variable "image_tag" {
  type    = string
  default = "staging-latest"
}

variable "db_password" {
  type      = string
  sensitive = true
}
