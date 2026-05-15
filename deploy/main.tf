terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "s3_tiered_storage" {
  source = "../modules/s3-tiered-storage"

  bucket_name_prefix        = var.bucket_name_prefix
  aws_region                = var.aws_region
  environment               = var.environment
  trusted_principal         = var.trusted_principal
  encryption_type           = "AES256"
  lifecycle_transition_days = 30

  tags = {
    Project = "HABE-Crypto-Backend"
    Lab     = "Hierarchical-Encryption"
  }
}

output "standard_bucket_name" {
  description = "Name of the Standard S3 bucket"
  value       = module.s3_tiered_storage.standard_bucket_id
}

output "archive_bucket_name" {
  description = "Name of the Archive S3 bucket"
  value       = module.s3_tiered_storage.archive_bucket_id
}

output "iam_role_arn" {
  description = "ARN of the backend IAM role"
  value       = module.s3_tiered_storage.iam_role_arn
}
