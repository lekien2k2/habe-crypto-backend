variable "bucket_name_prefix" {
  description = "Prefix for S3 bucket names. Must contain only lowercase letters, numbers, and hyphens."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.bucket_name_prefix))
    error_message = "bucket_name_prefix must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "lifecycle_transition_days" {
  description = "Number of days before transitioning objects from Standard to Glacier storage class."
  type        = number
  default     = 30

  validation {
    condition     = var.lifecycle_transition_days >= 1
    error_message = "lifecycle_transition_days must be at least 1."
  }
}

variable "aws_region" {
  description = "AWS region for resources."
  type        = string
}

variable "environment" {
  description = "Environment tag value (e.g., dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "trusted_principal" {
  description = "ARN of the principal allowed to assume the IAM role."
  type        = string
}

variable "encryption_type" {
  description = "Encryption type for S3 buckets. Must be \"AES256\" or \"aws:kms\"."
  type        = string
  default     = "AES256"

  validation {
    condition     = contains(["AES256", "aws:kms"], var.encryption_type)
    error_message = "encryption_type must be \"AES256\" or \"aws:kms\"."
  }
}

variable "kms_key_arn" {
  description = "KMS key ARN for server-side encryption. Required if encryption_type is \"aws:kms\"."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
