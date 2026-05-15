# Hướng dẫn Deploy lên AWS

Tài liệu này hướng dẫn chi tiết cách triển khai toàn bộ hệ thống HABE Crypto Backend lên AWS, bao gồm:
- Hạ tầng S3 Tiered Storage (Terraform)
- Backend API (ECS Fargate hoặc EC2)

---

## Mục lục

1. [Yêu cầu trước khi bắt đầu](#1-yêu-cầu-trước-khi-bắt-đầu)
2. [Cấu hình AWS CLI](#2-cấu-hình-aws-cli)
3. [Triển khai hạ tầng S3 (Terraform)](#3-triển-khai-hạ-tầng-s3-terraform)
4. [Build và Push Docker Image (ECR)](#4-build-và-push-docker-image-ecr)
5. [Deploy Backend API (ECS Fargate)](#5-deploy-backend-api-ecs-fargate)
6. [Deploy Backend API (EC2 — phương án đơn giản)](#6-deploy-backend-api-ec2--phương-án-đơn-giản)
7. [Kiểm tra và Test](#7-kiểm-tra-và-test)
8. [Dọn dẹp tài nguyên](#8-dọn-dẹp-tài-nguyên)
9. [Chi phí ước tính](#9-chi-phí-ước-tính)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Yêu cầu trước khi bắt đầu

### Tài khoản & Tools

| Tool | Version | Cài đặt |
|---|---|---|
| AWS Account | — | https://aws.amazon.com |
| AWS CLI | v2 | `msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi` |
| Terraform | >= 1.0 | https://developer.hashicorp.com/terraform/install |
| Docker Desktop | latest | https://www.docker.com/products/docker-desktop |
| Git | latest | https://git-scm.com |

### AWS Permissions cần thiết

User/Role của bạn cần có các quyền sau:
- `s3:*` (hoặc ít nhất CreateBucket, PutObject, GetObject)
- `iam:*` (CreateRole, CreatePolicy, AttachRolePolicy)
- `ecr:*` (nếu dùng ECS)
- `ecs:*` (nếu dùng ECS Fargate)
- `ec2:*` (nếu dùng EC2)
- `logs:*` (CloudWatch Logs)

> **Tip:** Dùng `AdministratorAccess` policy cho lab/dev. Không dùng cho production.

---

## 2. Cấu hình AWS CLI

```bash
# Cấu hình credentials
aws configure
```

Nhập:
```
AWS Access Key ID: <your-access-key>
AWS Secret Access Key: <your-secret-key>
Default region name: ap-southeast-1    # hoặc region bạn muốn
Default output format: json
```

Kiểm tra:
```bash
aws sts get-caller-identity
```

Output mẫu:
```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-username"
}
```

> **Ghi lại Account ID** (ví dụ: `123456789012`) — sẽ dùng ở các bước sau.

---

## 3. Triển khai hạ tầng S3 (Terraform)

### 3.1. Tạo file cấu hình Terraform

Tạo file `deploy/main.tf` ở thư mục gốc:

```hcl
# deploy/main.tf

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
  value = module.s3_tiered_storage.standard_bucket_id
}

output "archive_bucket_name" {
  value = module.s3_tiered_storage.archive_bucket_id
}

output "iam_role_arn" {
  value = module.s3_tiered_storage.iam_role_arn
}
```

Tạo file `deploy/variables.tf`:

```hcl
# deploy/variables.tf

variable "aws_region" {
  default = "ap-southeast-1"
}

variable "bucket_name_prefix" {
  default = "habe-lab"  # Đổi thành tên unique của bạn
}

variable "environment" {
  default = "dev"
}

variable "trusted_principal" {
  description = "ARN of your AWS account root or IAM user"
  # Thay bằng Account ID của bạn
  default = "arn:aws:iam::123456789012:root"
}
```

### 3.2. Chạy Terraform

```bash
cd deploy

# Khởi tạo
terraform init

# Xem plan (kiểm tra trước khi tạo)
terraform plan

# Apply (tạo tài nguyên thực tế)
terraform apply
```

Nhập `yes` khi được hỏi. Output sẽ hiển thị:
```
standard_bucket_name = "habe-lab-standard"
archive_bucket_name  = "habe-lab-archive"
iam_role_arn         = "arn:aws:iam::123456789012:role/habe-lab-backend-role"
```

> **Ghi lại** tên 2 bucket — sẽ dùng cho cấu hình Backend API.

### 3.3. Kiểm tra S3 buckets

```bash
aws s3 ls | grep habe
```

Output:
```
2024-01-15 10:30:00 habe-lab-standard
2024-01-15 10:30:01 habe-lab-archive
```

---

## 4. Build và Push Docker Image (ECR)

### 4.1. Tạo ECR Repository

```bash
# Thay region và account ID
AWS_REGION=ap-southeast-1
AWS_ACCOUNT_ID=123456789012

aws ecr create-repository \
  --repository-name habe-crypto-backend \
  --region $AWS_REGION
```

### 4.2. Login Docker vào ECR

```bash
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

### 4.3. Build Docker Image

```bash
# Từ thư mục gốc project
docker build -t habe-crypto-backend .
```

> **Lưu ý:** Build lần đầu mất 10-15 phút vì compile charm-crypto từ source.

### 4.4. Tag và Push

```bash
# Tag
docker tag habe-crypto-backend:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/habe-crypto-backend:latest

# Push
docker push \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/habe-crypto-backend:latest
```

---

## 5. Deploy Backend API (ECS Fargate)

### 5.1. Tạo ECS Cluster

```bash
aws ecs create-cluster --cluster-name habe-cluster
```

### 5.2. Tạo Task Execution Role

```bash
# Tạo trust policy file
cat > ecs-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Tạo role
aws iam create-role \
  --role-name habe-ecs-task-execution-role \
  --assume-role-policy-document file://ecs-trust-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name habe-ecs-task-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Attach S3 access (cho task role)
aws iam attach-role-policy \
  --role-name habe-ecs-task-execution-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

### 5.3. Tạo Task Definition

Tạo file `ecs-task-definition.json`:

```json
{
  "family": "habe-crypto-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::123456789012:role/habe-ecs-task-execution-role",
  "taskRoleArn": "arn:aws:iam::123456789012:role/habe-ecs-task-execution-role",
  "containerDefinitions": [
    {
      "name": "habe-backend",
      "image": "123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/habe-crypto-backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "S3_BUCKET_STANDARD", "value": "habe-lab-standard"},
        {"name": "S3_BUCKET_ARCHIVE", "value": "habe-lab-archive"},
        {"name": "AWS_REGION", "value": "ap-southeast-1"},
        {"name": "MAX_FILE_SIZE_MB", "value": "100"},
        {"name": "CORS_ORIGINS", "value": "[\"*\"]"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/habe-crypto-backend",
          "awslogs-region": "ap-southeast-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 15
      }
    }
  ]
}
```

> **Quan trọng:** Thay `123456789012` bằng Account ID thực của bạn, và `ap-southeast-1` bằng region bạn chọn.

```bash
# Tạo CloudWatch Log Group
aws logs create-log-group --log-group-name /ecs/habe-crypto-backend

# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json
```

### 5.4. Tạo Security Group

```bash
# Lấy VPC ID mặc định
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text)

# Tạo Security Group
SG_ID=$(aws ec2 create-security-group \
  --group-name habe-backend-sg \
  --description "HABE Backend API" \
  --vpc-id $VPC_ID \
  --query "GroupId" --output text)

# Mở port 8000
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 8000 \
  --cidr 0.0.0.0/0
```

### 5.5. Chạy Service

```bash
# Lấy subnet IDs
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[*].SubnetId" --output text | tr '\t' ',')

# Tạo service
aws ecs create-service \
  --cluster habe-cluster \
  --service-name habe-backend-service \
  --task-definition habe-crypto-backend \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}"
```

### 5.6. Lấy Public IP

```bash
# Đợi task running (30-60 giây)
aws ecs list-tasks --cluster habe-cluster --service-name habe-backend-service

# Lấy task ARN
TASK_ARN=$(aws ecs list-tasks --cluster habe-cluster --query "taskArns[0]" --output text)

# Lấy ENI ID
ENI_ID=$(aws ecs describe-tasks --cluster habe-cluster --tasks $TASK_ARN \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" --output text)

# Lấy Public IP
PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID \
  --query "NetworkInterfaces[0].Association.PublicIp" --output text)

echo "API URL: http://$PUBLIC_IP:8000"
echo "Docs: http://$PUBLIC_IP:8000/docs"
```

---

## 6. Deploy Backend API (EC2 — phương án đơn giản)

> Phương án này đơn giản hơn ECS, phù hợp cho demo/lab.

### 6.1. Launch EC2 Instance

```bash
# Tạo key pair (nếu chưa có)
aws ec2 create-key-pair --key-name habe-key --query "KeyMaterial" --output text > habe-key.pem
chmod 400 habe-key.pem

# Launch instance (Ubuntu 22.04, t3.small)
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.small \
  --key-name habe-key \
  --security-group-ids $SG_ID \
  --associate-public-ip-address \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=habe-backend}]" \
  --query "Instances[0].InstanceId" --output text)

echo "Instance ID: $INSTANCE_ID"

# Đợi instance running
aws ec2 wait instance-running --instance-ids $INSTANCE_ID

# Lấy Public IP
EC2_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query "Reservations[0].Instances[0].PublicIpAddress" --output text)

echo "EC2 IP: $EC2_IP"
```

> **Lưu ý AMI ID:** AMI ID khác nhau theo region. Tìm Ubuntu 22.04 AMI cho region của bạn tại [Ubuntu AMI Locator](https://cloud-images.ubuntu.com/locator/ec2/).

### 6.2. SSH vào EC2 và Setup

```bash
ssh -i habe-key.pem ubuntu@$EC2_IP
```

Trên EC2, chạy:

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone project
git clone <your-repo-url> habe-crypto-backend
cd habe-crypto-backend

# Tạo .env file
cat > .env << EOF
S3_BUCKET_STANDARD=habe-lab-standard
S3_BUCKET_ARCHIVE=habe-lab-archive
AWS_REGION=ap-southeast-1
MAX_FILE_SIZE_MB=100
CORS_ORIGINS=["*"]
EOF

# Build và chạy (không cần LocalStack vì dùng S3 thật)
docker build -t habe-crypto-backend .
docker run -d \
  --name habe-backend \
  -p 8000:8000 \
  --env-file .env \
  habe-crypto-backend
```

### 6.3. Cấu hình IAM cho EC2

Để EC2 truy cập S3, attach IAM Role:

```bash
# Từ máy local (không phải EC2)

# Tạo instance profile
aws iam create-instance-profile --instance-profile-name habe-ec2-profile

# Attach role (dùng role đã tạo bởi Terraform)
aws iam add-role-to-instance-profile \
  --instance-profile-name habe-ec2-profile \
  --role-name habe-lab-backend-role

# Associate với EC2
aws ec2 associate-iam-instance-profile \
  --instance-id $INSTANCE_ID \
  --iam-instance-profile Name=habe-ec2-profile
```

> **Lưu ý:** Sau khi attach role, cần restart container để Boto3 nhận credentials mới.

### 6.4. Mở Security Group cho SSH + HTTP

```bash
# Mở SSH (port 22)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0
```

---

## 7. Kiểm tra và Test

### 7.1. Health Check

```bash
curl http://$PUBLIC_IP:8000/health
```

Expected:
```json
{
  "status": "healthy",
  "s3_connected": true,
  "crypto_module_ready": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 7.2. Test Setup

```bash
curl -X POST http://$PUBLIC_IP:8000/admin/setup
```

### 7.3. Test KeyGen

```bash
# Dùng MPK và MSK từ bước setup
curl -X POST http://$PUBLIC_IP:8000/admin/keygen \
  -H "Content-Type: application/json" \
  -d '{
    "master_public_key": "<MPK_FROM_SETUP>",
    "master_secret_key": "<MSK_FROM_SETUP>",
    "attributes": ["MANAGER", "DEPT_A"]
  }'
```

### 7.4. Test Upload

```bash
curl -X POST http://$PUBLIC_IP:8000/files/upload \
  -F "file=@test_file.txt" \
  -F "access_policy=MANAGER AND DEPT_A" \
  -F "master_public_key=<MPK_FROM_SETUP>" \
  -F "storage_tier=standard"
```

### 7.5. Test Download

```bash
curl -X GET "http://$PUBLIC_IP:8000/files/<FILE_ID>" \
  -H "x-user-secret-key: <USK_FROM_KEYGEN>" \
  -H "x-master-public-key: <MPK_FROM_SETUP>" \
  --output downloaded_file.txt
```

### 7.6. Chạy Demo Script (từ local)

```bash
python demo.py --api --url http://$PUBLIC_IP:8000
```

### 7.7. Kiểm tra S3

```bash
# Xem files đã upload
aws s3 ls s3://habe-lab-standard/standard/ --recursive
aws s3 ls s3://habe-lab-archive/archive/ --recursive
```

---

## 8. Dọn dẹp tài nguyên

> **QUAN TRỌNG:** Chạy các lệnh này sau khi demo xong để tránh phát sinh chi phí.

### 8.1. Xóa ECS (nếu dùng)

```bash
# Xóa service
aws ecs update-service --cluster habe-cluster --service habe-backend-service --desired-count 0
aws ecs delete-service --cluster habe-cluster --service habe-backend-service --force

# Xóa cluster
aws ecs delete-cluster --cluster habe-cluster

# Xóa ECR repository
aws ecr delete-repository --repository-name habe-crypto-backend --force

# Xóa log group
aws logs delete-log-group --log-group-name /ecs/habe-crypto-backend
```

### 8.2. Xóa EC2 (nếu dùng)

```bash
aws ec2 terminate-instances --instance-ids $INSTANCE_ID
aws ec2 delete-key-pair --key-name habe-key
rm -f habe-key.pem
```

### 8.3. Xóa S3 + IAM (Terraform)

```bash
cd deploy

# Xóa tất cả objects trong buckets trước
aws s3 rm s3://habe-lab-standard --recursive
aws s3 rm s3://habe-lab-archive --recursive

# Destroy infrastructure
terraform destroy
```

Nhập `yes` khi được hỏi.

### 8.4. Xóa Security Group

```bash
aws ec2 delete-security-group --group-id $SG_ID
```

### 8.5. Xóa IAM resources (nếu tạo thủ công)

```bash
aws iam remove-role-from-instance-profile --instance-profile-name habe-ec2-profile --role-name habe-lab-backend-role
aws iam delete-instance-profile --instance-profile-name habe-ec2-profile
aws iam detach-role-policy --role-name habe-ecs-task-execution-role --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam detach-role-policy --role-name habe-ecs-task-execution-role --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam delete-role --role-name habe-ecs-task-execution-role
```

---

## 9. Chi phí ước tính

### Cho mục đích Lab/Demo (vài giờ sử dụng)

| Tài nguyên | Chi phí ước tính |
|---|---|
| S3 Standard (< 1GB) | ~$0.02/tháng |
| S3 Archive (< 1GB) | ~$0.01/tháng |
| EC2 t3.small (vài giờ) | ~$0.02/giờ |
| ECS Fargate (0.5 vCPU, 1GB) | ~$0.03/giờ |
| ECR (< 1GB image) | ~$0.10/tháng |
| Data Transfer | ~$0.00 (minimal) |
| **Tổng (demo 2-3 giờ)** | **< $0.50** |

> **Tip:** Dùng AWS Free Tier nếu account mới (12 tháng đầu). EC2 t2.micro miễn phí 750 giờ/tháng.

### Lưu ý tiết kiệm chi phí

- Terminate EC2/ECS ngay sau khi demo xong
- Xóa S3 objects và buckets khi không cần
- Dùng `t2.micro` (Free Tier) thay vì `t3.small` nếu đủ RAM
- Không để resources chạy qua đêm

---

## 10. Troubleshooting

### Docker build thất bại (charm-crypto)

**Vấn đề:** `libpbc-dev` không tìm thấy
```
E: Unable to locate package libpbc-dev
```

**Giải pháp:** Dockerfile đã có fallback build PBC từ source. Nếu vẫn lỗi, thêm PPA:
```dockerfile
RUN add-apt-repository ppa:pbc/pbc && apt-get update && apt-get install -y libpbc-dev
```

### EC2 không kết nối được S3

**Vấn đề:** `botocore.exceptions.NoCredentialsError`

**Giải pháp:**
1. Kiểm tra IAM Role đã attach vào EC2
2. Restart container: `docker restart habe-backend`
3. Kiểm tra: `curl http://169.254.169.254/latest/meta-data/iam/security-credentials/`

### Health check trả về "unhealthy"

**Vấn đề:** `s3_connected: false`

**Giải pháp:**
1. Kiểm tra bucket name trong env vars khớp với Terraform output
2. Kiểm tra region khớp
3. Kiểm tra IAM permissions

### ECS Task không start

**Vấn đề:** Task ở trạng thái STOPPED

**Xem logs:**
```bash
aws ecs describe-tasks --cluster habe-cluster --tasks $TASK_ARN \
  --query "tasks[0].stoppedReason"

# Hoặc xem CloudWatch logs
aws logs get-log-events \
  --log-group-name /ecs/habe-crypto-backend \
  --log-stream-name ecs/habe-backend/<task-id>
```

### Port 8000 không truy cập được

**Kiểm tra:**
1. Security Group có mở port 8000 không
2. EC2/ECS có Public IP không
3. Container đang chạy: `docker ps` (trên EC2)

---

## Tóm tắt Luồng Deploy

```
┌─────────────────────────────────────────────────────────────┐
│  1. terraform apply     → S3 Buckets + IAM Role             │
│  2. docker build        → Container Image (charm-crypto)    │
│  3. docker push (ECR)   → Image trên AWS                    │
│  4. ECS/EC2 run         → Backend API chạy trên cloud       │
│  5. curl /health        → Verify hệ thống hoạt động         │
│  6. python demo.py --api → Demo end-to-end                  │
│  7. terraform destroy   → Dọn dẹp (sau khi xong)           │
└─────────────────────────────────────────────────────────────┘
```
