output "uploads_bucket" {
  value = aws_s3_bucket.uploads.bucket
}

output "vectors_bucket" {
  value = "${var.project}-${var.env}-vectors"
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "frontend_oac_id" {
  value = aws_cloudfront_origin_access_control.frontend.id
}

output "frontend_bucket_regional_domain" {
  value = aws_s3_bucket.frontend.bucket_regional_domain_name
}
