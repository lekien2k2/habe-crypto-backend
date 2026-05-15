"""File upload and download endpoints with encryption/decryption.

Provides endpoints for:
- Uploading files with ABE encryption under an access policy
- Downloading and decrypting files using a user's secret key
"""

import uuid
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.models.responses import UploadResponse
from backend.services.crypto_service import CryptoService
from backend.services.storage_service import (
    FileNotFoundError as StorageFileNotFoundError,
    StorageService,
)
from crypto_module.exceptions import AccessDeniedError

router = APIRouter(prefix="/files", tags=["files"])

crypto_service = CryptoService()
storage_service = StorageService()


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    access_policy: str = Form(...),
    master_public_key: str = Form(...),
    storage_tier: str = Form(default="standard"),
) -> UploadResponse:
    """Encrypt and upload a file to S3.

    Accepts a multipart form with the file, access policy, master public key,
    and optional storage tier. Encrypts the file under the given policy and
    stores the ciphertext in S3.

    Returns metadata about the uploaded file including its unique ID.
    """
    # Read file content
    content = await file.read()

    # Validate file size
    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB",
        )

    # Encrypt the file
    ciphertext = crypto_service.encrypt_file(master_public_key, content, access_policy)

    # Generate file ID
    file_id = str(uuid.uuid4())

    # Upload to S3
    metadata = {
        "original_filename": file.filename or "unknown",
        "access_policy": access_policy,
        "encrypted_at": datetime.now(timezone.utc).isoformat(),
        "content_type": file.content_type or "application/octet-stream",
    }

    storage_service.upload_file(file_id, ciphertext, tier=storage_tier, metadata=metadata)

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "unknown",
        size_bytes=len(content),
        storage_tier=storage_tier,
        access_policy=access_policy,
        uploaded_at=datetime.now(timezone.utc),
    )


@router.get("/{file_id}")
async def download_file(
    file_id: str,
    x_user_secret_key: str = Header(default=None),
    x_master_public_key: str = Header(default=None),
    storage_tier: str = "standard",
):
    """Download and decrypt a file from S3.

    Requires the user's secret key and master public key via headers.
    Downloads the encrypted file from S3, decrypts it using the provided
    keys, and returns the plaintext as a streaming response.

    Raises:
        HTTPException 401: If authentication headers are missing.
        HTTPException 403: If user attributes don't satisfy the access policy.
        HTTPException 404: If the file is not found in storage.
    """
    # Check for required auth headers
    if not x_user_secret_key or not x_master_public_key:
        raise HTTPException(status_code=401, detail="Missing authentication headers")

    # Download from S3
    try:
        ciphertext = storage_service.download_file(file_id, tier=storage_tier)
    except StorageFileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    # Decrypt
    try:
        plaintext = crypto_service.decrypt_file(
            x_master_public_key, x_user_secret_key, ciphertext
        )
    except AccessDeniedError:
        raise HTTPException(
            status_code=403,
            detail="Access denied: attributes do not satisfy the access policy",
        )

    return StreamingResponse(
        BytesIO(plaintext),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={file_id}"},
    )
