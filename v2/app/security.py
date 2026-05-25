"""Segurança: password hashing (argon2) + rate-limit login + verificação flexível.

Aceita 3 formatos de APP_PASSWORD no .env:
1. Argon2 hash (começa com `$argon2`)  → recomendado
2. SHA-256 hex prefixed (`sha256:<hex>`) → ok
3. Plaintext                              → compatibilidade (warning no startup)

Use `python -m app.security hash <pass>` para gerar hash argon2.
"""

import hashlib
import secrets
import sys
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from loguru import logger


_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Cria hash argon2id (recomendado pelo OWASP)."""
    return _hasher.hash(plain)


def verify_password(plain: str, stored: str) -> bool:
    """Verifica password contra hash. Suporta argon2, sha256 e plaintext."""
    if not stored:
        return False

    # Argon2
    if stored.startswith("$argon2"):
        try:
            _hasher.verify(stored, plain)
            return True
        except VerifyMismatchError:
            return False
        except Exception as e:
            logger.warning("Argon2 verify error: {}", e)
            return False

    # SHA-256
    if stored.startswith("sha256:"):
        expected = stored.replace("sha256:", "", 1)
        actual = hashlib.sha256(plain.encode()).hexdigest()
        return secrets.compare_digest(expected, actual)

    # Plaintext (legacy — deve ser migrado)
    return secrets.compare_digest(plain, stored)


# ───────────────────────── Rate limit ─────────────────────────

class RateLimiter:
    """In-memory sliding-window rate limiter.

    Lifecycle limita-se ao processo. Para escala horizontal usar Redis.
    Para single-user/single-process é suficiente.
    """
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        """Devolve (allowed, seconds_until_reset)."""
        now = time.time()
        bucket = self._buckets[key]
        # Drop expired
        while bucket and bucket[0] < now - self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_attempts:
            wait = int(self.window_seconds - (now - bucket[0]))
            return False, max(1, wait)
        bucket.append(now)
        return True, 0

    def reset(self, key: str) -> None:
        self._buckets.pop(key, None)


# Limiters globais
login_limiter = RateLimiter(max_attempts=8, window_seconds=15 * 60)  # 8 tentativas / 15 min
webhook_limiter = RateLimiter(max_attempts=300, window_seconds=60)  # 300/min


def client_ip(request) -> str:
    """Tenta apanhar IP real (atrás de proxy/Cloudflare)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# CLI: gera hash argon2 de uma password
if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "hash":
        print(hash_password(sys.argv[2]))
    else:
        print("Uso: python -m app.security hash <password>")
