# Slide Thuyết trình: Mã hóa Phân cấp cho Hệ thống Lưu trữ Đa tầng

---

## Slide 1: Trang bìa

### Mã hóa Phân cấp (Hierarchical Encryption) cho Hệ thống Lưu trữ Đa tầng

**Hierarchical Attribute-Based Encryption (HABE) with Tiered Cloud Storage**

- Môn học: An toàn Thông tin / Cyber Security
- Công nghệ: CP-ABE (BSW07) + AWS S3 + FastAPI
- Ngôn ngữ: Python 3.10+

---

## Slide 2: Bài toán

### Vấn đề cần giải quyết

- **Kiểm soát truy cập chi tiết (Fine-grained Access Control):**
  - Nhiều người dùng với vai trò khác nhau trong tổ chức
  - Cần mã hóa dữ liệu sao cho chỉ người có đủ thuộc tính mới giải mã được

- **Lưu trữ đa tầng (Tiered Storage):**
  - Dữ liệu nóng (truy cập thường xuyên) → Standard Storage
  - Dữ liệu lạnh (lưu trữ dài hạn) → Archive/Glacier Storage
  - Tự động chuyển đổi tầng để tối ưu chi phí

- **Bảo mật nhiều lớp:**
  - Client-side encryption (trước khi upload)
  - Server-side encryption (trên S3)
  - Integrity verification (HMAC)

---

## Slide 3: Giải pháp — CP-ABE (Ciphertext-Policy ABE)

### Mã hóa dựa trên Chính sách Truy cập

**Ý tưởng cốt lõi:**
- Người mã hóa chỉ định **chính sách truy cập** (access policy)
- Người giải mã cần có **tập thuộc tính** thỏa mãn chính sách

**Ví dụ:**
```
Policy: "MANAGER AND DEPT_A"

User 1: [MANAGER, DEPT_A]     → ✓ Giải mã được
User 2: [EMPLOYEE, DEPT_B]    → ✗ Bị từ chối
User 3: [ADMIN, MANAGER, DEPT_A, DEPT_B] → ✓ Giải mã được
```

**Scheme sử dụng:** BSW07 (Bethencourt-Sahai-Waters, 2007)
- Thư viện: Charm-crypto (Python)
- Pairing Group: SS512 (Symmetric bilinear pairing)

---

## Slide 4: Kiến trúc Hệ thống

### 3 Thành phần chính

```
┌──────────┐     ┌─────────────────────┐     ┌──────────────┐
│  Client  │────▶│  Backend API        │────▶│  AWS S3      │
│          │◀────│  (FastAPI)          │◀────│  (Terraform) │
└──────────┘     │                     │     ├──────────────┤
                 │  ┌───────────────┐  │     │ Standard     │
                 │  │ Crypto Module │  │     │ Archive      │
                 │  │ (CP-ABE+AES)  │  │     │ Glacier      │
                 │  └───────────────┘  │     └──────────────┘
                 └─────────────────────┘
```

| Layer | Công nghệ | Vai trò |
|---|---|---|
| Infrastructure | Terraform + AWS S3 | Lưu trữ đa tầng |
| Crypto | Charm-crypto + PyCryptodome | Mã hóa/Giải mã |
| API | FastAPI + Uvicorn | REST proxy |
| Testing | Pytest + Hypothesis | Kiểm chứng |

---

## Slide 5: Hybrid Encryption

### Tại sao cần Hybrid?

- **ABE thuần túy:** Chậm cho dữ liệu lớn (pairing-based crypto)
- **AES thuần túy:** Không hỗ trợ access policy

### Giải pháp: ABE + AES

```
ENCRYPT:
  1. Random GT element (group target)
  2. AES key = SHA-256(GT element)        ← Derive symmetric key
  3. ABE_CT = CP-ABE.encrypt(GT, policy)  ← Protect key with policy
  4. AES_CT = AES-CBC(plaintext, key, IV) ← Fast bulk encryption
  5. HMAC = HMAC-SHA256(key, AES_CT)      ← Integrity protection
  6. Bundle = MessagePack(ABE_CT + AES_CT + IV + HMAC + metadata)

DECRYPT:
  1. Unpack bundle
  2. GT = CP-ABE.decrypt(ABE_CT, user_key) ← Recover GT (or fail)
  3. AES key = SHA-256(GT)
  4. Verify HMAC                           ← Check integrity
  5. plaintext = AES-CBC.decrypt(AES_CT)   ← Recover data
```

---

## Slide 6: Thuộc tính Phân cấp

### Cấu trúc Tổ chức → Thuộc tính

```
COMPANY
├── DEPT_A
│   ├── MANAGER
│   └── EMPLOYEE
├── DEPT_B
│   ├── MANAGER
│   └── EMPLOYEE
└── ADMIN (cross-department)
```

### Ví dụ Chính sách

| Policy | Ý nghĩa | Ai truy cập được? |
|---|---|---|
| `MANAGER AND DEPT_A` | Manager của Dept A | Chỉ Manager Dept A |
| `MANAGER OR ADMIN` | Manager hoặc Admin | Mọi Manager + Admin |
| `(MANAGER AND DEPT_A) OR ADMIN` | Manager Dept A hoặc Admin | Manager Dept A + Admin |
| `COMPANY` | Toàn công ty | Tất cả nhân viên |

---

## Slide 7: Lưu trữ Đa tầng (Terraform)

### S3 Tiered Storage Module

| Tầng | Storage Class | Chi phí | Use Case |
|---|---|---|---|
| Standard | S3 Standard | Cao | Dữ liệu truy cập thường xuyên |
| Archive | S3 Standard-IA | Trung bình | Dữ liệu ít truy cập |
| Glacier | S3 Glacier | Thấp | Lưu trữ dài hạn (auto-transition) |

### Bảo mật Infrastructure

- ✅ Server-Side Encryption (AES-256 / KMS)
- ✅ Versioning enabled
- ✅ Block Public Access (tất cả 4 options)
- ✅ IAM Least Privilege (chỉ PutObject + GetObject)
- ✅ Lifecycle Rule: Standard → Glacier sau 30 ngày

---

## Slide 8: API Endpoints

### REST API Design

| Method | Endpoint | Chức năng |
|---|---|---|
| `POST` | `/admin/setup` | Tạo MPK + MSK |
| `POST` | `/admin/keygen` | Phát hành USK cho user |
| `POST` | `/files/upload` | Encrypt + Upload to S3 |
| `GET` | `/files/{id}` | Download from S3 + Decrypt |
| `GET` | `/health` | Health check |

### Error Handling

| HTTP Code | Ý nghĩa |
|---|---|
| 400 | Invalid policy / attributes / ciphertext |
| 401 | Missing authentication headers |
| 403 | Access Denied (attributes ⊄ policy) |
| 404 | File not found |
| 413 | File too large |
| 503 | S3 unavailable |

---

## Slide 9: Testing & Correctness Properties

### Property-Based Testing (Hypothesis)

| # | Property | Mô tả |
|---|---|---|
| P1 | Round-Trip | `decrypt(encrypt(P)) == P` ∀ plaintext |
| P2 | Access Denial | attrs ⊄ policy → AccessDeniedError |
| P3 | Distinct Keys | Mỗi setup() tạo khóa khác nhau |
| P4 | Input Rejection | Invalid input → proper error |
| P5 | Corruption Detection | Modified CT → detected |
| P6 | Error Format | All errors match schema |

### Test Coverage

| Loại | Số lượng | Framework |
|---|---|---|
| Unit Tests (Crypto) | 34 | pytest |
| Unit Tests (Storage) | 11 | pytest + moto |
| Property Tests | 7 | Hypothesis (100 examples/test) |
| API Integration | 32 | httpx + moto |
| **Tổng** | **84+** | |

---

## Slide 10: Demo

### Luồng Demo

```
1. SETUP     → Tạo MPK, MSK
2. KEYGEN    → Tạo khóa cho Manager (MANAGER, DEPT_A)
               Tạo khóa cho Employee (EMPLOYEE, DEPT_B)
3. ENCRYPT   → Mã hóa file với policy "MANAGER AND DEPT_A"
4. UPLOAD    → Lưu ciphertext lên S3 Standard
5. DOWNLOAD  → Manager tải + giải mã → ✓ Thành công
6. DENIED    → Employee tải + giải mã → ✗ 403 Forbidden
7. INTEGRITY → Sửa ciphertext → Phát hiện corruption
```

### Chạy Demo

```bash
# Docker (đầy đủ)
docker-compose up -d
docker-compose exec app python demo.py

# Standalone (chỉ crypto, không cần S3)
python demo.py
```

---

## Slide 11: Kết quả & Đánh giá

### Đã đạt được

| Tiêu chí | Kết quả |
|---|---|
| Mã hóa phân cấp (CP-ABE) | ✅ BSW07 scheme, AND/OR policies |
| Hybrid encryption | ✅ ABE + AES-256-CBC + HMAC-SHA256 |
| Lưu trữ đa tầng | ✅ Standard + Archive + Glacier lifecycle |
| API RESTful | ✅ FastAPI với OpenAPI docs |
| Bảo mật nhiều lớp | ✅ Client-side + Server-side + IAM |
| Testing | ✅ 84+ tests, property-based testing |
| Infrastructure as Code | ✅ Terraform module |

### Hạn chế & Hướng phát triển

- Charm-crypto cần compile từ source (phức tạp trên Windows)
- Key management chưa persistent (client tự quản lý)
- Chưa có key revocation mechanism
- Có thể mở rộng: Multi-Authority ABE, Proxy Re-Encryption

---

## Slide 12: Công nghệ sử dụng

| Thành phần | Công nghệ | Version |
|---|---|---|
| Crypto Scheme | CP-ABE BSW07 | — |
| Crypto Library | Charm-crypto | 0.50 |
| Symmetric Cipher | AES-256-CBC (PyCryptodome) | 3.19 |
| Backend Framework | FastAPI | 0.104 |
| ASGI Server | Uvicorn | 0.24 |
| AWS SDK | Boto3 | 1.29 |
| Infrastructure | Terraform (AWS Provider) | ≥ 4.0 |
| Testing | Pytest + Hypothesis + Moto | — |
| Serialization | MessagePack + JSON + Base64 | — |
| Language | Python | 3.10+ |

---

## Slide 13: Q&A

### Câu hỏi thường gặp

**Q: Tại sao chọn CP-ABE thay vì KP-ABE?**
A: CP-ABE cho phép người mã hóa quyết định chính sách truy cập, phù hợp với mô hình "data owner controls access".

**Q: Tại sao cần HMAC nếu đã có ABE?**
A: ABE chỉ bảo vệ confidentiality. HMAC bảo vệ integrity — phát hiện nếu ciphertext bị sửa đổi.

**Q: Performance như thế nào?**
A: ABE operations ~100-500ms (pairing-based). AES encryption rất nhanh. Hybrid approach đảm bảo file lớn vẫn nhanh.

**Q: Có thể revoke quyền truy cập không?**
A: Trong thiết kế hiện tại, cần re-encrypt file với policy mới. Có thể mở rộng với Proxy Re-Encryption.

---

*Cảm ơn đã lắng nghe!*
