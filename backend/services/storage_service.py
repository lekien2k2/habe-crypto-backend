"""Storage service for S3 interaction via Boto3.

Provides upload, download, and connectivity checking for encrypted files
stored in AWS S3 tiered storage (standard and archive buckets).
"""

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from backend.config import settings

logger = logging.getLogger(__name__)


class FileNotFoundError(Exception):
    """Raised when a requested file does not exist in S3."""

    def __init__(self, file_id: str, tier: str = "standard"):
        self.file_id = file_id
        self.tier = tier
        super().__init__(f"File '{file_id}' not found in {tier} storage")


class StorageUnavailableError(Exception):
    """Raised when S3 storage is unreachable or unavailable."""

    def __init__(self, message: str = "Storage service is unavailable"):
        super().__init__(message)


class StorageService:
    """S3 storage service for encrypted file operations.

    Uses Boto3 to interact with AWS S3 buckets configured for
    standard and archive storage tiers.
    """

    def __init__(self) -> None:
        """Initialize the StorageService with a Boto3 S3 client."""
        self._client = boto3.client("s3", region_name=settings.AWS_REGION)
        self._buckets = {
            "standard": settings.S3_BUCKET_STANDARD,
            "archive": settings.S3_BUCKET_ARCHIVE,
        }

    def _get_bucket(self, tier: str) -> str:
        """Resolve storage tier to bucket name.

        Args:
            tier: Storage tier ("standard" or "archive").

        Returns:
            The S3 bucket name for the given tier.

        Raises:
            ValueError: If the tier is not recognized.
        """
        if tier not in self._buckets:
            raise ValueError(
                f"Invalid storage tier '{tier}'. Must be one of: {list(self._buckets.keys())}"
            )
        return self._buckets[tier]

    def _build_object_key(self, file_id: str, tier: str) -> str:
        """Build the S3 object key following the convention: {tier}/{file_id}.enc

        Args:
            file_id: Unique file identifier.
            tier: Storage tier.

        Returns:
            The S3 object key string.
        """
        return f"{tier}/{file_id}.enc"

    def upload_file(
        self,
        file_id: str,
        data: bytes,
        tier: str = "standard",
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Upload encrypted file data to S3.

        Args:
            file_id: Unique identifier for the file.
            data: Encrypted file bytes to store.
            tier: Storage tier ("standard" or "archive").
            metadata: Optional metadata tags (original_filename, access_policy,
                      encrypted_at, content_type).

        Returns:
            Dict with upload details: bucket, key, size_bytes, tier.

        Raises:
            StorageUnavailableError: If S3 is unreachable.
            ValueError: If the tier is invalid.
        """
        bucket = self._get_bucket(tier)
        key = self._build_object_key(file_id, tier)

        put_kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": data,
        }

        # Store metadata as S3 object metadata (not tags - tags have character restrictions)
        if metadata:
            put_kwargs["Metadata"] = {
                k: str(v)[:256] for k, v in metadata.items() if v is not None
            }

        try:
            self._client.put_object(**put_kwargs)
        except (EndpointConnectionError, NoCredentialsError) as exc:
            logger.error("S3 connection error during upload: %s", exc)
            raise StorageUnavailableError(
                f"Unable to connect to S3 for upload: {exc}"
            ) from exc
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            logger.error("S3 ClientError during upload: %s (code=%s)", exc, error_code)
            raise StorageUnavailableError(
                f"S3 upload failed: {error_code}"
            ) from exc

        return {
            "bucket": bucket,
            "key": key,
            "size_bytes": len(data),
            "tier": tier,
        }

    def download_file(self, file_id: str, tier: str = "standard") -> bytes:
        """Download encrypted file data from S3.

        Args:
            file_id: Unique identifier for the file.
            tier: Storage tier ("standard" or "archive").

        Returns:
            The encrypted file bytes.

        Raises:
            FileNotFoundError: If the file does not exist in S3.
            StorageUnavailableError: If S3 is unreachable.
            ValueError: If the tier is invalid.
        """
        bucket = self._get_bucket(tier)
        key = self._build_object_key(file_id, tier)

        try:
            response = self._client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404"):
                raise FileNotFoundError(file_id, tier) from exc
            logger.error(
                "S3 ClientError during download: %s (code=%s)", exc, error_code
            )
            raise StorageUnavailableError(
                f"S3 download failed: {error_code}"
            ) from exc
        except (EndpointConnectionError, NoCredentialsError) as exc:
            logger.error("S3 connection error during download: %s", exc)
            raise StorageUnavailableError(
                f"Unable to connect to S3 for download: {exc}"
            ) from exc

    def check_connectivity(self) -> bool:
        """Check if S3 storage is reachable by performing a head_bucket call.

        Returns:
            True if the standard bucket is accessible, False otherwise.
        """
        bucket = self._buckets["standard"]
        try:
            self._client.head_bucket(Bucket=bucket)
            return True
        except (ClientError, EndpointConnectionError, NoCredentialsError):
            return False
