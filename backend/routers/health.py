"""Health check endpoint for the HABE Crypto Backend API.

Provides a GET /health endpoint that checks S3 connectivity
and crypto module readiness, returning overall system status.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from backend.models.responses import HealthResponse
from backend.services.storage_service import StorageService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API and S3 connectivity status.

    Returns a HealthResponse indicating:
    - "healthy" if both S3 and crypto module are operational
    - "degraded" if only one of S3 or crypto module is operational
    - "unhealthy" if neither S3 nor crypto module is operational
    """
    storage_service = StorageService()
    s3_connected = storage_service.check_connectivity()

    # Crypto module is ready if it can be imported and instantiated
    try:
        from crypto_module.core import HABECrypto

        HABECrypto()
        crypto_ready = True
    except Exception:
        crypto_ready = False

    # Determine overall status
    if s3_connected and crypto_ready:
        status = "healthy"
    elif s3_connected or crypto_ready:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        s3_connected=s3_connected,
        crypto_module_ready=crypto_ready,
        timestamp=datetime.now(timezone.utc),
    )
