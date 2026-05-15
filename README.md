# HABE Crypto Backend — Mã hóa Phân cấp cho Hệ thống Lưu trữ Đa tầng

## Giới thiệu

Hệ thống triển khai **Hierarchical Attribute-Based Encryption (HABE)** kết hợp **CP-ABE (Ciphertext-Policy ABE)** với hạ tầng lưu trữ đa tầng AWS S3. Dữ liệu được mã hóa phía client theo chính sách truy cập dựa trên thuộc tính phân cấp trước khi lưu trữ trên S3.

### Kiến trúc tổng quan

```
┌─────────────┐       ┌──────────────────────┐       ┌─────────────────┐
│   Client    │──────▶│  Backend API (FastAPI)│──────▶│  AWS S3 Tiered  │
│ Application │◀──────│  + Crypto Module      │◀──────│  Storage        │
└─────────────┘       └──────────────────────┘       └─────────────────┘
                              │                         ├── Standard Bucket
                              │                         └── Archive Bucket
                      ┌───────┴───────┐
                      │ CP-ABE BSW07  │
                      │ + AES-256-CBC │
                      │ + HMAC-SHA256 │
                      └───────────────┘
```

### Thành phần chính

| Thành phần | Công nghệ | Chức năng |
|---|---|---|
| Crypto Module | Charm-crypto (CP-ABE BSW07) | Setup, KeyGen, Encrypt, Decrypt |
| Backend API | FastAPI + Uvicorn | REST API proxy (encrypt → store, fetch → decrypt) |
| Storage | AWS S3 (Terraform) | Lưu trữ đa tầng (Standard + Archive) |
| Testing | Pytest + Hypothesis | Unit, Integration, Property-Based Testing |

---

## Yêu cầu Hệ thống

- **Python** 3.10+
- **Docker** & Docker Compose (khuyến nghị)
- **Charm-crypto** dependencies: PBC library, GMP library
- **AWS CLI** (nếu deploy thực tế) hoặc **LocalStack** (cho development)

---

## Cài đặt

### Cách 1: Docker (Khuyến nghị)

```bash
# Clone repository
git clone <repo-url>
cd habe-crypto-backend

# Khởi động toàn bộ hệ thống (API + LocalStack S3)
docker-compose up -d

# Chạy demo
docker-compose exec app python demo.py

# Chạy tests
docker-compose exec app pytest -v
```

### Cách 2: Cài đặt thủ công (Linux/macOS)

#### Bước 1: Cài đặt system dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    python3-dev \
    libgmp-dev \
    libpbc-dev \
    libssl-dev \
    flex \
    bison

# macOS (Homebrew)
brew install gmp pbc openssl
```

#### Bước 2: Cài đặt Poetry và dependencies

```bash
# Cài Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Cài dependencies
poetry install

# Activate virtual environment
poetry shell
```

#### Bước 3: Cài đặt Charm-crypto

```bash
# Clone và build charm-crypto
git clone https://github.com/JHUISI/charm.git
cd charm
./configure.sh
make
sudo make install

# Verify
python -c "from charm.toolbox.pairinggroup import PairingGroup; print('OK')"
```

#### Bước 4: Cấu hình môi trường

```bash
# Tạo file .env
cat > .env << EOF
S3_BUCKET_STANDARD=habe-standard-storage
S3_BUCKET_ARCHIVE=habe-archive-storage
AWS_REGION=us-east-1
MAX_FILE_SIZE_MB=100
CORS_ORIGINS=["*"]
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_ENDPOINT_URL=http://localhost:4566
EOF
```

---

## Chạy ứng dụng

### Khởi động API server

```bash
# Development mode
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Documentation

Sau khi khởi động, truy cập:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Demo End-to-End

```bash
# Chạy script demo (cần API server đang chạy)
python demo.py

# Hoặc chạy demo standalone (không cần server)
python demo.py --standalone
```

Demo minh họa luồng hoàn chỉnh:
1. **Setup** — Tạo Master Public Key (MPK) và Master Secret Key (MSK)
2. **KeyGen** — Phát hành khóa cho người dùng dựa trên thuộc tính phân cấp
3. **Encrypt + Upload** — Mã hóa file theo chính sách truy cập, upload lên S3
4. **Download + Decrypt** — Tải file từ S3, giải mã với khóa người dùng
5. **Access Denied** — Minh họa từ chối truy cập khi thuộc tính không thỏa mãn

---

## Chạy Tests

```bash
# Tất cả tests
pytest -v

# Chỉ unit tests (không cần charm-crypto)
pytest tests/test_serialization.py tests/test_storage_service.py -v

# Property-based tests (cần charm-crypto)
pytest tests/test_crypto_roundtrip.py -v

# API integration tests
pytest tests/test_api_upload.py tests/test_api_download.py tests/test_health.py -v

# Với coverage report
pytest --cov=crypto_module --cov=backend --cov-report=html
```

---

## Cấu trúc Dự án

```
habe-crypto-backend/
├── crypto_module/              # Module mã hóa CP-ABE
│   ├── __init__.py
│   ├── core.py                 # HABECrypto class (Setup, KeyGen, Encrypt, Decrypt)
│   ├── serialization.py        # Key/ciphertext serialization
│   └── exceptions.py           # Exception hierarchy
├── backend/                    # FastAPI Backend API
│   ├── __init__.py
│   ├── main.py                 # App initialization, CORS, routers
│   ├── config.py               # Settings (env vars)
│   ├── exceptions.py           # Global exception handlers
│   ├── routers/
│   │   ├── admin.py            # POST /admin/setup, /admin/keygen
│   │   ├── files.py            # POST /files/upload, GET /files/{id}
│   │   └── health.py           # GET /health
│   ├── services/
│   │   ├── crypto_service.py   # Wraps crypto_module for API
│   │   └── storage_service.py  # S3 interaction (Boto3)
│   └── models/
│       ├── requests.py         # Pydantic request models
│       └── responses.py        # Pydantic response models
├── modules/                    # Terraform Infrastructure
│   └── s3-tiered-storage/
│       ├── main.tf             # S3 buckets, IAM role/policy
│       ├── variables.tf        # Input variables
│       ├── outputs.tf          # Output values
│       └── versions.tf         # Provider requirements
├── tests/                      # Test Suite
│   ├── conftest.py             # Shared fixtures
│   ├── test_crypto_core.py     # Unit tests (crypto)
│   ├── test_crypto_roundtrip.py # Property-based tests (Hypothesis)
│   ├── test_serialization.py   # Unit tests (serialization)
│   ├── test_storage_service.py # Unit tests (S3 service)
│   ├── test_api_upload.py      # Integration tests (upload)
│   ├── test_api_download.py    # Integration tests (download)
│   └── test_health.py          # Integration tests (health)
├── demo.py                     # End-to-end demo script
├── docker-compose.yml          # Docker setup (app + LocalStack)
├── Dockerfile                  # Container image
├── pyproject.toml              # Poetry dependencies
├── requirements.txt            # Pinned dependencies
└── README.md                   # Tài liệu này
```

---

## Triển khai Hạ tầng (Terraform)

```bash
cd modules/s3-tiered-storage

# Khởi tạo
terraform init

# Xem plan
terraform plan \
  -var="bucket_name_prefix=habe" \
  -var="aws_region=us-east-1" \
  -var="trusted_principal=arn:aws:iam::123456789012:root"

# Apply
terraform apply \
  -var="bucket_name_prefix=habe" \
  -var="aws_region=us-east-1" \
  -var="trusted_principal=arn:aws:iam::123456789012:root"
```

---

## Tài liệu Tham khảo

- [Charm-crypto Documentation](https://jhuisi.github.io/charm/)
- [BSW07 CP-ABE Paper](https://eprint.iacr.org/2007/131)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AWS S3 Storage Classes](https://aws.amazon.com/s3/storage-classes/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest)

---

## License

MIT
