"""Custom exceptions for the HABE crypto module.

Exception hierarchy:
    CryptoError (base)
    ├── CryptoSetupError
    ├── CryptoKeyGenError
    │   └── InvalidAttributeSetError
    ├── CryptoEncryptError
    │   └── InvalidPolicyError
    └── CryptoDecryptError
        ├── AccessDeniedError
        └── InvalidCiphertextError
"""


class CryptoError(Exception):
    """Base exception for all crypto module errors."""

    def __init__(self, message: str = "A cryptographic operation failed."):
        self.message = message
        super().__init__(self.message)


class CryptoSetupError(CryptoError):
    """Raised when pairing group or system parameter initialization fails."""

    def __init__(self, message: str = "Crypto system setup failed."):
        super().__init__(message)


class CryptoKeyGenError(CryptoError):
    """Raised when user secret key generation fails."""

    def __init__(self, message: str = "Key generation failed."):
        super().__init__(message)


class CryptoEncryptError(CryptoError):
    """Raised when encryption operation fails."""

    def __init__(self, message: str = "Encryption failed."):
        super().__init__(message)


class CryptoDecryptError(CryptoError):
    """Raised when decryption operation fails."""

    def __init__(self, message: str = "Decryption failed."):
        super().__init__(message)


class InvalidAttributeSetError(CryptoKeyGenError):
    """Raised when the attribute set is empty or contains invalid values."""

    def __init__(self, message: str = "Attribute set is empty or contains invalid values."):
        super().__init__(message)


class InvalidPolicyError(CryptoEncryptError):
    """Raised when the access policy string has invalid syntax."""

    def __init__(self, message: str = "Access policy syntax is invalid."):
        super().__init__(message)


class AccessDeniedError(CryptoDecryptError):
    """Raised when user attributes do not satisfy the ciphertext access policy."""

    def __init__(self, message: str = "Access denied: attributes do not satisfy the access policy."):
        super().__init__(message)


class InvalidCiphertextError(CryptoDecryptError):
    """Raised when the ciphertext is corrupted or malformed."""

    def __init__(self, message: str = "Ciphertext is corrupted or malformed."):
        super().__init__(message)
