# -----------------------------------------------------
# Standard Bucket Outputs
# -----------------------------------------------------

output "standard_bucket_arn" {
  description = "ARN of the Standard S3 bucket"
  value       = aws_s3_bucket.standard.arn
}

output "standard_bucket_id" {
  description = "ID/name of the Standard S3 bucket"
  value       = aws_s3_bucket.standard.id
}

# -----------------------------------------------------
# Archive Bucket Outputs
# -----------------------------------------------------

output "archive_bucket_arn" {
  description = "ARN of the Archive S3 bucket"
  value       = aws_s3_bucket.archive.arn
}

output "archive_bucket_id" {
  description = "ID/name of the Archive S3 bucket"
  value       = aws_s3_bucket.archive.id
}

# -----------------------------------------------------
# IAM Role Outputs
# -----------------------------------------------------

output "iam_role_arn" {
  description = "ARN of the IAM role"
  value       = aws_iam_role.backend.arn
}

output "iam_role_name" {
  description = "Name of the IAM role"
  value       = aws_iam_role.backend.name
}

# -----------------------------------------------------
# IAM Policy Outputs
# -----------------------------------------------------

output "iam_policy_arn" {
  description = "ARN of the IAM policy"
  value       = aws_iam_policy.s3_access.arn
}
