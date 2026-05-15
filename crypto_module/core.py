"""Core HABE/CP-ABE cryptographic operations using Charm-crypto.

Provides the HABECrypto class implementing Setup, KeyGen, Encrypt, and Decrypt
operations using the Bethencourt-Sahai-Waters CP-ABE scheme (CPabe_BSW07).
"""

import hashlib
import hmac as hmac_module
import os
from typing import Tuple

from charm.core.engine.util import objectToBytes, bytesToObject
from charm.toolbox.pairinggroup import PairingGroup, GT
from charm.schemes.abenc.abenc_bsw07 import CPabe_BSW07
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from crypto_module.exceptions import (
    AccessDeniedError,
    CryptoDecryptError,
    CryptoEncryptError,
    CryptoSetupError,
    CryptoKeyGenError,
    InvalidAttributeSetError,
    InvalidCiphertextError,
    InvalidPolicyError,
)
from crypto_module.serialization import (
    serialize_key,
    deserialize_key,
    serialize_ciphertext_bundle,
    deserialize_ciphertext_bundle,
)


class HABECrypto:
    """Core HABE/CP-ABE cryptographic operations using Charm-crypto."""

    def __init__(self, group_name: str = "SS512"):
        """Initialize with a pairing group.

        Args:
            group_name: Pairing group identifier (default: SS512).

        Raises:
            CryptoSetupError: If pairing group initialization fails.
        """
        try:
            self.group = PairingGroup(group_name)
            self.cpabe = CPabe_BSW07(self.group)
        except Exception as e:
            raise CryptoSetupError(
                f"Failed to initialize pairing group '{group_name}': {e}"
            ) from e

    def setup(self) -> Tuple[bytes, bytes]:
        """Generate master public key and master secret key.

        Returns:
            Tuple of (master_public_key_bytes, master_secret_key_bytes).
            Both keys are serialized for storage/transmission.

        Raises:
            CryptoSetupError: If key generation or serialization fails.
        """
        try:
            (mpk, msk) = self.cpabe.setup()
            mpk_bytes = serialize_key(mpk, self.group)
            msk_bytes = serialize_key(msk, self.group)
            return (mpk_bytes, msk_bytes)
        except CryptoSetupError:
            raise
        except Exception as e:
            raise CryptoSetupError(f"Setup failed: {e}") from e

    def keygen(
        self,
        master_public_key: bytes,
        master_secret_key: bytes,
        attributes: list,
    ) -> bytes:
        """Generate a user secret key for a given attribute set.

        Args:
            master_public_key: Serialized MPK from setup().
            master_secret_key: Serialized MSK from setup().
            attributes: List of attribute strings (e.g., ["Manager", "Dept_A"]).

        Returns:
            Serialized user secret key bytes.

        Raises:
            InvalidAttributeSetError: If attributes list is empty or contains
                invalid values (non-string or whitespace-only).
            CryptoKeyGenError: If key generation fails for other reasons.
        """
        # Validate attributes
        self._validate_attributes(attributes)

        try:
            mpk = deserialize_key(master_public_key, self.group)
            msk = deserialize_key(master_secret_key, self.group)
            usk = self.cpabe.keygen(mpk, msk, attributes)
            return serialize_key(usk, self.group)
        except InvalidAttributeSetError:
            raise
        except Exception as e:
            raise CryptoKeyGenError(f"Key generation failed: {e}") from e

    def _validate_attributes(self, attributes: list) -> None:
        """Validate that attributes is a non-empty list of valid strings.

        Args:
            attributes: The attribute list to validate.

        Raises:
            InvalidAttributeSetError: If validation fails.
        """
        if not isinstance(attributes, list) or len(attributes) == 0:
            raise InvalidAttributeSetError(
                "Attribute set must be a non-empty list."
            )

        for i, attr in enumerate(attributes):
            if not isinstance(attr, str):
                raise InvalidAttributeSetError(
                    f"Attribute at index {i} is not a string: {type(attr).__name__}."
                )
            if attr.strip() == "":
                raise InvalidAttributeSetError(
                    f"Attribute at index {i} is empty or whitespace-only."
                )

    def encrypt(
        self,
        master_public_key: bytes,
        plaintext: bytes,
        access_policy: str,
    ) -> bytes:
        """Encrypt data under an access policy using hybrid encryption.

        Internally:
        1. Generates a random 32-byte AES key
        2. ABE-encrypts the AES key under the access policy
        3. AES-CBC encrypts the plaintext with PKCS7 padding
        4. Computes HMAC-SHA256 over the AES ciphertext for integrity
        5. Bundles everything into MessagePack format

        Args:
            master_public_key: Serialized MPK from setup().
            plaintext: Raw bytes to encrypt (any size).
            access_policy: Boolean formula (e.g., "Manager AND Dept_A").

        Returns:
            Serialized ciphertext bundle bytes (MessagePack format).

        Raises:
            InvalidPolicyError: If access_policy syntax is invalid.
            CryptoEncryptError: If encryption fails for other reasons.
        """
        # Validate access policy syntax
        self._validate_policy(access_policy)

        try:
            # Deserialize the master public key
            mpk = deserialize_key(master_public_key, self.group)

            # Step 1: Generate a random GT element and derive AES key from it
            key_element = self.group.random(GT)

            # Derive AES key from the group element
            element_bytes = objectToBytes(key_element, self.group)
            aes_key = hashlib.sha256(element_bytes).digest()

            # ABE-encrypt the group element under the policy
            try:
                abe_ct = self.cpabe.encrypt(mpk, key_element, access_policy)
            except Exception as e:
                error_msg = str(e).lower()
                if ("policy" in error_msg or "parse" in error_msg
                        or "invalid" in error_msg or "attribute" in error_msg
                        or "literal" in error_msg):
                    raise InvalidPolicyError(
                        f"Access policy is invalid: {e}"
                    ) from e
                raise

            if abe_ct is None or abe_ct is False:
                raise InvalidPolicyError(
                    "ABE encryption returned None - policy may be invalid"
                )

            # Serialize the ABE ciphertext dict element by element
            # Charm's ABE ciphertext is a dict with pairing elements + metadata
            abe_ct_serialized = {}
            for key, value in abe_ct.items():
                try:
                    # Try to serialize as a pairing group element
                    abe_ct_serialized[key] = self.group.serialize(value)
                except (TypeError, AttributeError):
                    # Non-element values (strings, ints, etc.) store as-is
                    abe_ct_serialized[key] = value

            import json
            abe_ct_bytes = json.dumps(abe_ct_serialized, default=str).encode('utf-8')

            # Step 3: AES-CBC encrypt the plaintext
            iv = os.urandom(16)
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            padded_plaintext = pad(plaintext, AES.block_size)
            aes_ct = cipher.encrypt(padded_plaintext)

            # Step 4: Compute HMAC-SHA256 over the AES ciphertext
            hmac_value = hmac_module.new(
                aes_key, aes_ct, hashlib.sha256
            ).digest()

            # Step 5: Bundle into MessagePack format
            metadata = {
                "original_size": len(plaintext),
            }

            bundle = serialize_ciphertext_bundle(
                abe_ct=abe_ct_bytes,
                aes_ct=aes_ct,
                iv=iv,
                hmac=hmac_value,
                policy=access_policy,
                metadata=metadata,
            )

            return bundle

        except InvalidPolicyError:
            raise
        except CryptoEncryptError:
            raise
        except Exception as e:
            raise CryptoEncryptError(f"Encryption failed: {e}") from e

    def _validate_policy(self, access_policy: str) -> None:
        """Validate access policy syntax.

        Performs basic validation of the access policy string before
        passing it to Charm's ABE encrypt function.

        Args:
            access_policy: The policy string to validate.

        Raises:
            InvalidPolicyError: If the policy is invalid.
        """
        if not isinstance(access_policy, str):
            raise InvalidPolicyError(
                "Access policy must be a string."
            )

        stripped = access_policy.strip()
        if not stripped:
            raise InvalidPolicyError(
                "Access policy must not be empty."
            )

        # Check for unbalanced parentheses
        depth = 0
        for ch in stripped:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            if depth < 0:
                raise InvalidPolicyError(
                    "Access policy has unbalanced parentheses."
                )
        if depth != 0:
            raise InvalidPolicyError(
                "Access policy has unbalanced parentheses."
            )

    def decrypt(
        self,
        master_public_key: bytes,
        user_secret_key: bytes,
        ciphertext: bytes,
    ) -> bytes:
        """Decrypt ciphertext using a user's secret key.

        Internally:
        1. Unpacks the ciphertext bundle (MessagePack)
        2. ABE-decrypts to recover the GT element
        3. Derives AES key from GT element using SHA-256
        4. Verifies HMAC-SHA256 integrity of AES ciphertext
        5. AES-CBC decrypts the file data with PKCS7 unpadding

        Args:
            master_public_key: Serialized MPK from setup().
            user_secret_key: Serialized USK from keygen().
            ciphertext: Serialized ciphertext bundle from encrypt().

        Returns:
            Original plaintext bytes.

        Raises:
            AccessDeniedError: If user attributes don't satisfy the policy.
            InvalidCiphertextError: If ciphertext is corrupted or malformed.
            CryptoDecryptError: If decryption fails for other reasons.
        """
        try:
            # Step 1: Deserialize the ciphertext bundle
            bundle = deserialize_ciphertext_bundle(ciphertext)

            # Deserialize MPK and USK
            mpk = deserialize_key(master_public_key, self.group)
            usk = deserialize_key(user_secret_key, self.group)

            # Step 2: Deserialize the ABE ciphertext and ABE-decrypt
            import json
            abe_ct_serialized = json.loads(bundle["abe_ciphertext"].decode('utf-8'))
            abe_ct = {}
            for key, value in abe_ct_serialized.items():
                try:
                    # Try to deserialize as a pairing group element
                    if isinstance(value, str) and len(value) > 0:
                        abe_ct[key] = self.group.deserialize(value.encode('utf-8'))
                    else:
                        abe_ct[key] = value
                except (TypeError, ValueError, Exception):
                    abe_ct[key] = value

            # ABE-decrypt to recover the GT element
            key_element = self.cpabe.decrypt(mpk, usk, abe_ct)

            # Charm returns False when attributes don't satisfy the policy
            if key_element is False or key_element is None:
                raise AccessDeniedError(
                    "Access denied: attributes do not satisfy the access policy."
                )

            # Step 3: Derive AES key from the recovered GT element
            element_bytes = objectToBytes(key_element, self.group)
            aes_key = hashlib.sha256(element_bytes).digest()

            # Step 4: Verify HMAC-SHA256 integrity
            expected_hmac = hmac_module.new(
                aes_key, bundle["aes_ciphertext"], hashlib.sha256
            ).digest()

            if not hmac_module.compare_digest(expected_hmac, bundle["hmac"]):
                raise InvalidCiphertextError(
                    "Ciphertext integrity check failed: HMAC mismatch."
                )

            # Step 5: AES-CBC decrypt with PKCS7 unpadding
            cipher = AES.new(aes_key, AES.MODE_CBC, bundle["aes_iv"])
            padded_plaintext = cipher.decrypt(bundle["aes_ciphertext"])
            plaintext = unpad(padded_plaintext, AES.block_size)

            return plaintext

        except AccessDeniedError:
            raise
        except InvalidCiphertextError:
            raise
        except CryptoDecryptError:
            raise
        except Exception as e:
            raise CryptoDecryptError(f"Decryption failed: {e}") from e
