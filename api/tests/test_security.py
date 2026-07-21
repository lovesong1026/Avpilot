"""Security utility tests that do not require external services."""

import uuid

import pytest

from app.shared.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_access_token_round_trip() -> None:
    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id)

    assert decode_access_token(token) == user_id


def test_invalid_access_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid access token"):
        decode_access_token("not-a-token")
