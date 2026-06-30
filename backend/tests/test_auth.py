"""Tests for auth service: JWT tokens, password hashing, blacklist."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from app.services import (
    hash_password, verify_password, create_access_token,
    decode_access_token, blacklist_token, _blacklisted_tokens,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "test-password-123!"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_same_password_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt salts


class TestJWTToken:
    def test_create_and_decode(self):
        data = {"sub": "test@example.com", "user_id": 1}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 20

        payload = decode_access_token(token)
        assert payload["sub"] == "test@example.com"
        assert payload["user_id"] == 1
        assert "exp" in payload

    def test_blacklisted_token_rejected(self):
        token = create_access_token({"sub": "test@example.com", "user_id": 2})
        # Verify it works first
        payload = decode_access_token(token)
        assert payload["sub"] == "test@example.com"

        # Blacklist and verify rejection
        import asyncio
        asyncio.run(blacklist_token(token))
        assert token in _blacklisted_tokens

        with pytest.raises(Exception) as exc:
            decode_access_token(token)
        assert "revoked" in str(exc.value).lower() or "blacklisted" in str(exc.value).lower()

    def test_expired_token_rejected(self):
        with patch("app.services.settings") as mock_settings:
            mock_settings.secret_key = "test-secret"
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.access_token_expire_minutes = -1  # Expire immediately
            token = create_access_token({"sub": "expired@test.com"})
        with pytest.raises(Exception):
            decode_access_token(token)


class TestBlacklistPersistence:
    def test_blacklist_cleaned_between_tests(self):
        # Ensure each test starts with empty blacklist
        assert len(_blacklisted_tokens) == 0

    def test_multiple_tokens_blacklisted(self):
        t1 = create_access_token({"sub": "a@b.com"})
        t2 = create_access_token({"sub": "c@d.com"})
        import asyncio
        asyncio.run(blacklist_token(t1))
        asyncio.run(blacklist_token(t2))
        assert len(_blacklisted_tokens) == 2
        with pytest.raises(Exception):
            decode_access_token(t1)
        with pytest.raises(Exception):
            decode_access_token(t2)
