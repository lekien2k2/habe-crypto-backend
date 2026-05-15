"""Service layer wrapping the crypto module for API use.

Handles base64 encoding/decoding of keys for HTTP transport
and provides a clean interface for the API routers.
"""

import base64
from typing import Tuple

from crypto_module.core import HABECrypto
from crypto_module.exceptions import CryptoError


class CryptoService:
    """Service layer wrapping the crypto module for API use.

    Handles base64 encoding/decoding of keys for HTTP transport
    and provides a clean interface for the API routers.
    """

    def __init__(self):
        self._crypto = HABECrypto()

    def perform_setup(self) -> Tuple[str, str]:
        """Initialize crypto system and return base64-encoded keys.

        Returns:
            Tuple of (mpk_base64, msk_base64)

        Raises:
            CryptoSetupError: If pairing group initialization fails.
        """
        mpk_bytes, msk_bytes = self._crypto.setup()
        return (
            base64.b64encode(mpk_bytes).decode("utf-8"),
            base64.b64encode(msk_bytes).decode("utf-8"),
        )

    def generate_key(self, mpk_b64: str, msk_b64: str, attributes: list[str]) -> str:
        """Generate user secret key and return base64-encoded.

        Args:
            mpk_b64: Base64-encoded master public key
            msk_b64: Base64-encoded master secret key
            attributes: List of user attributes

        Returns:
            Base64-encoded user secret key

        Raises:
            InvalidAttributeSetError: If attributes list is empty or invalid.
            CryptoKeyGenError: If key generation fails.
        """
        mpk_bytes = base64.b64decode(mpk_b64)
        msk_bytes = base64.b64decode(msk_b64)
        usk_bytes = self._crypto.keygen(mpk_bytes, msk_bytes, attributes)
        return base64.b64encode(usk_bytes).decode("utf-8")

    def encrypt_file(self, mpk_b64: str, plaintext: bytes, policy: str) -> bytes:
        """Encrypt file data under an access policy.

        Args:
            mpk_b64: Base64-encoded master public key
            plaintext: Raw file bytes
            policy: Access policy string

        Returns:
            Ciphertext bundle bytes

        Raises:
            InvalidPolicyError: If access policy syntax is invalid.
            CryptoEncryptError: If encryption fails.
        """
        mpk_bytes = base64.b64decode(mpk_b64)
        return self._crypto.encrypt(mpk_bytes, plaintext, policy)

    def decrypt_file(self, mpk_b64: str, usk_b64: str, ciphertext: bytes) -> bytes:
        """Decrypt file data using user's secret key.

        Args:
            mpk_b64: Base64-encoded master public key
            usk_b64: Base64-encoded user secret key
            ciphertext: Ciphertext bundle bytes

        Returns:
            Original plaintext bytes

        Raises:
            AccessDeniedError: If user attributes don't satisfy the policy.
            InvalidCiphertextError: If ciphertext is corrupted or malformed.
            CryptoDecryptError: If decryption fails for other reasons.
        """
        mpk_bytes = base64.b64decode(mpk_b64)
        usk_bytes = base64.b64decode(usk_b64)
        return self._crypto.decrypt(mpk_bytes, usk_bytes, ciphertext)
