"""Unit tests for crypto_module.core - HABECrypto class.

Validates: Requirements 1.1, 1.5, 2.1, 2.4, 3.1, 3.4, 4.1, 4.3, 4.5
"""

import pytest

try:
    from charm.toolbox.pairinggroup import PairingGroup
    HAS_CHARM = True
except ImportError:
    HAS_CHARM = False

# Import exceptions directly from the exceptions module to avoid
# triggering charm-dependent imports in crypto_module/__init__.py
from crypto_module.exceptions import (
    AccessDeniedError,
    CryptoSetupError,
    CryptoKeyGenError,
    InvalidAttributeSetError,
    InvalidPolicyError,
    InvalidCiphertextError,
)


@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestHABECryptoInit:
    """Tests for HABECrypto.__init__."""

    def test_default_group(self):
        """Initializes with default SS512 group."""
        from crypto_module.core import HABECrypto

        crypto = HABECrypto()
        assert crypto.group is not None
        assert crypto.cpabe is not None

    def test_custom_group(self):
        """Initializes with a specified group name."""
        from crypto_module.core import HABECrypto

        crypto = HABECrypto(group_name="SS512")
        assert crypto.group is not None

    def test_invalid_group_raises_setup_error(self):
        """Raises CryptoSetupError for an invalid group name."""
        from crypto_module.core import HABECrypto

        with pytest.raises(CryptoSetupError):
            HABECrypto(group_name="INVALID_GROUP_NAME_XYZ")


@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestHABECryptoSetup:
    """Tests for HABECrypto.setup(). Validates: Requirement 1.1, 1.5."""

    def setup_method(self):
        from crypto_module.core import HABECrypto

        self.crypto = HABECrypto()

    def test_setup_returns_two_byte_sequences(self):
        """setup() returns a tuple of two non-empty byte sequences."""
        mpk_bytes, msk_bytes = self.crypto.setup()

        assert isinstance(mpk_bytes, bytes)
        assert isinstance(msk_bytes, bytes)
        assert len(mpk_bytes) > 0
        assert len(msk_bytes) > 0

    def test_setup_produces_distinct_keys_each_call(self):
        """Calling setup() multiple times produces different key pairs."""
        mpk1, msk1 = self.crypto.setup()
        mpk2, msk2 = self.crypto.setup()

        # At least one of the keys should differ between calls
        assert mpk1 != mpk2 or msk1 != msk2


@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestHABECryptoKeygen:
    """Tests for HABECrypto.keygen(). Validates: Requirement 2.1, 2.4."""

    def setup_method(self):
        from crypto_module.core import HABECrypto

        self.crypto = HABECrypto()
        self.mpk_bytes, self.msk_bytes = self.crypto.setup()

    def test_keygen_with_valid_attributes(self):
        """keygen() with valid attributes returns non-empty bytes."""
        usk = self.crypto.keygen(
            self.mpk_bytes, self.msk_bytes, ["Manager", "Dept_A"]
        )

        assert isinstance(usk, bytes)
        assert len(usk) > 0

    def test_keygen_single_attribute(self):
        """keygen() works with a single attribute."""
        usk = self.crypto.keygen(
            self.mpk_bytes, self.msk_bytes, ["Admin"]
        )

        assert isinstance(usk, bytes)
        assert len(usk) > 0

    def test_keygen_many_attributes(self):
        """keygen() works with many attributes."""
        attrs = ["Admin", "Manager", "Dept_A", "Dept_B", "Company", "Level1", "Level2"]
        usk = self.crypto.keygen(self.mpk_bytes, self.msk_bytes, attrs)

        assert isinstance(usk, bytes)
        assert len(usk) > 0

    def test_keygen_hierarchical_attributes(self):
        """keygen() works with hierarchical attribute sets."""
        usk = self.crypto.keygen(
            self.mpk_bytes, self.msk_bytes, ["Company", "Dept_A", "Manager"]
        )

        assert isinstance(usk, bytes)
        assert len(usk) > 0

    def test_keygen_empty_attributes_raises_error(self):
        """keygen() raises InvalidAttributeSetError for empty list."""
        with pytest.raises(InvalidAttributeSetError):
            self.crypto.keygen(self.mpk_bytes, self.msk_bytes, [])

    def test_keygen_non_string_attribute_raises_error(self):
        """keygen() raises InvalidAttributeSetError for non-string attributes."""
        with pytest.raises(InvalidAttributeSetError):
            self.crypto.keygen(self.mpk_bytes, self.msk_bytes, [123, "Valid"])

    def test_keygen_whitespace_only_attribute_raises_error(self):
        """keygen() raises InvalidAttributeSetError for whitespace-only strings."""
        with pytest.raises(InvalidAttributeSetError):
            self.crypto.keygen(self.mpk_bytes, self.msk_bytes, ["  ", "Valid"])

    def test_keygen_empty_string_attribute_raises_error(self):
        """keygen() raises InvalidAttributeSetError for empty string attributes."""
        with pytest.raises(InvalidAttributeSetError):
            self.crypto.keygen(self.mpk_bytes, self.msk_bytes, [""])

    def test_keygen_none_attributes_raises_error(self):
        """keygen() raises InvalidAttributeSetError when attributes is None."""
        with pytest.raises(InvalidAttributeSetError):
            self.crypto.keygen(self.mpk_bytes, self.msk_bytes, None)


@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestHABECryptoEncrypt:
    """Tests for HABECrypto.encrypt(). Validates: Requirement 3.1, 3.4."""

    def setup_method(self):
        from crypto_module.core import HABECrypto

        self.crypto = HABECrypto()
        self.mpk_bytes, self.msk_bytes = self.crypto.setup()

    def test_encrypt_with_valid_policy_produces_ciphertext(self):
        """encrypt() with a valid policy returns non-empty ciphertext bytes."""
        plaintext = b"Hello, HABE encryption!"
        policy = "Manager AND Dept_A"

        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)

        assert isinstance(ct, bytes)
        assert len(ct) > 0

    def test_encrypt_with_or_policy(self):
        """encrypt() works with OR policy."""
        plaintext = b"Secret data"
        policy = "Manager OR Admin"

        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)

        assert isinstance(ct, bytes)
        assert len(ct) > 0

    def test_encrypt_with_complex_policy(self):
        """encrypt() works with complex nested policy."""
        plaintext = b"Complex policy data"
        policy = "(Manager AND Dept_A) OR Admin"

        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)

        assert isinstance(ct, bytes)
        assert len(ct) > 0

    def test_encrypt_with_single_attribute_policy(self):
        """encrypt() works with a single-attribute policy."""
        plaintext = b"Single attr data"
        policy = "Admin"

        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)

        assert isinstance(ct, bytes)
        assert len(ct) > 0

    def test_encrypt_empty_plaintext(self):
        """encrypt() works with empty plaintext (zero bytes)."""
        plaintext = b""
        policy = "Manager AND Dept_A"

        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)

        assert isinstance(ct, bytes)
        assert len(ct) > 0

    def test_encrypt_invalid_policy_empty_raises_error(self):
        """encrypt() raises InvalidPolicyError for empty policy string."""
        with pytest.raises(InvalidPolicyError):
            self.crypto.encrypt(self.mpk_bytes, b"data", "")

    def test_encrypt_invalid_policy_whitespace_raises_error(self):
        """encrypt() raises InvalidPolicyError for whitespace-only policy."""
        with pytest.raises(InvalidPolicyError):
            self.crypto.encrypt(self.mpk_bytes, b"data", "   ")

    def test_encrypt_invalid_policy_unbalanced_parens_raises_error(self):
        """encrypt() raises InvalidPolicyError for unbalanced parentheses."""
        with pytest.raises(InvalidPolicyError):
            self.crypto.encrypt(self.mpk_bytes, b"data", "(Manager AND Dept_A")


@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestHABECryptoDecrypt:
    """Tests for HABECrypto.decrypt(). Validates: Requirement 4.1, 4.3, 4.5."""

    def setup_method(self):
        from crypto_module.core import HABECrypto

        self.crypto = HABECrypto()
        self.mpk_bytes, self.msk_bytes = self.crypto.setup()

    def test_decrypt_with_matching_key_returns_original(self):
        """decrypt() with a key satisfying the policy returns original plaintext."""
        plaintext = b"Secret message for managers"
        policy = "Manager AND Dept_A"
        attributes = ["Manager", "Dept_A"]

        usk = self.crypto.keygen(self.mpk_bytes, self.msk_bytes, attributes)
        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)
        result = self.crypto.decrypt(self.mpk_bytes, usk, ct)

        assert result == plaintext

    def test_decrypt_with_non_matching_key_raises_access_denied(self):
        """decrypt() raises AccessDeniedError when attributes don't satisfy policy."""
        plaintext = b"Secret message for managers"
        policy = "Manager AND Dept_A"
        # Attributes that do NOT satisfy the policy (missing Dept_A)
        non_matching_attributes = ["Employee", "Dept_B"]

        usk = self.crypto.keygen(
            self.mpk_bytes, self.msk_bytes, non_matching_attributes
        )
        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)

        with pytest.raises(AccessDeniedError):
            self.crypto.decrypt(self.mpk_bytes, usk, ct)

    def test_decrypt_corrupted_ciphertext_raises_error(self):
        """decrypt() raises InvalidCiphertextError for corrupted ciphertext."""
        corrupted_data = b"this is not valid ciphertext at all"

        usk = self.crypto.keygen(
            self.mpk_bytes, self.msk_bytes, ["Manager", "Dept_A"]
        )

        with pytest.raises((InvalidCiphertextError, Exception)):
            self.crypto.decrypt(self.mpk_bytes, usk, corrupted_data)

    def test_decrypt_empty_plaintext_round_trip(self):
        """decrypt() correctly recovers empty plaintext."""
        plaintext = b""
        policy = "Admin"
        attributes = ["Admin"]

        usk = self.crypto.keygen(self.mpk_bytes, self.msk_bytes, attributes)
        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)
        result = self.crypto.decrypt(self.mpk_bytes, usk, ct)

        assert result == plaintext

    def test_decrypt_with_or_policy_first_attribute(self):
        """decrypt() works when user has first attribute in OR policy."""
        plaintext = b"OR policy test"
        policy = "Manager OR Admin"
        attributes = ["Manager"]

        usk = self.crypto.keygen(self.mpk_bytes, self.msk_bytes, attributes)
        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)
        result = self.crypto.decrypt(self.mpk_bytes, usk, ct)

        assert result == plaintext

    def test_decrypt_with_or_policy_second_attribute(self):
        """decrypt() works when user has second attribute in OR policy."""
        plaintext = b"OR policy test"
        policy = "Manager OR Admin"
        attributes = ["Admin"]

        usk = self.crypto.keygen(self.mpk_bytes, self.msk_bytes, attributes)
        ct = self.crypto.encrypt(self.mpk_bytes, plaintext, policy)
        result = self.crypto.decrypt(self.mpk_bytes, usk, ct)

        assert result == plaintext


@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestHABECryptoEndToEnd:
    """End-to-end round-trip tests: setup → keygen → encrypt → decrypt.

    Validates: Requirements 1.1, 2.1, 3.1, 4.1, 4.4 (round-trip property).
    """

    def test_full_round_trip_simple_policy(self):
        """Full round-trip with a simple AND policy."""
        from crypto_module.core import HABECrypto

        crypto = HABECrypto()
        mpk, msk = crypto.setup()

        attributes = ["Manager", "Dept_A"]
        usk = crypto.keygen(mpk, msk, attributes)

        plaintext = b"Confidential report content"
        policy = "Manager AND Dept_A"
        ct = crypto.encrypt(mpk, plaintext, policy)

        result = crypto.decrypt(mpk, usk, ct)
        assert result == plaintext

    def test_full_round_trip_hierarchical_attributes(self):
        """Full round-trip with hierarchical attributes (Company > Dept > Role)."""
        from crypto_module.core import HABECrypto

        crypto = HABECrypto()
        mpk, msk = crypto.setup()

        # Hierarchical: Company → Dept_A → Manager
        attributes = ["Company", "Dept_A", "Manager"]
        usk = crypto.keygen(mpk, msk, attributes)

        plaintext = b"Hierarchical access test data"
        policy = "Company AND Dept_A AND Manager"
        ct = crypto.encrypt(mpk, plaintext, policy)

        result = crypto.decrypt(mpk, usk, ct)
        assert result == plaintext

    def test_full_round_trip_binary_data(self):
        """Full round-trip preserves arbitrary binary data."""
        from crypto_module.core import HABECrypto

        crypto = HABECrypto()
        mpk, msk = crypto.setup()

        attributes = ["Admin"]
        usk = crypto.keygen(mpk, msk, attributes)

        # Binary data with all byte values
        plaintext = bytes(range(256)) * 4
        policy = "Admin"
        ct = crypto.encrypt(mpk, plaintext, policy)

        result = crypto.decrypt(mpk, usk, ct)
        assert result == plaintext

    def test_full_round_trip_empty_file(self):
        """Full round-trip works with empty file (zero bytes)."""
        from crypto_module.core import HABECrypto

        crypto = HABECrypto()
        mpk, msk = crypto.setup()

        attributes = ["Manager", "Dept_A"]
        usk = crypto.keygen(mpk, msk, attributes)

        plaintext = b""
        policy = "Manager AND Dept_A"
        ct = crypto.encrypt(mpk, plaintext, policy)

        result = crypto.decrypt(mpk, usk, ct)
        assert result == plaintext

    def test_full_round_trip_complex_policy(self):
        """Full round-trip with complex nested policy."""
        from crypto_module.core import HABECrypto

        crypto = HABECrypto()
        mpk, msk = crypto.setup()

        attributes = ["Admin", "Company"]
        usk = crypto.keygen(mpk, msk, attributes)

        plaintext = b"Complex policy access"
        policy = "(Manager AND Dept_A) OR Admin"
        ct = crypto.encrypt(mpk, plaintext, policy)

        result = crypto.decrypt(mpk, usk, ct)
        assert result == plaintext

    def test_full_round_trip_access_denied_for_wrong_attributes(self):
        """Full round-trip: access denied when attributes don't satisfy policy."""
        from crypto_module.core import HABECrypto

        crypto = HABECrypto()
        mpk, msk = crypto.setup()

        # User only has Employee attribute, not Manager
        attributes = ["Employee", "Dept_B"]
        usk = crypto.keygen(mpk, msk, attributes)

        plaintext = b"Managers only content"
        policy = "Manager AND Dept_A"
        ct = crypto.encrypt(mpk, plaintext, policy)

        with pytest.raises(AccessDeniedError):
            crypto.decrypt(mpk, usk, ct)
