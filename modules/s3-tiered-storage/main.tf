# -----------------------------------------------------
# Local Values
# -----------------------------------------------------

locals {
  default_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
  merged_tags = merge(local.default_tags, var.tags)
}

# -----------------------------------------------------
# Standard Bucket
# -----------------------------------------------------

resource "aws_s3_bucket" "standard" {
  bucket = "${var.bucket_name_prefix}-standard"
  tags   = local.merged_tags
}

resource "aws_s3_bucket_versioning" "standard" {
  bucket = aws_s3_bucket.standard.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "standard" {
  bucket = aws_s3_bucket.standard.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.encryption_type
      kms_master_key_id = var.encryption_type == "aws:kms" ? var.kms_key_arn : null
    }
  }
}

resource "aws_s3_bucket_public_access_block" "standard" {
  bucket = aws_s3_bucket.standard.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "standard" {
  bucket = aws_s3_bucket.standard.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    transition {
      days          = var.lifecycle_transition_days
      storage_class = "GLACIER"
    }
  }
}

# -----------------------------------------------------
# Archive Bucket
# -----------------------------------------------------

resource "aws_s3_bucket" "archive" {
  bucket = "${var.bucket_name_prefix}-archive"
  tags   = local.merged_tags
}

resource "aws_s3_bucket_versioning" "archive" {
  bucket = aws_s3_bucket.archive.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.encryption_type
      kms_master_key_id = var.encryption_type == "aws:kms" ? var.kms_key_arn : null
    }
  }
}

resource "aws_s3_bucket_public_access_block" "archive" {
  bucket = aws_s3_bucket.archive.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------
# IAM Role and Policy
# -----------------------------------------------------

resource "aws_iam_role" "backend" {
  name = "${var.bucket_name_prefix}-backend-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = var.trusted_principal
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.merged_tags
}

resource "aws_iam_policy" "s3_access" {
  name = "${var.bucket_name_prefix}-s3-access-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = [
          "${aws_s3_bucket.standard.arn}/*",
          "${aws_s3_bucket.archive.arn}/*"
        ]
      }
    ]
  })

  tags = local.merged_tags
}

resource "aws_iam_role_policy_attachment" "backend_s3_access" {
  role       = aws_iam_role.backend.name
  policy_arn = aws_iam_policy.s3_access.arn
}
