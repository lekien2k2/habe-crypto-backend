#!/usr/bin/env python3
"""
Demo End-to-End: Mã hóa Phân cấp (HABE) cho Hệ thống Lưu trữ Đa tầng

Minh họa luồng hoàn chỉnh:
  1. Setup    — Tạo Master Public Key (MPK) và Master Secret Key (MSK)
  2. KeyGen   — Phát hành khóa cho người dùng dựa trên thuộc tính phân cấp
  3. Encrypt  — Mã hóa file theo chính sách truy cập
  4. Upload   — Lưu ciphertext lên S3 (tiered storage)
  5. Download — Tải ciphertext từ S3
  6. Decrypt  — Giải mã với khóa người dùng (thành công + thất bại)

Chạy:
  python demo.py              # Standalone mode (không cần server)
  python demo.py --api        # API mode (cần server đang chạy tại localhost:8000)
"""

import argparse
import sys
import time

# ═══════════════════════════════════════════════════════════════
# ANSI Colors for terminal output
# ═══════════════════════════════════════════════════════════════

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text):
    print(f"\n{'═' * 70}")
    print(f"{Colors.BOLD}{Colors.HEADER}  {text}{Colors.END}")
    print(f"{'═' * 70}\n")


def print_step(num, text):
    print(f"{Colors.BOLD}{Colors.CYAN}  [{num}] {text}{Colors.END}")


def print_success(text):
    print(f"  {Colors.GREEN}✓ {text}{Colors.END}")


def print_fail(text):
    print(f"  {Colors.RED}✗ {text}{Colors.END}")


def print_info(text):
    print(f"  {Colors.YELLOW}→ {text}{Colors.END}")


def print_data(label, value, max_len=60):
    if isinstance(value, bytes):
        display = value[:max_len].hex() + ("..." if len(value) > max_len else "")
        print(f"    {label}: [{len(value)} bytes] {display}")
    elif isinstance(value, str) and len(value) > max_len:
        print(f"    {label}: {value[:max_len]}...")
    else:
        print(f"    {label}: {value}")


# ═══════════════════════════════════════════════════════════════
# Standalone Demo (trực tiếp dùng crypto_module)
# ═══════════════════════════════════════════════════════════════

def run_standalone_demo():
    """Demo trực tiếp sử dụng crypto_module (không cần server/S3)."""

    print_header("DEMO: Mã hóa Phân cấp (HABE) — Standalone Mode")
    print_info("Sử dụng trực tiếp crypto_module (CP-ABE BSW07 + AES-256-CBC)")
    print()

    try:
        from crypto_module.core import HABECrypto
        from crypto_module.exceptions import AccessDeniedError, InvalidPolicyError
    except ImportError as e:
        print_fail(f"Không thể import crypto_module: {e}")
        print_info("Đảm bảo charm-crypto đã được cài đặt (xem README.md)")
        sys.exit(1)

    # ─── Step 1: Setup ───
    print_step(1, "SETUP — Khởi tạo hệ thống mã hóa")
    print_info("Tạo Master Public Key (MPK) và Master Secret Key (MSK)")
    print_info("Scheme: CP-ABE BSW07 | Pairing Group: SS512")
    print()

    crypto = HABECrypto(group_name="SS512")
    start = time.time()
    mpk_bytes, msk_bytes = crypto.setup()
    elapsed = time.time() - start

    print_success(f"Setup hoàn tất ({elapsed:.3f}s)")
    print_data("MPK size", mpk_bytes)
    print_data("MSK size", msk_bytes)
    print()

    # ─── Step 2: KeyGen ───
    print_step(2, "KEYGEN — Phát hành khóa người dùng")
    print()

    # User 1: Manager of Department A
    attrs_manager = ["COMPANY", "DEPTA", "MANAGER"]
    print_info(f"User 1 (Manager Dept A): attributes = {attrs_manager}")
    start = time.time()
    usk_manager = crypto.keygen(mpk_bytes, msk_bytes, attrs_manager)
    elapsed = time.time() - start
    print_success(f"USK generated ({elapsed:.3f}s)")
    print_data("USK size", usk_manager)
    print()

    # User 2: Employee of Department B
    attrs_employee = ["COMPANY", "DEPTB", "EMPLOYEE"]
    print_info(f"User 2 (Employee Dept B): attributes = {attrs_employee}")
    start = time.time()
    usk_employee = crypto.keygen(mpk_bytes, msk_bytes, attrs_employee)
    elapsed = time.time() - start
    print_success(f"USK generated ({elapsed:.3f}s)")
    print_data("USK size", usk_employee)
    print()

    # User 3: Admin (has all access)
    attrs_admin = ["COMPANY", "DEPTA", "DEPTB", "ADMIN", "MANAGER"]
    print_info(f"User 3 (Admin): attributes = {attrs_admin}")
    start = time.time()
    usk_admin = crypto.keygen(mpk_bytes, msk_bytes, attrs_admin)
    elapsed = time.time() - start
    print_success(f"USK generated ({elapsed:.3f}s)")
    print_data("USK size", usk_admin)
    print()

    # ─── Step 3: Encrypt ───
    print_step(3, "ENCRYPT — Mã hóa file với chính sách truy cập")
    print()

    # File content
    plaintext = b"[CONFIDENTIAL] Bao cao tai chinh Quy 4/2024 - Department A\n" \
                b"Doanh thu: 15.2 ty VND | Loi nhuan: 3.8 ty VND\n" \
                b"Chi tiet xem file dinh kem."
    access_policy = "MANAGER and DEPTA"

    print_info(f"Plaintext: {len(plaintext)} bytes")
    print_info(f"Access Policy: \"{access_policy}\"")
    print_info("Hybrid Encryption: ABE(GT element) + AES-256-CBC(plaintext) + HMAC-SHA256")
    print()

    start = time.time()
    ciphertext = crypto.encrypt(mpk_bytes, plaintext, access_policy)
    elapsed = time.time() - start

    print_success(f"Encryption hoàn tất ({elapsed:.3f}s)")
    print_data("Ciphertext size", ciphertext)
    print_info(f"Expansion ratio: {len(ciphertext)/len(plaintext):.1f}x")
    print()

    # ─── Step 4: Decrypt (Success) ───
    print_step(4, "DECRYPT — Giải mã với khóa hợp lệ")
    print()

    # Manager (has MANAGER AND DEPT_A) → should succeed
    print_info("User 1 (Manager Dept A) giải mã...")
    print_info(f"  Attributes: {attrs_manager}")
    print_info(f"  Policy cần: \"{access_policy}\"")
    print_info(f"  Thỏa mãn? MANAGER ∈ attrs ✓, DEPTA ∈ attrs ✓")
    start = time.time()
    decrypted = crypto.decrypt(mpk_bytes, usk_manager, ciphertext)
    elapsed = time.time() - start

    assert decrypted == plaintext, "Round-trip failed!"
    print_success(f"Giải mã thành công ({elapsed:.3f}s)")
    print_success("Plaintext khôi phục đúng 100% (byte-by-byte identical)")
    print_data("Decrypted", decrypted[:80])
    print()

    # Admin (has MANAGER AND DEPT_A among others) → should succeed
    print_info("User 3 (Admin) giải mã...")
    print_info(f"  Attributes: {attrs_admin}")
    print_info(f"  Thỏa mãn? MANAGER ∈ attrs ✓, DEPTA ∈ attrs ✓")
    start = time.time()
    decrypted_admin = crypto.decrypt(mpk_bytes, usk_admin, ciphertext)
    elapsed = time.time() - start

    assert decrypted_admin == plaintext
    print_success(f"Giải mã thành công ({elapsed:.3f}s)")
    print()

    # ─── Step 5: Decrypt (Access Denied) ───
    print_step(5, "ACCESS DENIED — Từ chối truy cập khi thuộc tính không thỏa mãn")
    print()

    # Employee Dept B (missing MANAGER and DEPT_A) → should fail
    print_info("User 2 (Employee Dept B) thử giải mã...")
    print_info(f"  Attributes: {attrs_employee}")
    print_info(f"  Policy cần: \"{access_policy}\"")
    print_info(f"  Thỏa mãn? MANAGER ∉ attrs ✗, DEPTA ∉ attrs ✗")

    try:
        crypto.decrypt(mpk_bytes, usk_employee, ciphertext)
        print_fail("LỖI: Giải mã thành công (không nên xảy ra!)")
    except AccessDeniedError as e:
        print_success(f"AccessDeniedError: {e}")
        print_success("Hệ thống từ chối truy cập đúng cách!")
    print()

    # ─── Step 6: Complex Policy Demo ───
    print_step(6, "COMPLEX POLICY — Chính sách phức tạp (OR)")
    print()

    complex_policy = "(MANAGER and DEPTA) or ADMIN"
    print_info(f"Policy: \"{complex_policy}\"")
    print_info("Cho phép: Manager của Dept A HOẶC Admin")
    print()

    ciphertext2 = crypto.encrypt(mpk_bytes, b"Secret data for complex policy", complex_policy)

    # Admin can decrypt (has ADMIN attribute)
    print_info("Admin giải mã (có ADMIN attribute)...")
    result = crypto.decrypt(mpk_bytes, usk_admin, ciphertext2)
    print_success(f"Thành công: {result.decode()}")

    # Employee cannot
    print_info("Employee Dept B thử giải mã...")
    try:
        crypto.decrypt(mpk_bytes, usk_employee, ciphertext2)
        print_fail("Không nên thành công!")
    except AccessDeniedError:
        print_success("Từ chối truy cập ✓")
    print()

    # ─── Step 7: Integrity Check ───
    print_step(7, "INTEGRITY — Phát hiện ciphertext bị sửa đổi")
    print()

    print_info("Sửa đổi 1 byte trong ciphertext...")
    corrupted = bytearray(ciphertext)
    corrupted[len(corrupted) // 2] ^= 0xFF  # Flip bits
    corrupted = bytes(corrupted)

    try:
        crypto.decrypt(mpk_bytes, usk_manager, corrupted)
        print_fail("Không phát hiện corruption!")
    except Exception as e:
        print_success(f"Phát hiện corruption: {type(e).__name__}")
        print_success("HMAC-SHA256 integrity check hoạt động đúng!")
    print()

    # ─── Summary ───
    print_header("KẾT QUẢ DEMO")
    print_success("Setup: Tạo cặp khóa Master (MPK, MSK) thành công")
    print_success("KeyGen: Phát hành khóa cho 3 users với thuộc tính phân cấp")
    print_success("Encrypt: Mã hóa hybrid (CP-ABE + AES-256-CBC + HMAC)")
    print_success("Decrypt: Giải mã thành công với khóa thỏa mãn policy")
    print_success("Access Control: Từ chối truy cập khi attributes không thỏa mãn")
    print_success("Integrity: Phát hiện ciphertext bị sửa đổi qua HMAC")
    print()
    print_info("Tất cả tính năng mã hóa phân cấp hoạt động chính xác!")
    print()


# ═══════════════════════════════════════════════════════════════
# API Demo (sử dụng HTTP requests đến server)
# ═══════════════════════════════════════════════════════════════

def run_api_demo(base_url="http://localhost:8000"):
    """Demo sử dụng API endpoints (cần server đang chạy)."""

    print_header("DEMO: Mã hóa Phân cấp (HABE) — API Mode")
    print_info(f"Server: {base_url}")
    print()

    try:
        import httpx
    except ImportError:
        print_fail("Cần cài httpx: pip install httpx")
        sys.exit(1)

    client = httpx.Client(base_url=base_url, timeout=30.0)

    # Health check
    print_step(0, "HEALTH CHECK")
    try:
        r = client.get("/health")
        health = r.json()
        print_success(f"Status: {health['status']}")
        print_info(f"S3 Connected: {health['s3_connected']}")
        print_info(f"Crypto Ready: {health['crypto_module_ready']}")
    except Exception as e:
        print_fail(f"Server không khả dụng: {e}")
        print_info(f"Đảm bảo server đang chạy tại {base_url}")
        sys.exit(1)
    print()

    # Step 1: Setup
    print_step(1, "SETUP — POST /admin/setup")
    r = client.post("/admin/setup")
    assert r.status_code == 200, f"Setup failed: {r.text}"
    setup_data = r.json()
    mpk = setup_data["master_public_key"]
    msk = setup_data["master_secret_key"]
    print_success(f"Scheme: {setup_data['scheme']}")
    print_data("MPK", mpk)
    print_data("MSK", msk)
    print()

    # Step 2: KeyGen
    print_step(2, "KEYGEN — POST /admin/keygen")
    print()

    # Manager
    r = client.post("/admin/keygen", json={
        "master_public_key": mpk,
        "master_secret_key": msk,
        "attributes": ["MANAGER", "DEPT_A", "COMPANY"],
    })
    assert r.status_code == 200, f"KeyGen failed: {r.text}"
    usk_manager = r.json()["user_secret_key"]
    print_success(f"Manager key generated (attributes: {r.json()['attributes']})")

    # Employee
    r = client.post("/admin/keygen", json={
        "master_public_key": mpk,
        "master_secret_key": msk,
        "attributes": ["EMPLOYEE", "DEPT_B", "COMPANY"],
    })
    assert r.status_code == 200
    usk_employee = r.json()["user_secret_key"]
    print_success(f"Employee key generated (attributes: {r.json()['attributes']})")
    print()

    # Step 3: Upload (Encrypt + Store)
    print_step(3, "UPLOAD — POST /files/upload (Encrypt + S3 Store)")
    file_content = b"[CONFIDENTIAL] Financial Report Q4/2024 - Department A"
    r = client.post("/files/upload", files={
        "file": ("report_q4.pdf", file_content, "application/pdf"),
    }, data={
        "access_policy": "MANAGER AND DEPT_A",
        "master_public_key": mpk,
        "storage_tier": "standard",
    })
    assert r.status_code == 200, f"Upload failed: {r.text}"
    upload_data = r.json()
    file_id = upload_data["file_id"]
    print_success(f"File uploaded: {upload_data['filename']}")
    print_info(f"File ID: {file_id}")
    print_info(f"Size: {upload_data['size_bytes']} bytes")
    print_info(f"Tier: {upload_data['storage_tier']}")
    print_info(f"Policy: {upload_data['access_policy']}")
    print()

    # Step 4: Download (Fetch + Decrypt) — Success
    print_step(4, "DOWNLOAD — GET /files/{id} (S3 Fetch + Decrypt)")
    print_info("Manager (MANAGER AND DEPT_A) downloads...")
    r = client.get(f"/files/{file_id}", headers={
        "x-user-secret-key": usk_manager,
        "x-master-public-key": mpk,
    })
    assert r.status_code == 200, f"Download failed: {r.status_code} {r.text}"
    assert r.content == file_content
    print_success("Download + Decrypt thành công!")
    print_success("Content matches original (byte-by-byte)")
    print()

    # Step 5: Download — Access Denied
    print_step(5, "ACCESS DENIED — Employee thử download")
    print_info("Employee (EMPLOYEE, DEPT_B) downloads...")
    r = client.get(f"/files/{file_id}", headers={
        "x-user-secret-key": usk_employee,
        "x-master-public-key": mpk,
    })
    assert r.status_code == 403
    print_success(f"HTTP 403 Forbidden: {r.json()['detail']}")
    print()

    # Step 6: Missing Auth
    print_step(6, "MISSING AUTH — Request không có khóa")
    r = client.get(f"/files/{file_id}")
    assert r.status_code == 401
    print_success(f"HTTP 401 Unauthorized: {r.json()['detail']}")
    print()

    # Summary
    print_header("KẾT QUẢ DEMO (API Mode)")
    print_success("POST /admin/setup → Tạo MPK + MSK")
    print_success("POST /admin/keygen → Phát hành USK theo attributes")
    print_success("POST /files/upload → Encrypt + Upload to S3")
    print_success("GET /files/{id} (valid key) → Download + Decrypt OK")
    print_success("GET /files/{id} (invalid key) → 403 Access Denied")
    print_success("GET /files/{id} (no key) → 401 Unauthorized")
    print()

    client.close()


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Demo End-to-End: HABE Crypto Backend"
    )
    parser.add_argument(
        "--api", action="store_true",
        help="Chạy demo qua API (cần server đang chạy)"
    )
    parser.add_argument(
        "--url", default="http://localhost:8000",
        help="Base URL của API server (mặc định: http://localhost:8000)"
    )
    args = parser.parse_args()

    if args.api:
        run_api_demo(args.url)
    else:
        run_standalone_demo()
