"""crypto_module - Hierarchical Attribute-Based Encryption (HABE) core module."""

from crypto_module.exceptions import (
    AccessDeniedError,
    CryptoDecryptError,
    CryptoEncryptError,
    CryptoError,
    CryptoKeyGenError,
    CryptoSetupError,
    InvalidAttributeSetError,
    InvalidCiphertextError,
    InvalidPolicyError,
)

try:
    from crypto_module.core import HABECrypto
except ImportError:
    HABECrypto = None  # charm-crypto not available

__all__ = [
    "HABECrypto",
    "CryptoError",
    "CryptoSetupError",
    "CryptoKeyGenError",
    "CryptoEncryptError",
    "CryptoDecryptError",
    "InvalidAttributeSetError",
    "InvalidPolicyError",
    "AccessDeniedError",
    "InvalidCiphertextError",
]
