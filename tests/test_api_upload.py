"""API integration tests for the upload endpoint.

Tests the POST /files/upload endpoint with mocked S3 (via moto) and
mocked crypto_service (to avoid charm-crypto dependency).

Validates: Requirements 6.1, 6.2, 6.5, 6.6, 6.7, 10.1, 10.2, 10.4, 10.5
"""

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
from hypothesis import given, settings as hypothesis_settings, HealthCheck
from hypothesis import strategies as st
from moto import mock_aws

from backend.config import settings
from crypto_module.exceptions import (
    CryptoEncryptError,
    InvalidPolicyError,
)


# Mock charm-crypto modules before importing the app so that
# backend.services.crypto_service can be loaded without charm installed.
_charm_mocks = {}
for mod_name in [
    "charm",
    "charm.core",
    "charm.core.engine",
    "charm.core.engine.util",
    "charm.toolbox",
    "charm.toolbox.pairinggroup",
    "charm.schemes",
    "charm.schemes.abenc",
    "charm.schemes.abenc.abenc_bsw07",
]:
    if mod_name not in sys.modules:
        _charm_mocks[mod_name] = MagicMock()
        sys.modules[mod_name] = _charm_mocks[mod_name]


@pytest.fixture(autouse=True)
def _mock_s3_env():
    """Set up mocked S3 buckets for all tests in this module."""
    with mock_aws():
        client = boto3.client("s3", region_name=settings.AWS_REGION)
        client.create_bucket(Bucket=settings.S3_BUCKET_STANDARD)
        client.create_bucket(Bucket=settings.S3_BUCKET_ARCHIVE)
        yield client


@pytest.fixture(autouse=True)
def _mock_crypto():
    """Mock the crypto service to avoid charm-crypto dependency.

    Patches the crypto_service instance used in the files router so that
    encrypt_file returns fake ciphertext without needing charm-crypto.
    """
    with patch("backend.routers.files.crypto_service") as mock_cs:
        mock_cs.encrypt_file.return_value = b"fake_encrypted_data"
        yield mock_cs


@pytest.fixture
def mock_crypto_ref(_mock_crypto):
    """Expose the mock crypto service for tests that need to configure it."""
    return _mock_crypto


@pytest.fixture
async def client():
    """Create async test client for the FastAPI app."""
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _validate_error_response(response_json: dict) -> None:
    """Validate that a response body conforms to the ErrorResponse schema.

    Checks for required fields: error_code (str), message (str), timestamp (ISO 8601).
    """
    assert "error_code" in response_json, "Missing 'error_code' field"
    assert "message" in response_json, "Missing 'message' field"
    assert "timestamp" in response_json, "Missing 'timestamp' field"

    assert isinstance(response_json["error_code"], str), "error_code must be a string"
    assert isinstance(response_json["message"], str), "message must be a string"
    assert isinstance(response_json["timestamp"], str), "timestamp must be a string"

    # Validate timestamp is ISO 8601 parseable
    datetime.fromisoformat(response_json["timestamp"].replace("Z", "+00:00"))


class TestUploadSuccess:
    """Tests for successful file upload."""

    @pytest.mark.asyncio
    async def test_successful_upload_returns_upload_response(self, client):
        """Successful upload returns UploadResponse with correct metadata."""
        response = await client.post(
            "/files/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
            data={
                "access_policy": "Manager AND Dept_A",
                "master_public_key": "base64encodedkey",
                "storage_tier": "standard",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "file_id" in data
        assert data["filename"] == "test.txt"
        assert data["access_policy"] == "Manager AND Dept_A"
        assert data["storage_tier"] == "standard"
        assert data["size_bytes"] == len(b"hello world")
        assert "uploaded_at" in data

    @pytest.mark.asyncio
    async def test_successful_upload_archive_tier(self, client):
        """Upload with archive tier stores in archive bucket."""
        response = await client.post(
            "/files/upload",
            files={"file": ("report.pdf", b"pdf content", "application/pdf")},
            data={
                "access_policy": "Admin",
                "master_public_key": "base64key",
                "storage_tier": "archive",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["storage_tier"] == "archive"
        assert data["filename"] == "report.pdf"

    @pytest.mark.asyncio
    async def test_successful_upload_default_tier(self, client):
        """Upload without explicit tier defaults to standard."""
        response = await client.post(
            "/files/upload",
            files={"file": ("data.bin", b"\x00\x01\x02", "application/octet-stream")},
            data={
                "access_policy": "Employee OR Manager",
                "master_public_key": "base64key",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["storage_tier"] == "standard"


class TestUploadMissingFile:
    """Tests for missing file in upload request."""

    @pytest.mark.asyncio
    async def test_missing_file_returns_422(self, client):
        """Missing file field returns 422 (FastAPI validation error)."""
        response = await client.post(
            "/files/upload",
            data={
                "access_policy": "Manager AND Dept_A",
                "master_public_key": "base64encodedkey",
            },
        )

        assert response.status_code == 422


class TestUploadMissingPolicy:
    """Tests for missing access_policy in upload request."""

    @pytest.mark.asyncio
    async def test_missing_access_policy_returns_422(self, client):
        """Missing access_policy field returns 422 (FastAPI validation error)."""
        response = await client.post(
            "/files/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
            data={
                "master_public_key": "base64key",
            },
        )

        assert response.status_code == 422


class TestUploadInvalidPolicy:
    """Tests for invalid access policy syntax."""

    @pytest.mark.asyncio
    async def test_invalid_policy_returns_400(self, client, mock_crypto_ref):
        """Invalid policy syntax returns 400 with ErrorResponse."""
        mock_crypto_ref.encrypt_file.side_effect = InvalidPolicyError(
            "Access policy syntax error: unbalanced parentheses"
        )

        response = await client.post(
            "/files/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
            data={
                "access_policy": "((Manager AND",
                "master_public_key": "base64key",
            },
        )

        assert response.status_code == 400
        data = response.json()
        _validate_error_response(data)
        assert data["error_code"] == "INVALID_POLICY"


class TestUploadFileTooLarge:
    """Tests for file size exceeding maximum."""

    @pytest.mark.asyncio
    async def test_file_too_large_returns_413(self, client):
        """File exceeding MAX_FILE_SIZE_MB returns 413."""
        # Create data larger than MAX_FILE_SIZE_MB
        large_data = b"x" * (settings.MAX_FILE_SIZE_MB * 1024 * 1024 + 1)

        response = await client.post(
            "/files/upload",
            files={"file": ("large.bin", large_data, "application/octet-stream")},
            data={
                "access_policy": "Admin",
                "master_public_key": "base64key",
            },
        )

        assert response.status_code == 413


class TestUploadS3Failure:
    """Tests for S3 upload failures."""

    @pytest.mark.asyncio
    async def test_s3_failure_returns_503(self, client):
        """S3 upload failure returns 503 with ErrorResponse."""
        with patch("backend.routers.files.storage_service") as mock_storage:
            from backend.services.storage_service import StorageUnavailableError

            mock_storage.upload_file.side_effect = StorageUnavailableError(
                "S3 upload failed: InternalError"
            )

            response = await client.post(
                "/files/upload",
                files={"file": ("test.txt", b"hello", "text/plain")},
                data={
                    "access_policy": "Manager AND Dept_A",
                    "master_public_key": "base64key",
                },
            )

            assert response.status_code == 503
            data = response.json()
            _validate_error_response(data)
            assert data["error_code"] == "S3_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_crypto_encrypt_failure_returns_500(self, client, mock_crypto_ref):
        """Crypto encryption failure returns 500 with ErrorResponse."""
        mock_crypto_ref.encrypt_file.side_effect = CryptoEncryptError(
            "Encryption failed due to internal error"
        )

        response = await client.post(
            "/files/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
            data={
                "access_policy": "Manager AND Dept_A",
                "master_public_key": "base64key",
            },
        )

        assert response.status_code == 500
        data = response.json()
        _validate_error_response(data)
        assert data["error_code"] == "CRYPTO_ENCRYPT_FAILED"


class TestErrorResponseFormatConsistency:
    """Property 6: Error Response Format Consistency.

    Verify all error responses match ErrorResponse schema containing exactly:
    error_code (string), message (string), and timestamp (ISO 8601 datetime).

    **Validates: Requirements 10.4**
    """

    @pytest.mark.asyncio
    async def test_422_response_format(self, client):
        """422 validation errors have proper format (FastAPI default)."""
        # Missing file - FastAPI returns its own validation error format
        response = await client.post(
            "/files/upload",
            data={
                "access_policy": "Manager AND Dept_A",
                "master_public_key": "base64key",
            },
        )
        assert response.status_code == 422
        # FastAPI 422 has its own format with "detail" field
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_400_invalid_policy_error_format(self, client, mock_crypto_ref):
        """400 error from invalid policy matches ErrorResponse schema."""
        mock_crypto_ref.encrypt_file.side_effect = InvalidPolicyError(
            "Invalid policy syntax"
        )

        response = await client.post(
            "/files/upload",
            files={"file": ("test.txt", b"data", "text/plain")},
            data={
                "access_policy": "INVALID(((",
                "master_public_key": "base64key",
            },
        )

        assert response.status_code == 400
        _validate_error_response(response.json())

    @pytest.mark.asyncio
    async def test_413_error_format(self, client):
        """413 error from oversized file has proper HTTP status."""
        large_data = b"x" * (settings.MAX_FILE_SIZE_MB * 1024 * 1024 + 1)

        response = await client.post(
            "/files/upload",
            files={"file": ("large.bin", large_data, "application/octet-stream")},
            data={
                "access_policy": "Admin",
                "master_public_key": "base64key",
            },
        )

        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_500_crypto_error_format(self, client, mock_crypto_ref):
        """500 error from crypto failure matches ErrorResponse schema."""
        mock_crypto_ref.encrypt_file.side_effect = CryptoEncryptError("Internal failure")

        response = await client.post(
            "/files/upload",
            files={"file": ("test.txt", b"data", "text/plain")},
            data={
                "access_policy": "Admin",
                "master_public_key": "base64key",
            },
        )

        assert response.status_code == 500
        _validate_error_response(response.json())

    @pytest.mark.asyncio
    async def test_503_storage_error_format(self, client):
        """503 error from S3 failure matches ErrorResponse schema."""
        with patch("backend.routers.files.storage_service") as mock_storage:
            from backend.services.storage_service import StorageUnavailableError

            mock_storage.upload_file.side_effect = StorageUnavailableError()

            response = await client.post(
                "/files/upload",
                files={"file": ("test.txt", b"data", "text/plain")},
                data={
                    "access_policy": "Admin",
                    "master_public_key": "base64key",
                },
            )

            assert response.status_code == 503
            _validate_error_response(response.json())

    @hypothesis_settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        filename=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters="._-"
            ),
            min_size=1,
            max_size=50,
        ),
        content=st.binary(min_size=1, max_size=1024),
        policy_fragment=st.sampled_from(
            [
                "(((",
                "AND AND",
                "OR",
                "AND",
                "((A AND B",
                "A AND AND B",
            ]
        ),
    )
    @pytest.mark.asyncio
    async def test_property_error_responses_match_schema(
        self, client, mock_crypto_ref, filename, content, policy_fragment
    ):
        """Property 6: Error Response Format Consistency.

        For any API request that triggers an error condition, the response body
        SHALL conform to the ErrorResponse schema containing exactly: error_code
        (string), message (string), and timestamp (ISO 8601 datetime).

        **Validates: Requirements 10.4**
        """
        mock_crypto_ref.encrypt_file.side_effect = InvalidPolicyError(
            f"Invalid policy: {policy_fragment}"
        )

        response = await client.post(
            "/files/upload",
            files={"file": (filename, content, "application/octet-stream")},
            data={
                "access_policy": policy_fragment,
                "master_public_key": "base64key",
            },
        )

        # All invalid policy errors should return 400
        assert response.status_code == 400
        data = response.json()
        _validate_error_response(data)
        assert data["error_code"] == "INVALID_POLICY"
