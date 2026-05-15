# Implementation Tasks

## Task 1: Set up module structure and provider configuration

- [x] 1.1 Create the module directory structure: `modules/s3-tiered-storage/`
- [x] 1.2 Create `versions.tf` with required Terraform version (>= 1.0) and AWS provider version constraint
- [x] 1.3 Create `variables.tf` with all input variable declarations (bucket_name_prefix, lifecycle_transition_days, aws_region, environment, trusted_principal, encryption_type, kms_key_arn, tags)
- [x] 1.4 Add validation blocks to `bucket_name_prefix` (regex `^[a-z0-9-]+$`) and `lifecycle_transition_days` (>= 1)
- [x] 1.5 Add validation block to `encryption_type` (must be "AES256" or "aws:kms")

## Task 2: Create Standard Bucket with security configurations

- [x] 2.1 Create `main.tf` and define `aws_s3_bucket` resource for the Standard Bucket with naming convention `{prefix}-standard`
- [x] 2.2 Add `aws_s3_bucket_versioning` resource to enable versioning on Standard Bucket
- [x] 2.3 Add `aws_s3_bucket_server_side_encryption_configuration` resource with conditional AES-256 or KMS encryption
- [x] 2.4 Add `aws_s3_bucket_public_access_block` resource with all four settings enabled (block_public_acls, block_public_policy, ignore_public_acls, restrict_public_buckets)

## Task 3: Create Archive Bucket with security configurations

- [x] 3.1 Define `aws_s3_bucket` resource for the Archive Bucket with naming convention `{prefix}-archive`
- [x] 3.2 Add `aws_s3_bucket_versioning` resource to enable versioning on Archive Bucket
- [x] 3.3 Add `aws_s3_bucket_server_side_encryption_configuration` resource with conditional AES-256 or KMS encryption
- [x] 3.4 Add `aws_s3_bucket_public_access_block` resource with all four settings enabled

## Task 4: Configure Lifecycle Rule on Standard Bucket

- [x] 4.1 Add `aws_s3_bucket_lifecycle_configuration` resource on Standard Bucket
- [x] 4.2 Configure transition rule to GLACIER storage class using `var.lifecycle_transition_days`
- [x] 4.3 Set lifecycle rule status to "Enabled" with descriptive rule ID

## Task 5: Create IAM Role and Policy

- [x] 5.1 Define `aws_iam_role` resource with trust policy allowing `var.trusted_principal` to assume the role
- [x] 5.2 Define `aws_iam_policy` resource with only s3:PutObject and s3:GetObject actions
- [x] 5.3 Scope IAM policy resource to both bucket ARNs with `/*` suffix for object-level access
- [x] 5.4 Add `aws_iam_role_policy_attachment` to attach the policy to the role

## Task 6: Configure outputs

- [x] 6.1 Create `outputs.tf` with Standard Bucket ARN and ID outputs
- [x] 6.2 Add Archive Bucket ARN and ID outputs
- [x] 6.3 Add IAM Role ARN and name outputs
- [x] 6.4 Add IAM Policy ARN output

## Task 7: Add default tags and finalize

- [x] 7.1 Define a `locals` block that merges default tags (Environment, ManagedBy) with user-provided tags
- [x] 7.2 Apply merged tags to all resources that support tagging (buckets, IAM role, IAM policy)
- [x] 7.3 Run `terraform fmt` and `terraform validate` to verify module correctness
