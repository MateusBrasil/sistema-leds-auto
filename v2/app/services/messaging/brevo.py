"""Brevo (ex-Sendinblue) transactional email client."""

import httpx
from loguru import logger

_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


class BrevoClient:
    def __init__(self, api_key: str, sender_name: str, sender_email: str):
        self.api_key = api_key
        self.sender_name = sender_name
        self.sender_email = sender_email
        self.enabled = bool(api_key)

    async def send(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_body: str,
        reply_to: str | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """Returns (success, message_id, error)."""
        if not self.enabled:
            return False, None, "Brevo API key not configured"

        payload = {
            "sender": {"name": self.sender_name, "email": self.sender_email},
            "to": [{"email": to_email, "name": to_name}],
            "subject": subject,
            "htmlContent": html_body,
        }
        if reply_to:
            payload["replyTo"] = {"email": reply_to}

        headers = {"api-key": self.api_key, "Content-Type": "application/json", "accept": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(_ENDPOINT, headers=headers, json=payload)
                if r.status_code == 201:
                    data = r.json()
                    return True, data.get("messageId"), None
                return False, None, f"HTTP {r.status_code}: {r.text[:300]}"
        except Exception as e:
            logger.error("Brevo send failed: {}", e)
            return False, None, str(e)
