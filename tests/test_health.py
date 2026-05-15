"""API integration tests for the health check endpoint.

Tests the GET /health endpoint with mocked S3 (via moto) and
mocked crypto_module (to avoid charm-crypto dependency).

Validates: Requirements 8.5, 8.6
"""

import sys
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws
from httpx import AsyncClient, ASGITransport

from backend.config import settings

# Mock charm-crypto modules before importing the app so that
# crypto_module.core can be loaded without charm installed.
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


@pytest.fixture
async def client_with_s3():
    """Client with S3 buckets available (healthy scenario)."""
    with mock_aws():
        client = boto3.client("s3", region_name=settings.AWS_REGION)
        client.create_bucket(Bucket=settings.S3_BUCKET_STANDARD)
        client.create_bucket(Bucket=settings.S3_BUCKET_ARCHIVE)

        from backend.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def client_without_s3():
    """Client without S3 buckets (S3 unreachable scenario)."""
    with mock_aws():
        # Don't create any buckets - S3 head_bucket check will fail
        from backend.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


class TestHealthCheck:
    """Tests for the GET /health endpoint.

    Validates: Requirements 8.5, 8.6
    """

    @pytest.mark.asyncio
    async def test_healthy_when_s3_reachable(self, client_with_s3):
        """Health check returns 200 with status 'healthy' when S3 is reachable
        and crypto module is available.

        Validates: Requirement 8.5
        """
        with patch("crypto_module.core.HABECrypto") as mock_crypto_cls:
            mock_crypto_cls.return_value = MagicMock()

            response = await client_with_s3.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["s3_connected"] is True
        assert data["crypto_module_ready"] is True
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_unhealthy_when_s3_unreachable(self, client_without_s3):
        """Health check returns 200 with status 'unhealthy' when S3 is unreachable
        and crypto module is unavailable.

        Validates: Requirement 8.6
        """
        with patch(
            "crypto_module.core.HABECrypto", side_effect=Exception("not available")
        ):
            response = await client_without_s3.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["s3_connected"] is False
        assert data["crypto_module_ready"] is False
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_degraded_when_only_s3_reachable(self, client_with_s3):
        """Health check returns 200 with status 'degraded' when S3 is reachable
        but crypto module is unavailable.

        Validates: Requirements 8.5, 8.6
        """
        with patch(
            "crypto_module.core.HABECrypto", side_effect=Exception("not available")
        ):
            response = await client_with_s3.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["s3_connected"] is True
        assert data["crypto_module_ready"] is False
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_degraded_when_only_crypto_available(self, client_without_s3):
        """Health check returns 200 with status 'degraded' when S3 is unreachable
        but crypto module is available.

        Validates: Requirements 8.5, 8.6
        """
        with patch("crypto_module.core.HABECrypto") as mock_crypto_cls:
            mock_crypto_cls.return_value = MagicMock()

            response = await client_without_s3.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["s3_connected"] is False
        assert data["crypto_module_ready"] is True
        assert "timestamp" in data
