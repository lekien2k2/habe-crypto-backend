"""Admin endpoints for the HABE Crypto Backend API.

Provides POST /admin/setup and POST /admin/keygen endpoints
for initializing the crypto system and generating user keys.
"""

from fastapi import APIRouter

from backend.models.requests import KeyGenRequest
from backend.models.responses import KeyGenResponse, SetupResponse
from backend.services.crypto_service import CryptoService

router = APIRouter(prefix="/admin", tags=["admin"])

# Service instance
crypto_service = CryptoService()


@router.post("/setup", response_model=SetupResponse)
async def setup_crypto() -> SetupResponse:
    """Initialize the HABE crypto system. Returns MPK and MSK."""
    mpk_b64, msk_b64 = crypto_service.perform_setup()
    return SetupResponse(
        master_public_key=mpk_b64,
        master_secret_key=msk_b64,
    )


@router.post("/keygen", response_model=KeyGenResponse)
async def generate_user_key(request: KeyGenRequest) -> KeyGenResponse:
    """Generate a user secret key for the given attributes."""
    usk_b64 = crypto_service.generate_key(
        request.master_public_key,
        request.master_secret_key,
        request.attributes,
    )
    return KeyGenResponse(
        user_secret_key=usk_b64,
        attributes=request.attributes,
    )
