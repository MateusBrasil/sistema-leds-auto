"""Free email validation: syntax + MX record check.
Optionally calls ZeroBounce if api_key provided."""

from email_validator import validate_email, EmailNotValidError
import httpx
from loguru import logger


class EmailValidator:
    def __init__(self, zerobounce_key: str = ""):
        self.zerobounce_key = zerobounce_key

    async def is_valid(self, email: str | None) -> bool:
        if not email:
            return False
        try:
            validate_email(email, check_deliverability=True)
        except EmailNotValidError:
            return False

        if self.zerobounce_key:
            return await self._zerobounce_check(email)
        return True

    async def _zerobounce_check(self, email: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.zerobounce.net/v2/validate",
                    params={"api_key": self.zerobounce_key, "email": email},
                )
                data = r.json()
                return data.get("status") in ("valid", "catch-all")
        except Exception as e:
            logger.warning("ZeroBounce failed for {}: {}", email, e)
            return True  # falha segura: assume válido para não bloquear envio
