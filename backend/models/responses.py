from datetime import datetime

from pydantic import BaseModel


class SetupResponse(BaseModel):
    master_public_key: str  # Base64-encoded
    master_secret_key: str  # Base64-encoded
    scheme: str = "CP-ABE-BSW07"
    group: str = "SS512"


class KeyGenResponse(BaseModel):
    user_secret_key: str  # Base64-encoded
    attributes: list[str]


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size_bytes: int
    storage_tier: str
    access_policy: str
    uploaded_at: datetime


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    timestamp: datetime


class HealthResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "unhealthy"
    s3_connected: bool
    crypto_module_ready: bool
    timestamp: datetime
