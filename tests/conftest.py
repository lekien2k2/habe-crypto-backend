import pytest

try:
    from charm.toolbox.pairinggroup import PairingGroup
    HAS_CHARM = True
except ImportError:
    HAS_CHARM = False


@pytest.fixture
def crypto_instance():
    """Provide an initialized HABECrypto instance."""
    pytest.importorskip("charm.toolbox.pairinggroup")
    from crypto_module.core import HABECrypto
    return HABECrypto()


@pytest.fixture
def master_keys(crypto_instance):
    """Provide a MPK/MSK pair from setup()."""
    mpk, msk = crypto_instance.setup()
    return mpk, msk


@pytest.fixture
def sample_attributes():
    """Provide sample attribute sets for testing."""
    return {
        "manager": ["Manager", "Dept_A"],
        "employee": ["Employee", "Dept_A"],
        "admin": ["Admin", "Company", "Dept_A", "Manager"],
        "single": ["Admin"],
        "hierarchical": ["Company", "Dept_A", "Manager"],
    }


@pytest.fixture
def sample_policies():
    """Provide sample access policies for testing."""
    return {
        "simple_and": "Manager AND Dept_A",
        "simple_or": "Manager OR Employee",
        "complex": "(Manager AND Dept_A) OR Admin",
        "single_attr": "Admin",
        "nested": "((Manager OR Admin) AND Dept_A)",
    }
