# Kiến trúc Hệ thống — HABE Crypto Backend

## 1. System Context Diagram

```mermaid
graph TB
    Client[Client Application] -->|HTTP REST| API[Backend API<br/>FastAPI + Uvicorn]
    API -->|Encrypt/Decrypt| Crypto[Crypto Module<br/>Charm-crypto CP-ABE]
    API -->|Upload/Download| S3[AWS S3<br/>Tiered Storage]
    Admin[System Admin] -->|Setup/KeyGen| API
    
    subgraph "Existing Infrastructure (Terraform)"
        S3
        S3Standard[Standard Bucket<br/>Truy cập thường xuyên]
        S3Archive[Archive Bucket<br/>Lưu trữ dài hạn]
        S3 --> S3Standard
        S3 --> S3Archive
        S3Standard -->|Lifecycle 30 ngày| Glacier[Glacier Storage]
    end
```

## 2. Component Architecture

```mermaid
graph LR
    subgraph "Backend API (FastAPI)"
        Router[API Router]
        Upload[POST /files/upload]
        Download["GET /files/:id"]
        AdminSetup[POST /admin/setup]
        AdminKeygen[POST /admin/keygen]
        Health[GET /health]
        Router --> Upload
        Router --> Download
        Router --> AdminSetup
        Router --> AdminKeygen
        Router --> Health
    end

    subgraph "Crypto Module (charm-crypto)"
        Setup[setup&#40;&#41; → MPK, MSK]
        KeyGen[keygen&#40;MPK, MSK, attrs&#41; → USK]
        Encrypt[encrypt&#40;MPK, data, policy&#41; → CT]
        Decrypt[decrypt&#40;MPK, USK, CT&#41; → data]
    end

    subgraph "Storage Layer (Boto3)"
        S3Client[S3 Client]
        StdBucket[Standard Bucket]
        ArcBucket[Archive Bucket]
        S3Client --> StdBucket
        S3Client --> ArcBucket
    end

    Upload --> Encrypt
    Download --> Decrypt
    AdminSetup --> Setup
    AdminKeygen --> KeyGen
    Upload --> S3Client
    Download --> S3Client
    Health --> S3Client
```

## 3. Hybrid Encryption Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Backend API
    participant Crypto as Crypto Module
    participant S3 as AWS S3

    Note over C,S3: ═══ UPLOAD FLOW (Encrypt + Store) ═══
    C->>API: POST /files/upload<br/>(file + access_policy + MPK)
    API->>API: Validate file size
    API->>Crypto: encrypt(MPK, plaintext, policy)
    Note over Crypto: 1. Random GT element<br/>2. AES key = SHA256(GT)<br/>3. ABE encrypt(GT, policy)<br/>4. AES-CBC encrypt(data)<br/>5. HMAC-SHA256(AES_ct)
    Crypto-->>API: ciphertext bundle (MessagePack)
    API->>S3: PutObject(tier/file_id.enc)
    S3-->>API: success
    API-->>C: 200 OK + UploadResponse

    Note over C,S3: ═══ DOWNLOAD FLOW (Fetch + Decrypt) ═══
    C->>API: GET /files/{id}<br/>(headers: USK + MPK)
    API->>API: Validate auth headers
    API->>S3: GetObject(tier/file_id.enc)
    S3-->>API: ciphertext bundle
    API->>Crypto: decrypt(MPK, USK, ciphertext)
    Note over Crypto: 1. Unpack MessagePack<br/>2. ABE decrypt → GT<br/>3. AES key = SHA256(GT)<br/>4. Verify HMAC<br/>5. AES-CBC decrypt
    Crypto-->>API: plaintext
    API-->>C: 200 OK + file stream

    Note over C,S3: ═══ ACCESS DENIED ═══
    C->>API: GET /files/{id}<br/>(USK with wrong attributes)
    API->>S3: GetObject(...)
    S3-->>API: ciphertext
    API->>Crypto: decrypt(MPK, USK_wrong, ciphertext)
    Note over Crypto: ABE decrypt fails<br/>(attrs ⊄ policy)
    Crypto-->>API: AccessDeniedError
    API-->>C: 403 Forbidden
```

## 4. Cấu trúc Ciphertext Bundle

```mermaid
graph TD
    subgraph "Ciphertext Bundle (MessagePack)"
        V[version: 1]
        S[scheme: CP-ABE-BSW07-HYBRID]
        P[access_policy: "Manager AND Dept_A"]
        ABE[abe_ciphertext: base64<br/>ABE encrypted GT element]
        AES[aes_ciphertext: base64<br/>AES-256-CBC encrypted data]
        IV[aes_iv: base64<br/>16-byte random IV]
        HMAC[hmac: base64<br/>HMAC-SHA256 of aes_ciphertext]
        META[metadata: dict<br/>original_size, filename, ...]
    end
```

## 5. Exception Hierarchy

```mermaid
graph TD
    Base[CryptoError<br/>500 Internal] --> Setup[CryptoSetupError<br/>500]
    Base --> KeyGen[CryptoKeyGenError<br/>500]
    Base --> Enc[CryptoEncryptError<br/>500]
    Base --> Dec[CryptoDecryptError<br/>500]
    
    KeyGen --> InvalidAttr[InvalidAttributeSetError<br/>400 Bad Request]
    Enc --> InvalidPolicy[InvalidPolicyError<br/>400 Bad Request]
    Dec --> AccessDenied[AccessDeniedError<br/>403 Forbidden]
    Dec --> InvalidCT[InvalidCiphertextError<br/>400 Bad Request]

    style AccessDenied fill:#ff6b6b
    style InvalidAttr fill:#ffd93d
    style InvalidPolicy fill:#ffd93d
    style InvalidCT fill:#ffd93d
```

## 6. Tiered Storage Architecture (Terraform)

```mermaid
graph TB
    subgraph "AWS S3 Tiered Storage Module"
        subgraph "Standard Bucket"
            STD[S3 Standard<br/>Truy cập thường xuyên]
            STD_ENC[SSE: AES-256 / KMS]
            STD_VER[Versioning: Enabled]
            STD_PUB[Public Access: Blocked]
            STD_LC[Lifecycle: → Glacier 30d]
        end
        
        subgraph "Archive Bucket"
            ARC[S3 Archive<br/>Lưu trữ dài hạn]
            ARC_ENC[SSE: AES-256 / KMS]
            ARC_VER[Versioning: Enabled]
            ARC_PUB[Public Access: Blocked]
        end
        
        subgraph "IAM"
            ROLE[Backend IAM Role]
            POLICY[Policy: s3:PutObject<br/>+ s3:GetObject only]
            ROLE --> POLICY
        end
    end

    POLICY -->|Least Privilege| STD
    POLICY -->|Least Privilege| ARC
```

## 7. Thuộc tính Phân cấp (Hierarchical Attributes)

```mermaid
graph TD
    subgraph "Cấu trúc Phân cấp Tổ chức"
        COMPANY[COMPANY]
        COMPANY --> DEPT_A[DEPT_A]
        COMPANY --> DEPT_B[DEPT_B]
        DEPT_A --> MGR_A[MANAGER]
        DEPT_A --> EMP_A[EMPLOYEE]
        DEPT_B --> MGR_B[MANAGER]
        DEPT_B --> EMP_B[EMPLOYEE]
    end

    subgraph "Ví dụ Chính sách Truy cập"
        P1["MANAGER AND DEPT_A"<br/>→ Chỉ Manager Dept A]
        P2["MANAGER OR ADMIN"<br/>→ Manager bất kỳ hoặc Admin]
        P3["(MANAGER AND DEPT_A) OR ADMIN"<br/>→ Manager Dept A hoặc Admin]
    end
```

## 8. Security Layers

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT SIDE                            │
│  • Access Policy enforcement (CP-ABE)                    │
│  • Attribute-based key management                        │
├─────────────────────────────────────────────────────────┤
│                    TRANSPORT                              │
│  • HTTPS/TLS encryption                                  │
│  • Base64 key encoding for HTTP headers                  │
├─────────────────────────────────────────────────────────┤
│                    APPLICATION (Backend API)              │
│  • Input validation (Pydantic)                           │
│  • File size limits                                      │
│  • CORS configuration                                    │
│  • Error sanitization (no sensitive data in responses)   │
│  • In-memory processing (no plaintext on disk)           │
├─────────────────────────────────────────────────────────┤
│                    ENCRYPTION (Crypto Module)             │
│  • CP-ABE BSW07 (attribute-based access control)         │
│  • AES-256-CBC (bulk data encryption)                    │
│  • HMAC-SHA256 (integrity verification)                  │
│  • Secure random (os.urandom for keys/IVs)              │
├─────────────────────────────────────────────────────────┤
│                    STORAGE (AWS S3)                       │
│  • Server-Side Encryption (SSE-S3 / SSE-KMS)            │
│  • Bucket versioning                                     │
│  • Block public access                                   │
│  • IAM least privilege (PutObject + GetObject only)      │
│  • Lifecycle rules (Standard → Glacier)                  │
└─────────────────────────────────────────────────────────┘
```
