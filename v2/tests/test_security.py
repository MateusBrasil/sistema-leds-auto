"""Testes de segurança — password hashing + rate limiter."""

import time

from app.security import hash_password, verify_password, RateLimiter


class TestPasswordHash:
    def test_argon2_roundtrip(self):
        h = hash_password("hello123")
        assert h.startswith("$argon2")
        assert verify_password("hello123", h) is True
        assert verify_password("hello1234", h) is False

    def test_sha256_legacy_format(self):
        import hashlib
        stored = "sha256:" + hashlib.sha256(b"secret").hexdigest()
        assert verify_password("secret", stored) is True
        assert verify_password("wrong", stored) is False

    def test_plaintext_compat(self):
        # Compatibilidade com .env não-migrado
        assert verify_password("admin", "admin") is True
        assert verify_password("wrong", "admin") is False

    def test_empty_stored(self):
        assert verify_password("anything", "") is False


class TestRateLimiter:
    def test_allows_below_limit(self):
        rl = RateLimiter(max_attempts=3, window_seconds=60)
        for _ in range(3):
            allowed, _ = rl.check("ip1")
            assert allowed

    def test_blocks_at_limit(self):
        rl = RateLimiter(max_attempts=2, window_seconds=60)
        rl.check("ip1")
        rl.check("ip1")
        allowed, wait = rl.check("ip1")
        assert not allowed
        assert wait > 0

    def test_different_keys_independent(self):
        rl = RateLimiter(max_attempts=1, window_seconds=60)
        a, _ = rl.check("ip1")
        b, _ = rl.check("ip2")
        assert a and b

    def test_reset_clears(self):
        rl = RateLimiter(max_attempts=1, window_seconds=60)
        rl.check("ip1")
        rl.reset("ip1")
        allowed, _ = rl.check("ip1")
        assert allowed
