from datetime import timedelta

import pytest

from exceptions.security import TokenExpiredError, InvalidTokenError
from security.token_manager import JWTAuthManager


@pytest.fixture
def jwt_manager():
    return JWTAuthManager(
        secret_key_access="test-secret",
        algorithm="HS256",
    )


def test_create_and_decode_access_token_success(jwt_manager):
    token = jwt_manager.create_access_token({"sub": "1"})
    payload = jwt_manager.decode_access_token(token)

    assert payload["sub"] == "1"
    assert payload["exp"]


def test_decode_access_token_expired(jwt_manager):
    token = jwt_manager.create_access_token(
        {"sub": "1"}, expires_delta=timedelta(seconds=-1)
    )

    with pytest.raises(TokenExpiredError):
        jwt_manager.decode_access_token(token)


def test_decode_access_token_garbage(jwt_manager):
    with pytest.raises(InvalidTokenError):
        jwt_manager.decode_access_token("not-a_jwt")


def test_decode_access_token_wrong_secret_key(jwt_manager):
    other_manager = JWTAuthManager(
        secret_key_access="other-secret",
        algorithm="HS256",
    )

    other_token = other_manager.create_access_token({"sub": "1"})
    with pytest.raises(InvalidTokenError):
        jwt_manager.decode_access_token(other_token)
