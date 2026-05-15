# Implementation Plan: HABE Crypto Backend

## Overview

Implement a Hierarchical Attribute-Based Encryption (HABE) system with a core crypto module (Charm-crypto CP-ABE) and a FastAPI backend API that acts as an encryption proxy between clients and AWS S3. The implementation follows a bottom-up approach: crypto module first, then backend services, then API layer, then testing.

## Tasks

- [x] 1. Set up project structure and dependencies
  - [x] 1.1 Create `pyproject.toml` with project metadata and dependencies (charm-crypto, fastapi, uvicorn, boto3, pydantic, python-multipart, msgpack, httpx, pytest, pytest-asyncio, hypothesis, moto)
    - _Requirements: 8.1, 8.2, 8.3_
  - [x] 1.2 Create `requirements.txt` with pinned versions for all dependencies
    - _Requirements: 8.1, 8.2, 8.3_
  - [x] 1.3 Create directory structure with `__init__.py` files for `crypto_module/`, `backend/`, `backend/routers/`, `backend/services/`, `backend/models/`, and `tests/`
    - _Requirements: 8.1_

- [x] 2. Implement crypto module exceptions
  - [x] 2.1 Create `crypto_module/exceptions.py` with the full exception hierarchy
    - Define `CryptoError` base exception
    - Define `CryptoSetupError`, `CryptoKeyGenError`, `CryptoEncryptError`, `CryptoDecryptError`
    - Define `InvalidAttributeSetError` (extends `CryptoKeyGenError`), `InvalidPolicyError` (extends `CryptoEncryptError`), `AccessDeniedError` (extends `CryptoDecryptError`), `InvalidCiphertextError` (extends `CryptoDecryptError`)
    - _Requirements: 2.4, 3.4, 4.3, 4.5, 10.4_

- [x] 3. Implement crypto module serialization utilities
  - [x] 3.1 Create `crypto_module/serialization.py` with key and ciphertext serialization functions
    - Implement `serialize_key(key_object, group) -> bytes` using Charm's `objectToBytes` + base64 + JSON envelope
    - Implement `deserialize_key(key_bytes, group) -> object` for reverse operation
    - Implement `serialize_ciphertext_bundle(abe_ct, aes_ct, iv, hmac, policy, metadata) -> bytes` using MessagePack
    - Implement `deserialize_ciphertext_bundle(bundle_bytes) -> dict` for reverse operation
    - _Requirements: 1.1, 1.2, 3.2, 4.1_

- [x] 4. Implement HABECrypto core class
  - [x] 4.1 Create `crypto_module/core.py` with `HABECrypto` class
    - Implement `__init__(self, group_name="SS512")` initializing PairingGroup and CPabe_BSW07
    - Implement `setup() -> Tuple[bytes, bytes]` generating MPK and MSK via `cpabe.setup()`, serializing both keys
    - Implement `keygen(mpk_bytes, msk_bytes, attributes) -> bytes` deserializing keys, calling `cpabe.keygen()`, serializing USK
    - Validate attributes list is non-empty and contains valid strings; raise `InvalidAttributeSetError` otherwise
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 4.2 Implement `encrypt(mpk_bytes, plaintext, access_policy) -> bytes` in `HABECrypto`
    - Deserialize MPK, validate access policy syntax
    - Use Charm's `HybridABEnc` (or manual hybrid): ABE-encrypt a random symmetric key under the policy, AES-CBC encrypt plaintext with derived key
    - Compute HMAC-SHA256 over AES ciphertext for integrity
    - Bundle into MessagePack format via serialization module
    - Raise `InvalidPolicyError` for bad policy syntax, `CryptoEncryptError` for other failures
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  - [x] 4.3 Implement `decrypt(mpk_bytes, usk_bytes, ciphertext_bytes) -> bytes` in `HABECrypto`
    - Deserialize ciphertext bundle, MPK, and USK
    - Verify HMAC integrity; raise `InvalidCiphertextError` if corrupted
    - ABE-decrypt to recover symmetric key; raise `AccessDeniedError` if attributes don't satisfy policy
    - AES-CBC decrypt file data with recovered key
    - Return original plaintext bytes
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  - [x] 4.4 Create `crypto_module/__init__.py` exporting `HABECrypto` and all exception classes
    - _Requirements: 1.1, 2.1, 3.1, 4.1_

- [x] 5. Checkpoint - Verify crypto module
  - Ensure all crypto module code is syntactically correct and imports resolve, ask the user if questions arise.

- [x] 6. Implement backend configuration and models
  - [x] 6.1 Create `backend/config.py` with settings class
    - Use Pydantic `BaseSettings` with env var support
    - Define: `S3_BUCKET_STANDARD`, `S3_BUCKET_ARCHIVE`, `AWS_REGION`, `MAX_FILE_SIZE_MB`, `CORS_ORIGINS`
    - _Requirements: 8.3, 8.4, 6.4, 10.5_
  - [x] 6.2 Create `backend/models/requests.py` with Pydantic request models
    - Define `KeyGenRequest` with `master_public_key`, `master_secret_key`, `attributes` (min_length=1 validation)
    - _Requirements: 2.1, 10.1_
  - [x] 6.3 Create `backend/models/responses.py` with Pydantic response models
    - Define `SetupResponse`, `KeyGenResponse`, `UploadResponse`, `ErrorResponse`, `HealthResponse`
    - _Requirements: 6.5, 7.4, 8.5, 10.4_

- [x] 7. Implement backend services
  - [x] 7.1 Create `backend/services/storage_service.py` with S3 interaction logic
    - Implement `StorageService` class with Boto3 client
    - Implement `upload_file(file_id, data, tier, metadata) -> dict` using `put_object`
    - Implement `download_file(file_id, tier) -> bytes` using `get_object`
    - Implement `check_connectivity() -> bool` using `head_bucket`
    - Handle Boto3 exceptions: `NoSuchKey` → raise custom not found, connection errors → raise service unavailable
    - _Requirements: 6.3, 6.4, 6.7, 7.2, 7.6, 7.7, 8.6_
  - [x] 7.2 Create `backend/services/crypto_service.py` wrapping crypto_module for API use
    - Implement `CryptoService` class holding an `HABECrypto` instance
    - Implement `perform_setup() -> Tuple[str, str]` returning base64-encoded keys
    - Implement `generate_key(mpk, msk, attributes) -> str` returning base64-encoded USK
    - Implement `encrypt_file(mpk, plaintext, policy) -> bytes` returning ciphertext bundle
    - Implement `decrypt_file(mpk, usk, ciphertext) -> bytes` returning plaintext
    - Map crypto exceptions to appropriate error responses
    - _Requirements: 6.2, 7.3, 9.3, 9.4_

- [x] 8. Implement backend API routers
  - [x] 8.1 Create `backend/routers/health.py` with health check endpoint
    - Implement `GET /health` checking S3 connectivity and crypto module readiness
    - Return `HealthResponse` with status "healthy", "degraded", or "unhealthy"
    - _Requirements: 8.5, 8.6_
  - [x] 8.2 Create `backend/routers/admin.py` with setup and keygen endpoints
    - Implement `POST /admin/setup` calling crypto_service.perform_setup()
    - Implement `POST /admin/keygen` accepting `KeyGenRequest`, calling crypto_service.generate_key()
    - Validate input; return appropriate error responses for invalid attributes
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 10.1, 10.2_
  - [x] 8.3 Create `backend/routers/files.py` with upload and download endpoints
    - Implement `POST /files/upload` accepting multipart form (file, access_policy, master_public_key, storage_tier)
    - Validate file size against MAX_FILE_SIZE_MB; return 413 if exceeded
    - Call crypto_service.encrypt_file(), then storage_service.upload_file()
    - Return `UploadResponse` with file metadata
    - Implement `GET /files/{file_id}` accepting USK and MPK via headers
    - Call storage_service.download_file(), then crypto_service.decrypt_file()
    - Return file content as StreamingResponse
    - Handle missing auth → 401, access denied → 403, not found → 404
    - _Requirements: 6.1, 6.2, 6.3, 6.5, 6.6, 6.7, 6.8, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 10.1, 10.2, 10.3, 10.5_

- [x] 9. Implement FastAPI app initialization and error handling
  - [x] 9.1 Create `backend/exceptions.py` with global exception handlers
    - Map `InvalidAttributeSetError` → 400, `InvalidPolicyError` → 400, `AccessDeniedError` → 403, `InvalidCiphertextError` → 400
    - Map other `CryptoError` → 500, S3 connection errors → 503, `NoSuchKey` → 404
    - All error responses use `ErrorResponse` schema with error_code, message, timestamp
    - Ensure sensitive data (keys, plaintext) is never included in error responses
    - _Requirements: 9.2, 9.4, 10.4_
  - [x] 9.2 Create `backend/main.py` with FastAPI app setup
    - Initialize FastAPI app with title, description, version
    - Configure CORS middleware using settings from config.py
    - Register all routers (admin, files, health)
    - Register global exception handlers
    - Implement lifespan context manager for startup/shutdown
    - _Requirements: 8.1, 8.4, 9.1_

- [x] 10. Checkpoint - Verify backend structure
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Write unit tests for crypto module
  - [x] 11.1 Create `tests/conftest.py` with shared test fixtures
    - Fixture for initialized `HABECrypto` instance
    - Fixture for MPK/MSK pair from setup()
    - Fixture for sample attribute sets and policies
    - _Requirements: 5.1, 5.2_
  - [x] 11.2 Create `tests/test_crypto_core.py` with unit tests
    - Test setup() returns two non-empty byte sequences
    - Test keygen() with known attributes produces a non-empty key
    - Test encrypt() with known policy produces ciphertext
    - Test decrypt() with matching key returns original data
    - Test hierarchical attributes (e.g., ["Company", "Dept_A", "Manager"])
    - Test edge cases: empty file, single attribute, many attributes
    - Test error cases: empty attributes → InvalidAttributeSetError, invalid policy → InvalidPolicyError
    - _Requirements: 1.1, 1.5, 2.1, 2.4, 3.1, 3.4, 4.1, 4.3, 4.5_

- [x] 12. Write property-based tests for crypto module
  - [x] 12.1 Create `tests/test_crypto_roundtrip.py` with Hypothesis property tests
    - **Property 1: Encryption Round-Trip**
    - Generate random plaintext (0-10KB), valid policies with AND/OR, satisfying attribute sets
    - Assert decrypt(encrypt(plaintext)) == plaintext
    - **Validates: Requirements 4.4, 5.1, 5.2, 5.4, 3.2, 3.3, 3.6**
  - [x] 12.2 Add property test for access denial
    - **Property 2: Access Denial for Non-Satisfying Attributes**
    - Generate valid policies and non-satisfying attribute sets
    - Assert decrypt raises AccessDeniedError
    - **Validates: Requirements 2.5, 3.5, 4.3, 5.3**
  - [x] 12.3 Add property test for distinct key pairs
    - **Property 3: Setup Produces Distinct Key Pairs**
    - Call setup() multiple times, assert all MPK/MSK pairs are distinct
    - **Validates: Requirements 1.5**
  - [x] 12.4 Add property test for invalid input rejection
    - **Property 4: Invalid Inputs Are Rejected**
    - Generate empty/invalid attribute sets → assert InvalidAttributeSetError
    - Generate invalid policy strings → assert InvalidPolicyError
    - **Validates: Requirements 2.4, 3.4**
  - [x] 12.5 Add property test for corrupted ciphertext detection
    - **Property 5: Corrupted Ciphertext Detection**
    - Generate valid ciphertext, corrupt random bytes, assert InvalidCiphertextError on decrypt
    - **Validates: Requirements 4.5**

- [x] 13. Write API integration tests
  - [x] 13.1 Create `tests/test_api_upload.py` with upload endpoint tests using moto for S3 mocking
    - Test successful upload returns UploadResponse with correct metadata
    - Test missing file → 400
    - Test missing access_policy → 400
    - Test invalid policy syntax → 400
    - Test file too large → 413
    - Test S3 failure → 500
    - **Property 6: Error Response Format Consistency** - verify all error responses match ErrorResponse schema
    - **Validates: Requirements 6.1, 6.2, 6.5, 6.6, 6.7, 10.1, 10.2, 10.4, 10.5**
  - [x] 13.2 Create `tests/test_api_download.py` with download endpoint tests using moto for S3 mocking
    - Test successful download returns original file content (end-to-end: upload then download)
    - Test non-matching key → 403
    - Test file not found → 404
    - Test missing auth header → 401
    - Test S3 failure → 500
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 10.3**
  - [x] 13.3 Add health check tests
    - Test S3 reachable → 200 with status "healthy"
    - Test S3 unreachable → 503 with status "unhealthy"
    - **Validates: Requirements 8.5, 8.6**

- [x] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The crypto module uses Charm-crypto's `CPabe_BSW07` scheme with `HybridABEnc` for hybrid encryption
- S3 interaction uses Boto3 with the existing `s3-tiered-storage` Terraform module infrastructure
- All tests use `moto` for S3 mocking and `httpx` with FastAPI's `TestClient` for API testing
