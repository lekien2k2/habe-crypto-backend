variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-southeast-1"
}

variable "bucket_name_prefix" {
  description = "Prefix for S3 bucket names (must be globally unique, lowercase)"
  type        = string
  default     = "habe-dreamsoft-lab"
}

variable "environment" {
  description = "Environment tag (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "trusted_principal" {
  description = "ARN of the AWS principal allowed to assume the backend role"
  type        = string
  default     = "arn:aws:iam::291162326645:user/Tech_role"
}
