terraform {
  backend "s3" {
    bucket         = "ai-course-architect-tf-state"
    key            = "staging/terraform.tfstate"
    region         = "eu-north-1"
    dynamodb_table = "ai-course-architect-tf-locks"
    encrypt        = true
  }
}
