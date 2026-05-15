#!/bin/bash
# Initialize LocalStack S3 buckets for HABE Crypto Backend

echo "Creating S3 buckets for HABE tiered storage..."

# Create Standard bucket
awslocal s3 mb s3://habe-standard-storage
echo "✓ Created: habe-standard-storage (Standard tier)"

# Create Archive bucket
awslocal s3 mb s3://habe-archive-storage
echo "✓ Created: habe-archive-storage (Archive tier)"

# Verify
echo ""
echo "S3 Buckets:"
awslocal s3 ls

echo ""
echo "LocalStack S3 initialization complete!"
