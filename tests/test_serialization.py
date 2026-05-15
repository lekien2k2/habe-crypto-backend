"""Unit tests for crypto_module.serialization."""

import base64
import json
import pytest

try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

try:
    from charm.core.engine.util import objectToBytes, bytesToObject
    from charm.toolbox.pairinggroup import PairingGroup
    HAS_CHARM = True
except ImportError:
    HAS_CHARM = False

from crypto_module.exceptions import CryptoError, InvalidCiphertextError


@pytest.mark.skipif(not HAS_MSGPACK, reason="msgpack not installed")
class TestCiphertextBundleSerialization:
    """Tests for serialize_ciphertext_bundle and deserialize_ciphertext_bundle."""

    def setup_method(self):
        from crypto_module.serialization import (
            serialize_ciphertext_bundle,
            deserialize_ciphertext_bundle,
        )
        self.serialize = serialize_ciphertext_bundle
        self.deserialize = deserialize_ciphertext_bundle

    def test_round_trip(self):
        """Serializing then deserializing returns original data."""
        abe_ct = b"fake_abe_ciphertext_data"
        aes_ct = b"fake_aes_encrypted_data"
        iv = b"\x00" * 16
        hmac_val = b"\xab" * 32
        policy = "Manager AND Dept_A"
        metadata = {
            "original_filename": "report.pdf",
            "original_size": 1048576,
            "content_type": "application/pdf",
            "encrypted_at": "2024-01-15T10:30:00Z",
        }

        bundle_bytes = self.serialize(abe_ct, aes_ct, iv, hmac_val, policy, metadata)
        result = self.deserialize(bundle_bytes)

        assert result["version"] == 1
        assert result["scheme"] == "CP-ABE-BSW07-HYBRID"
        assert result["access_policy"] == policy
        assert result["abe_ciphertext"] == abe_ct
        assert result["aes_ciphertext"] == aes_ct
        assert result["aes_iv"] == iv
        assert result["hmac"] == hmac_val
        assert result["metadata"] == metadata

    def test_empty_data(self):
        """Handles empty binary fields correctly."""
        bundle_bytes = self.serialize(b"", b"", b"", b"", "", {})
        result = self.deserialize(bundle_bytes)

        assert result["abe_ciphertext"] == b""
        assert result["aes_ciphertext"] == b""
        assert result["aes_iv"] == b""
        assert result["hmac"] == b""
        assert result["access_policy"] == ""
        assert result["metadata"] == {}

    def test_invalid_bundle_bytes(self):
        """Raises InvalidCiphertextError for corrupted data."""
        with pytest.raises(InvalidCiphertextError):
            self.deserialize(b"not valid msgpack data!!")

    def test_missing_required_field(self):
        """Raises InvalidCiphertextError when required fields are missing."""
        incomplete = msgpack.packb({"version": 1, "scheme": "test"}, use_bin_type=True)
        with pytest.raises(InvalidCiphertextError):
            self.deserialize(incomplete)

    def test_non_dict_bundle(self):
        """Raises InvalidCiphertextError when bundle is not a dict."""
        not_a_dict = msgpack.packb([1, 2, 3], use_bin_type=True)
        with pytest.raises(InvalidCiphertextError):
            self.deserialize(not_a_dict)


@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestKeySerialization:
    """Tests for serialize_key and deserialize_key (requires charm-crypto)."""

    def setup_method(self):
        from crypto_module.serialization import serialize_key, deserialize_key
        self.serialize = serialize_key
        self.deserialize = deserialize_key
        self.group = PairingGroup("SS512")

    def test_key_round_trip_with_random_element(self):
        """Serializing then deserializing a group element returns equivalent object."""
        # Create a simple key-like object (a random group element)
        element = self.group.random()
        key_obj = {"key": element}

        serialized = self.serialize(key_obj, self.group)
        deserialized = self.deserialize(serialized, self.group)

        assert deserialized["key"] == key_obj["key"]

    def test_key_envelope_format(self):
        """Serialized key has correct JSON envelope structure."""
        element = self.group.random()
        key_obj = {"key": element}

        serialized = self.serialize(key_obj, self.group)
        envelope = json.loads(serialized.decode("utf-8"))

        assert envelope["scheme"] == "CP-ABE-BSW07"
        assert "group" in envelope
        assert "key_data" in envelope
        # key_data should be valid base64
        base64.b64decode(envelope["key_data"])

    def test_invalid_key_bytes(self):
        """Raises CryptoError for invalid key bytes."""
        with pytest.raises(CryptoError):
            self.deserialize(b"not valid json", self.group)

    def test_missing_envelope_field(self):
        """Raises CryptoError when envelope is missing required fields."""
        incomplete = json.dumps({"scheme": "test"}).encode("utf-8")
        with pytest.raises(CryptoError):
            self.deserialize(incomplete, self.group)
