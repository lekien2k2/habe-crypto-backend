"""Global exception handlers for the HABE Backend API.

Maps crypto module exceptions and storage errors to appropriate HTTP responses.
All error responses use the ErrorResponse schema with error_code, message, and timestamp.
Sensitive data (keys, plaintext) is never included in error responses.
"""

from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from crypto_module.exceptions import (
    CryptoDecryptError,
    CryptoEncryptError,
    CryptoError,
    CryptoKeyGenError,
    CryptoSetupError,
    AccessDeniedError,
    InvalidAttributeSetError,
    InvalidCiphertextError,
    InvalidPolicyError,
)
from backend.services.storage_service import (
    FileNotFoundError as StorageFileNotFoundError,
    StorageUnavailableError,
)


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Build a standardized JSON error response.

    Args:
        status_code: HTTP status code.
        error_code: Machine-readable error code string.
        message: Human-readable error description (must not contain sensitive data).

    Returns:
        JSONResponse with ErrorResponse schema body.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI application.

    Handlers are registered from most specific to most general to ensure
    proper exception matching (subclass handlers before parent class handlers).

    Args:
        app: The FastAPI application instance.
    """

    # --- Specific crypto exceptions (400-level) ---

    @app.exception_handler(InvalidAttributeSetError)
    async def handle_invalid_attributes(
        request: Request, exc: InvalidAttributeSetError
    ) -> JSONResponse:
        return _error_response(400, "INVALID_ATTRIBUTES", str(exc))

    @app.exception_handler(InvalidPolicyError)
    async def handle_invalid_policy(
        request: Request, exc: InvalidPolicyError
    ) -> JSONResponse:
        return _error_response(400, "INVALID_POLICY", str(exc))

    @app.exception_handler(AccessDeniedError)
    async def handle_access_denied(
        request: Request, exc: AccessDeniedError
    ) -> JSONResponse:
        return _error_response(403, "ACCESS_DENIED", str(exc))

    @app.exception_handler(InvalidCiphertextError)
    async def handle_invalid_ciphertext(
        request: Request, exc: InvalidCiphertextError
    ) -> JSONResponse:
        return _error_response(400, "INVALID_CIPHERTEXT", str(exc))

    # --- General crypto exceptions (500-level) ---

    @app.exception_handler(CryptoSetupError)
    async def handle_crypto_setup(
        request: Request, exc: CryptoSetupError
    ) -> JSONResponse:
        return _error_response(500, "CRYPTO_SETUP_FAILED", "Crypto system initialization failed")

    @app.exception_handler(CryptoKeyGenError)
    async def handle_crypto_keygen(
        request: Request, exc: CryptoKeyGenError
    ) -> JSONResponse:
        return _error_response(500, "CRYPTO_KEYGEN_FAILED", "Key generation failed")

    @app.exception_handler(CryptoEncryptError)
    async def handle_crypto_encrypt(
        request: Request, exc: CryptoEncryptError
    ) -> JSONResponse:
        return _error_response(500, "CRYPTO_ENCRYPT_FAILED", "Encryption failed")

    @app.exception_handler(CryptoDecryptError)
    async def handle_crypto_decrypt(
        request: Request, exc: CryptoDecryptError
    ) -> JSONResponse:
        return _error_response(500, "CRYPTO_DECRYPT_FAILED", "Decryption failed")

    @app.exception_handler(CryptoError)
    async def handle_crypto_generic(
        request: Request, exc: CryptoError
    ) -> JSONResponse:
        return _error_response(500, "CRYPTO_ERROR", "A cryptographic operation failed")

    # --- Storage exceptions ---

    @app.exception_handler(StorageFileNotFoundError)
    async def handle_file_not_found(
        request: Request, exc: StorageFileNotFoundError
    ) -> JSONResponse:
        return _error_response(404, "FILE_NOT_FOUND", str(exc))

    @app.exception_handler(StorageUnavailableError)
    async def handle_storage_unavailable(
        request: Request, exc: StorageUnavailableError
    ) -> JSONResponse:
        return _error_response(503, "S3_UNAVAILABLE", "Storage service is unavailable")

    # --- Catch-all for unhandled exceptions ---

    @app.exception_handler(Exception)
    async def handle_generic(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")
