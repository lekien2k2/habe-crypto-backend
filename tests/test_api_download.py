"""API integration tests for the download endpoint.

Tests the GET /files/{file_id} endpoint with mocked S3 (via moto) and
mocked crypto_service (to avoid charm-crypto dependency).

Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 10.3
"""

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from backend.config import settings
from crypto_module.exceptions import AccessDeniedError


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
    """Set up mocked S3 buckets with a pre-uploaded test file."""
    with mock_aws():
        client = boto3.client("s3", region_name=settings.AWS_REGION)
        client.create_bucket(Bucket=settings.S3_BUCKET_STANDARD)
        client.create_bucket(Bucket=settings.S3_BUCKET_ARCHIVE)
        # Pre-upload a test encrypted file
        client.put_object(
            Bucket=settings.S3_BUCKET_STANDARD,
            Key="standard/test-file-123.enc",
            Body=b"fake_encrypted_data",
        )
        yield client


@pytest.fixture(autouse=True)
def _mock_crypto():
    """Mock the crypto service to avoid charm-crypto dependency.

    Patches the crypto_service instance used in the files router so that
    decrypt_file returns fake plaintext without needing charm-crypto.
    """
    with patch("backend.routers.files.crypto_service") as mock_cs:
        mock_cs.decrypt_file.return_value = b"original plaintext content"
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


class TestDownloadSuccess:
    """Tests for successful file download.

    Validates: Requirements 7.1, 7.2, 7.3, 7.4
    """

    @pytest.mark.asyncio
    async def test_successful_download_returns_plaintext(self, client):
        """Successful download returns decrypted file content as bytes.

        End-to-end flow: file exists in S3, crypto_service decrypts it,
        response contains the original plaintext.
        """
        response = await client.get(
            "/files/test-file-123",
            headers={
                "x-user-secret-key": "base64usk",
                "x-master-public-key": "base64mpk",
            },
        )

        assert response.status_code == 200
        assert response.content == b"original plaintext content"

    @pytest.mark.asyncio
    async def test_successful_download_content_type(self, client):
        """Successful download returns application/octet-stream content type."""
        response = await client.get(
            "/files/test-file-123",
            headers={
                "x-user-secret-key": "base64usk",
                "x-master-public-key": "base64mpk",
            },
        )

        assert response.status_code == 200
        assert "application/octet-stream" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_successful_download_content_disposition(self, client):
        """Successful download includes Content-Disposition header with file ID."""
        response = await client.get(
            "/files/test-file-123",
            headers={
                "x-user-secret-key": "base64usk",
                "x-master-public-key": "base64mpk",
            },
        )

        assert response.status_code == 200
        assert "content-disposition" in response.headers
        assert "test-file-123" in response.headers["content-disposition"]

    @pytest.mark.asyncio
    async def test_end_to_end_upload_then_download(self, client, mock_crypto_ref):
        """End-to-end: upload a file then download it, verify content matches.

        Validates: Requirements 7.1, 7.2, 7.3, 7.4
        """
        original_content = b"secret document content for e2e test"
        mock_crypto_ref.encrypt_file.return_value = b"encrypted_e2e_data"
        mock_crypto_ref.decrypt_file.return_value = original_content

        # Upload
        upload_response = await client.post(
            "/files/upload",
            files={"file": ("secret.txt", original_content, "text/plain")},
            data={
                "access_policy": "Manager AND Dept_A",
                "master_public_key": "base64mpk",
                "storage_tier": "standard",
            },
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]

        # Patch storage_service to serve the uploaded ciphertext for this file_id
        with patch("backend.routers.files.storage_service") as mock_storage:
            mock_storage.download_file.return_value = b"encrypted_e2e_data"

            # Download
            download_response = await client.get(
                f"/files/{file_id}",
                headers={
                    "x-user-secret-key": "base64usk",
                    "x-master-public-key": "base64mpk",
                },
            )

        assert download_response.status_code == 200
        assert download_response.content == original_content


class TestDownloadAccessDenied:
    """Tests for access denied (non-matching key).

    Validates: Requirements 7.5
    """

    @pytest.mark.asyncio
    async def test_non_matching_key_returns_403(self, client, mock_crypto_ref):
        """Non-matching user secret key returns 403 Forbidden."""
        mock_crypto_ref.decrypt_file.side_effect = AccessDeniedError()

        response = await client.get(
            "/files/test-file-123",
            headers={
                "x-user-secret-key": "wrong_key",
                "x-master-public-key": "base64mpk",
            },
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_access_denied_response_detail(self, client, mock_crypto_ref):
        """403 response includes meaningful detail about access denial."""
        mock_crypto_ref.decrypt_file.side_effect = AccessDeniedError()

        response = await client.get(
            "/files/test-file-123",
            headers={
                "x-user-secret-key": "wrong_key",
                "x-master-public-key": "base64mpk",
            },
        )

        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert "access" in data["detail"].lower() or "denied" in data["detail"].lower()


class TestDownloadNotFound:
    """Tests for file not found in S3.

    Validates: Requirements 7.6
    """

    @pytest.mark.asyncio
    async def test_file_not_found_returns_404(self, client):
        """Non-existent file ID returns 404 Not Found."""
        response = await client.get(
            "/files/nonexistent-file-id",
            headers={
                "x-user-secret-key": "base64usk",
                "x-master-public-key": "base64mpk",
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_file_not_found_response_detail(self, client):
        """404 response includes meaningful detail about missing file."""
        response = await client.get(
            "/files/nonexistent-file-id",
            headers={
                "x-user-secret-key": "base64usk",
                "x-master-public-key": "base64mpk",
            },
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestDownloadMissingAuth:
    """Tests for missing authentication headers.

    Validates: Requirements 10.3
    """

    @pytest.mark.asyncio
    async def test_missing_all_auth_headers_returns_401(self, client):
        """Missing both auth headers returns 401 Unauthorized."""
        response = await client.get("/files/test-file-123")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_usk_header_returns_401(self, client):
        """Missing x-user-secret-key header returns 401 Unauthorized."""
        response = await client.get(
            "/files/test-file-123",
            headers={"x-master-public-key": "base64mpk"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_mpk_header_returns_401(self, client):
        """Missing x-master-public-key header returns 401 Unauthorized."""
        response = await client.get(
            "/files/test-file-123",
            headers={"x-user-secret-key": "base64usk"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_auth_response_detail(self, client):
        """401 response includes meaningful detail about missing auth."""
        response = await client.get("/files/test-file-123")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


class TestDownloadS3Failure:
    """Tests for S3 download failures.

    Validates: Requirements 7.7
    """

    @pytest.mark.asyncio
    async def test_s3_failure_returns_503(self, client):
        """S3 download failure returns 503 with ErrorResponse."""
        with patch("backend.routers.files.storage_service") as mock_storage:
            from backend.services.storage_service import StorageUnavailableError

            mock_storage.download_file.side_effect = StorageUnavailableError(
                "S3 download failed: InternalError"
            )

            response = await client.get(
                "/files/test-file-123",
                headers={
                    "x-user-secret-key": "base64usk",
                    "x-master-public-key": "base64mpk",
                },
            )

            assert response.status_code == 503
            data = response.json()
            _validate_error_response(data)
            assert data["error_code"] == "S3_UNAVAILABLE"
