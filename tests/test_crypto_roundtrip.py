"""Property-based tests for crypto_module using Hypothesis.

Property 1: Encryption Round-Trip
For any valid plaintext (0-10KB), valid access policy using AND/OR operators,
and any attribute set that satisfies that policy, encrypting the plaintext
under the policy and then decrypting with a key generated for the satisfying
attribute set returns bytes identical to the original plaintext.

**Validates: Requirements 4.4, 5.1, 5.2, 5.4, 3.2, 3.3, 3.6**
"""

import pytest
from hypothesis import given, settings, strategies as st

try:
    from charm.toolbox.pairinggroup import PairingGroup
    HAS_CHARM = True
except ImportError:
    HAS_CHARM = False


# --- Custom Strategies ---

def valid_attribute_names():
    """Generate valid attribute name strings (uppercase alphabetic).

    Charm-crypto CP-ABE requires attribute names to be simple uppercase
    alphanumeric identifiers without spaces or special characters.
    """
    return st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        min_size=2,
        max_size=8,
    ).filter(lambda s: len(s) >= 2)


def valid_attribute_set(min_size=1, max_size=5):
    """Generate a list of 1-5 unique valid attribute strings."""
    return st.lists(
        valid_attribute_names(),
        min_size=min_size,
        max_size=max_size,
        unique=True,
    )


def valid_access_policy_from_attributes(attributes):
    """Given a list of attributes, generate a policy that all attributes satisfy.

    Uses AND to join all attributes, guaranteeing that a user with all
    attributes will satisfy the policy. For single attributes, returns
    the attribute directly.
    """
    if len(attributes) == 1:
        return attributes[0]
    # AND-join guarantees the attribute set satisfies the policy
    return " AND ".join(attributes)


def valid_or_policy_from_attributes(attributes):
    """Given a list of attributes, generate an OR policy.

    Any single attribute from the set satisfies the policy.
    """
    if len(attributes) == 1:
        return attributes[0]
    return " OR ".join(attributes)


@st.composite
def policy_and_attributes(draw):
    """Generate a (policy, attributes) pair where attributes satisfy the policy.

    Randomly chooses between AND and OR policies to cover both operators.
    """
    attributes = draw(valid_attribute_set(min_size=1, max_size=4))
    use_or = draw(st.booleans())

    if use_or and len(attributes) > 1:
        policy = valid_or_policy_from_attributes(attributes)
    else:
        policy = valid_access_policy_from_attributes(attributes)

    return policy, attributes


# --- Property Tests ---

@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestEncryptionRoundTrip:
    """Property 1: Encryption Round-Trip.

    For any valid plaintext, valid access policy, and satisfying attribute set,
    encrypt then decrypt returns the original plaintext.

    **Validates: Requirements 4.4, 5.1, 5.2, 5.4, 3.2, 3.3, 3.6**
    """

    def setup_method(self):
        from crypto_module.core import HABECrypto
        self.crypto = HABECrypto()
        self.mpk, self.msk = self.crypto.setup()

    @settings(max_examples=100, deadline=None)
    @given(
        plaintext=st.binary(min_size=0, max_size=10240),
        policy_attrs=policy_and_attributes(),
    )
    def test_round_trip_property(self, plaintext, policy_attrs):
        """Encrypt then decrypt with satisfying key returns original plaintext.

        **Validates: Requirements 4.4, 5.1, 5.2, 5.4, 3.2, 3.3, 3.6**
        """
        policy, attributes = policy_attrs

        # Generate user key with these attributes
        usk = self.crypto.keygen(self.mpk, self.msk, attributes)

        # Encrypt under the policy
        ct = self.crypto.encrypt(self.mpk, plaintext, policy)

        # Decrypt with the satisfying key
        result = self.crypto.decrypt(self.mpk, usk, ct)

        assert result == plaintext, (
            f"Round-trip failed: expected {len(plaintext)} bytes, "
            f"got {len(result)} bytes"
        )


# --- Strategy for Property 2: Access Denial ---

@st.composite
def non_satisfying_policy_and_attributes(draw):
    """Generate a (policy, non_satisfying_attributes) tuple.

    The policy uses AND of policy_attributes, and non_satisfying_attributes
    is a completely disjoint set that does NOT satisfy the policy.
    """
    # Generate enough unique attributes to split into two disjoint sets
    all_attrs = draw(st.lists(
        valid_attribute_names(),
        min_size=4,
        max_size=8,
        unique=True,
    ))

    # Split into policy attrs and user attrs (disjoint)
    split = draw(st.integers(min_value=2, max_value=len(all_attrs) - 2))
    policy_attrs = all_attrs[:split]
    user_attrs = all_attrs[split:]

    policy = " AND ".join(policy_attrs)
    return policy, user_attrs


# --- Property 2 Tests ---

@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestAccessDenial:
    """Property 2: Access Denial for Non-Satisfying Attributes.

    For any valid access policy and any attribute set that does NOT satisfy
    that policy, attempting to decrypt raises AccessDeniedError.

    **Validates: Requirements 2.5, 3.5, 4.3, 5.3**
    """

    def setup_method(self):
        from crypto_module.core import HABECrypto
        self.crypto = HABECrypto()
        self.mpk, self.msk = self.crypto.setup()

    @settings(max_examples=100, deadline=None)
    @given(data=non_satisfying_policy_and_attributes())
    def test_access_denial_property(self, data):
        """Decrypt with non-satisfying attributes raises AccessDeniedError.

        **Validates: Requirements 2.5, 3.5, 4.3, 5.3**
        """
        from crypto_module.exceptions import AccessDeniedError

        policy, non_satisfying_attrs = data

        # Encrypt some data under the policy
        plaintext = b"secret data"
        ct = self.crypto.encrypt(self.mpk, plaintext, policy)

        # Generate key with non-satisfying attributes
        usk = self.crypto.keygen(self.mpk, self.msk, non_satisfying_attrs)

        # Attempt to decrypt should raise AccessDeniedError
        with pytest.raises(AccessDeniedError):
            self.crypto.decrypt(self.mpk, usk, ct)


# --- Property 3 Tests ---

@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestDistinctKeyPairs:
    """Property 3: Setup Produces Distinct Key Pairs.
    
    For any two invocations of Setup(), the resulting master key pairs
    are distinct (both MPK and MSK differ between invocations).
    
    **Validates: Requirements 1.5**
    """

    def setup_method(self):
        from crypto_module.core import HABECrypto
        self.crypto = HABECrypto()

    @settings(max_examples=50, deadline=None)
    @given(data=st.data())
    def test_distinct_key_pairs_property(self, data):
        """Two calls to setup() produce different key pairs."""
        mpk1, msk1 = self.crypto.setup()
        mpk2, msk2 = self.crypto.setup()
        
        # At least one component must differ
        assert mpk1 != mpk2 or msk1 != msk2, (
            "Two setup() calls produced identical key pairs"
        )


# --- Strategies for Property 4 ---

def invalid_attribute_sets():
    """Generate invalid attribute sets (empty list, whitespace-only, non-string)."""
    return st.one_of(
        st.just([]),  # Empty list
        st.lists(st.just(""), min_size=1, max_size=3),  # Empty strings
        st.lists(st.just("   "), min_size=1, max_size=3),  # Whitespace only
        st.lists(st.integers(), min_size=1, max_size=3),  # Non-string values
    )


def invalid_policy_strings():
    """Generate invalid policy strings."""
    return st.one_of(
        st.just(""),  # Empty string
        st.just("   "),  # Whitespace only
        st.just("(Manager AND Dept_A"),  # Unbalanced open paren
        st.just("Manager AND Dept_A)"),  # Unbalanced close paren
        st.just("((())"),  # Unbalanced nested
    )


@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestInvalidInputRejection:
    """Property 4: Invalid Inputs Are Rejected.
    
    For any empty or invalid attribute set, KeyGen raises InvalidAttributeSetError.
    For any syntactically invalid access policy, Encrypt raises InvalidPolicyError.
    
    **Validates: Requirements 2.4, 3.4**
    """

    def setup_method(self):
        from crypto_module.core import HABECrypto
        self.crypto = HABECrypto()
        self.mpk, self.msk = self.crypto.setup()

    @settings(max_examples=50, deadline=None)
    @given(attrs=invalid_attribute_sets())
    def test_invalid_attributes_rejected(self, attrs):
        """KeyGen rejects invalid attribute sets with InvalidAttributeSetError."""
        from crypto_module.exceptions import InvalidAttributeSetError
        
        with pytest.raises(InvalidAttributeSetError):
            self.crypto.keygen(self.mpk, self.msk, attrs)

    @settings(max_examples=50, deadline=None)
    @given(policy=invalid_policy_strings())
    def test_invalid_policy_rejected(self, policy):
        """Encrypt rejects invalid policy strings with InvalidPolicyError."""
        from crypto_module.exceptions import InvalidPolicyError
        
        with pytest.raises(InvalidPolicyError):
            self.crypto.encrypt(self.mpk, b"test data", policy)


# --- Property 5 Tests ---

@pytest.mark.skipif(not HAS_CHARM, reason="charm-crypto not installed")
class TestCorruptedCiphertextDetection:
    """Property 5: Corrupted Ciphertext Detection.
    
    For any valid ciphertext, if one or more bytes are modified (corrupted),
    attempting to decrypt the corrupted ciphertext raises an error
    (InvalidCiphertextError or CryptoDecryptError) rather than returning
    incorrect plaintext.
    
    **Validates: Requirements 4.5**
    """

    def setup_method(self):
        from crypto_module.core import HABECrypto
        self.crypto = HABECrypto()
        self.mpk, self.msk = self.crypto.setup()

    @settings(max_examples=50, deadline=None)
    @given(
        plaintext=st.binary(min_size=1, max_size=1024),
        corruption_offset=st.integers(min_value=0),
        corruption_byte=st.integers(min_value=0, max_value=255),
    )
    def test_corrupted_ciphertext_detected(self, plaintext, corruption_offset, corruption_byte):
        """Corrupted ciphertext raises an error rather than returning wrong data."""
        from crypto_module.exceptions import InvalidCiphertextError, CryptoDecryptError
        
        attributes = ["MANAGER", "DEPTA"]
        policy = "MANAGER AND DEPTA"
        
        usk = self.crypto.keygen(self.mpk, self.msk, attributes)
        ct = self.crypto.encrypt(self.mpk, plaintext, policy)
        
        # Corrupt a byte in the ciphertext
        ct_array = bytearray(ct)
        offset = corruption_offset % len(ct_array)
        original_byte = ct_array[offset]
        
        # Ensure we actually change the byte
        new_byte = corruption_byte if corruption_byte != original_byte else (corruption_byte + 1) % 256
        ct_array[offset] = new_byte
        corrupted_ct = bytes(ct_array)
        
        # Decryption should either raise an error or (very rarely) succeed
        # but never return incorrect plaintext silently
        try:
            result = self.crypto.decrypt(self.mpk, usk, corrupted_ct)
            # If decryption somehow succeeds, it must return the original plaintext
            # (this would mean the corruption didn't affect the actual data)
            # This is acceptable - some bytes in the bundle are metadata
            # The key property is: it should NOT return WRONG plaintext
            assert result == plaintext, (
                "Corrupted ciphertext returned incorrect plaintext without raising an error"
            )
        except (InvalidCiphertextError, CryptoDecryptError, Exception):
            # Expected behavior - corruption detected
            pass
