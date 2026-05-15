"""Serialization utilities for HABE crypto module.

Provides functions for serializing/deserializing:
- ABE keys (MPK, MSK, USK) using JSON envelope with base64-encoded Charm objectToBytes output
- Ciphertext bundles using MessagePack for efficient binary handling
"""

import base64
import json
from typing import Any

import msgpack

from crypto_module.exceptions import CryptoError, InvalidCiphertextError


# Constants
SCHEME = "CP-ABE-BSW07"
HYBRID_SCHEME = "CP-ABE-BSW07-HYBRID"
BUNDLE_VERSION = 1


def serialize_key(key_object: Any, group: Any) -> bytes:
    """Serialize a Charm key object to bytes using JSON envelope with base64 encoding.

    Format:
    {
        "scheme": "CP-ABE-BSW07",
        "group": "SS512",
        "key_data": "<base64-encoded Charm objectToBytes output>"
    }

    Args:
        key_object: A Charm crypto key object (MPK, MSK, or USK dict).
        group: The PairingGroup instance used for serialization.

    Returns:
        JSON-encoded bytes containing the key envelope.

    Raises:
        CryptoError: If serialization fails.
    """
    try:
        from charm.core.engine.util import objectToBytes

        # Serialize the key object using Charm's objectToBytes
        raw_bytes = objectToBytes(key_object, group)

        # Base64-encode the raw bytes
        key_data_b64 = base64.b64encode(raw_bytes).decode("utf-8")

        # Build the JSON envelope
        envelope = {
            "scheme": SCHEME,
            "group": group.groupType(),
            "key_data": key_data_b64,
        }

        # Serialize envelope to JSON bytes
        return json.dumps(envelope).encode("utf-8")
    except Exception as e:
        raise CryptoError(f"Key serialization failed: {e}") from e


def deserialize_key(key_bytes: bytes, group: Any) -> Any:
    """Deserialize a key from its JSON envelope format back to a Charm key object.

    Args:
        key_bytes: JSON-encoded bytes containing the key envelope.
        group: The PairingGroup instance used for deserialization.

    Returns:
        The deserialized Charm key object.

    Raises:
        CryptoError: If deserialization fails (invalid format, corrupted data, etc.).
    """
    try:
        from charm.core.engine.util import bytesToObject

        # Parse the JSON envelope
        envelope = json.loads(key_bytes.decode("utf-8"))

        # Validate envelope structure
        if not isinstance(envelope, dict):
            raise CryptoError("Invalid key envelope: not a JSON object.")
        for field in ("scheme", "group", "key_data"):
            if field not in envelope:
                raise CryptoError(f"Invalid key envelope: missing '{field}' field.")

        # Decode base64 key data
        raw_bytes = base64.b64decode(envelope["key_data"])

        # Deserialize using Charm's bytesToObject
        return bytesToObject(raw_bytes, group)
    except CryptoError:
        raise
    except Exception as e:
        raise CryptoError(f"Key deserialization failed: {e}") from e


def serialize_ciphertext_bundle(
    abe_ct: bytes,
    aes_ct: bytes,
    iv: bytes,
    hmac: bytes,
    policy: str,
    metadata: dict,
) -> bytes:
    """Serialize a hybrid ciphertext bundle using MessagePack.

    Format:
    {
        "version": 1,
        "scheme": "CP-ABE-BSW07-HYBRID",
        "access_policy": "<policy string>",
        "abe_ciphertext": "<base64-encoded ABE ciphertext>",
        "aes_ciphertext": "<base64-encoded AES-CBC encrypted data>",
        "aes_iv": "<base64-encoded 16-byte IV>",
        "hmac": "<base64-encoded HMAC-SHA256>",
        "metadata": { ... }
    }

    Args:
        abe_ct: Raw ABE ciphertext bytes (already serialized via Charm).
        aes_ct: AES-CBC encrypted data bytes.
        iv: 16-byte AES initialization vector.
        hmac: HMAC-SHA256 bytes for integrity verification.
        policy: The access policy string used for encryption.
        metadata: Dictionary with file metadata (original_filename, original_size,
                  content_type, encrypted_at).

    Returns:
        MessagePack-encoded bytes of the ciphertext bundle.

    Raises:
        CryptoError: If serialization fails.
    """
    try:
        bundle = {
            "version": BUNDLE_VERSION,
            "scheme": HYBRID_SCHEME,
            "access_policy": policy,
            "abe_ciphertext": base64.b64encode(abe_ct).decode("utf-8"),
            "aes_ciphertext": base64.b64encode(aes_ct).decode("utf-8"),
            "aes_iv": base64.b64encode(iv).decode("utf-8"),
            "hmac": base64.b64encode(hmac).decode("utf-8"),
            "metadata": metadata,
        }

        return msgpack.packb(bundle, use_bin_type=True)
    except Exception as e:
        raise CryptoError(f"Ciphertext bundle serialization failed: {e}") from e


def deserialize_ciphertext_bundle(bundle_bytes: bytes) -> dict:
    """Deserialize a MessagePack-encoded ciphertext bundle.

    Args:
        bundle_bytes: MessagePack-encoded bytes of the ciphertext bundle.

    Returns:
        Dictionary with the following keys (binary fields are base64-decoded):
        - version (int)
        - scheme (str)
        - access_policy (str)
        - abe_ciphertext (bytes) - decoded from base64
        - aes_ciphertext (bytes) - decoded from base64
        - aes_iv (bytes) - decoded from base64
        - hmac (bytes) - decoded from base64
        - metadata (dict)

    Raises:
        InvalidCiphertextError: If the bundle is corrupted or malformed.
    """
    try:
        bundle = msgpack.unpackb(bundle_bytes, raw=False)

        if not isinstance(bundle, dict):
            raise InvalidCiphertextError("Ciphertext bundle is not a valid structure.")

        # Validate required fields
        required_fields = [
            "version", "scheme", "access_policy",
            "abe_ciphertext", "aes_ciphertext", "aes_iv", "hmac",
        ]
        for field in required_fields:
            if field not in bundle:
                raise InvalidCiphertextError(
                    f"Ciphertext bundle missing required field: '{field}'."
                )

        # Decode base64 binary fields
        return {
            "version": bundle["version"],
            "scheme": bundle["scheme"],
            "access_policy": bundle["access_policy"],
            "abe_ciphertext": base64.b64decode(bundle["abe_ciphertext"]),
            "aes_ciphertext": base64.b64decode(bundle["aes_ciphertext"]),
            "aes_iv": base64.b64decode(bundle["aes_iv"]),
            "hmac": base64.b64decode(bundle["hmac"]),
            "metadata": bundle.get("metadata", {}),
        }
    except InvalidCiphertextError:
        raise
    except Exception as e:
        raise InvalidCiphertextError(
            f"Ciphertext bundle deserialization failed: {e}"
        ) from e
