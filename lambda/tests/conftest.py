import pytest
from nacl.signing import SigningKey


@pytest.fixture
def signing_key() -> SigningKey:
    return SigningKey.generate()
