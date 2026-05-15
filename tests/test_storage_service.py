"""Unit tests for StorageService using moto for S3 mocking."""

import boto3
import pytest
from moto import mock_aws

from backend.config import settings
from backend.services.storage_service import (
    FileNotFoundError as StorageFileNotFoundError,
    StorageService,
    StorageUnavailableError,
)


@pytest.fixture
def s3_setup():
    """Set up mocked S3 buckets for testing."""
    with mock_aws():
        client = boto3.client("s3", region_name=settings.AWS_REGION)
        client.create_bucket(Bucket=settings.S3_BUCKET_STANDARD)
        client.create_bucket(
            Bucket=settings.S3_BUCKET_ARCHIVE,
            CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION}
            if settings.AWS_REGION != "us-east-1"
            else {},
        )
        yield client


@pytest.fixture
def storage_service(s3_setup):
    """Create a StorageService instance within the mocked AWS context."""
    return StorageService()


class TestUploadFile:
    """Tests for StorageService.upload_file."""

    def test_upload_standard_tier(self, storage_service, s3_setup):
        """Upload to standard tier stores data correctly."""
        file_id = "test-file-001"
        data = b"encrypted content here"

        result = storage_service.upload_file(file_id, data, tier="standard")

        assert result["bucket"] == settings.S3_BUCKET_STANDARD
        assert result["key"] == "standard/test-file-001.enc"
        assert result["size_bytes"] == len(data)
        assert result["tier"] == "standard"

        # Verify data was actually stored
        obj = s3_setup.get_object(
            Bucket=settings.S3_BUCKET_STANDARD, Key="standard/test-file-001.enc"
        )
        assert obj["Body"].read() == data

    def test_upload_archive_tier(self, storage_service, s3_setup):
        """Upload to archive tier stores data in the archive bucket."""
        file_id = "archive-file-001"
        data = b"archived encrypted content"

        result = storage_service.upload_file(file_id, data, tier="archive")

        assert result["bucket"] == settings.S3_BUCKET_ARCHIVE
        assert result["key"] == "archive/archive-file-001.enc"
        assert result["tier"] == "archive"

    def test_upload_with_metadata(self, storage_service, s3_setup):
        """Upload with metadata stores tags on the S3 object."""
        file_id = "meta-file-001"
        data = b"data with metadata"
        metadata = {
            "original_filename": "report.pdf",
            "access_policy": "Manager AND Dept_A",
            "encrypted_at": "2024-01-15T10:30:00Z",
            "content_type": "application/pdf",
        }

        result = storage_service.upload_file(
            file_id, data, tier="standard", metadata=metadata
        )

        assert result["size_bytes"] == len(data)

        # Verify tags were stored
        tags_response = s3_setup.get_object_tagging(
            Bucket=settings.S3_BUCKET_STANDARD, Key="standard/meta-file-001.enc"
        )
        tag_set = {
            tag["Key"]: tag["Value"] for tag in tags_response["TagSet"]
        }
        assert tag_set["original_filename"] == "report.pdf"
        assert tag_set["content_type"] == "application/pdf"

    def test_upload_invalid_tier_raises_value_error(self, storage_service):
        """Upload with invalid tier raises ValueError."""
        with pytest.raises(ValueError, match="Invalid storage tier"):
            storage_service.upload_file("file-001", b"data", tier="invalid")

    def test_upload_empty_data(self, storage_service, s3_setup):
        """Upload with empty bytes succeeds."""
        result = storage_service.upload_file("empty-file", b"", tier="standard")
        assert result["size_bytes"] == 0


class TestDownloadFile:
    """Tests for StorageService.download_file."""

    def test_download_existing_file(self, storage_service, s3_setup):
        """Download returns the stored file data."""
        file_id = "download-test-001"
        data = b"encrypted file content for download"

        # Upload first
        storage_service.upload_file(file_id, data, tier="standard")

        # Download
        result = storage_service.download_file(file_id, tier="standard")
        assert result == data

    def test_download_nonexistent_file_raises_not_found(self, storage_service):
        """Download of non-existent file raises FileNotFoundError."""
        with pytest.raises(StorageFileNotFoundError) as exc_info:
            storage_service.download_file("nonexistent-file", tier="standard")

        assert exc_info.value.file_id == "nonexistent-file"
        assert exc_info.value.tier == "standard"

    def test_download_invalid_tier_raises_value_error(self, storage_service):
        """Download with invalid tier raises ValueError."""
        with pytest.raises(ValueError, match="Invalid storage tier"):
            storage_service.download_file("file-001", tier="unknown")

    def test_upload_then_download_roundtrip(self, storage_service):
        """Upload and download returns identical data."""
        file_id = "roundtrip-001"
        original_data = b"\x00\x01\x02\xff" * 1000  # Binary data

        storage_service.upload_file(file_id, original_data, tier="standard")
        downloaded = storage_service.download_file(file_id, tier="standard")

        assert downloaded == original_data


class TestCheckConnectivity:
    """Tests for StorageService.check_connectivity."""

    def test_connectivity_success(self, storage_service):
        """check_connectivity returns True when bucket is accessible."""
        assert storage_service.check_connectivity() is True

    def test_connectivity_failure_nonexistent_bucket(self, s3_setup):
        """check_connectivity returns False when bucket doesn't exist."""
        # Override settings to point to a non-existent bucket
        original = settings.S3_BUCKET_STANDARD
        settings.S3_BUCKET_STANDARD = "nonexistent-bucket-xyz"
        service = StorageService()
        result = service.check_connectivity()
        settings.S3_BUCKET_STANDARD = original
        assert result is False
