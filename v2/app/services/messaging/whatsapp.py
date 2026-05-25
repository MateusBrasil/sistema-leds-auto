"""WhatsApp client — suporta Evolution (self-hosted) e Z-API (cloud trial)."""

import httpx
from loguru import logger


class WhatsAppClient:
    def __init__(
        self,
        provider: str,
        # evolution
        evolution_base_url: str = "",
        evolution_api_key: str = "",
        evolution_instance: str = "",
        # zapi
        zapi_instance_id: str = "",
        zapi_token: str = "",
        zapi_client_token: str = "",
    ):
        self.provider = (provider or "evolution").lower()
        self.evolution_base_url = evolution_base_url.rstrip("/")
        self.evolution_api_key = evolution_api_key
        self.evolution_instance = evolution_instance
        self.zapi_instance_id = zapi_instance_id
        self.zapi_token = zapi_token
        self.zapi_client_token = zapi_client_token

    @property
    def enabled(self) -> bool:
        if self.provider == "evolution":
            return bool(self.evolution_base_url and self.evolution_api_key and self.evolution_instance)
        if self.provider == "zapi":
            return bool(self.zapi_instance_id and self.zapi_token)
        return False

    async def send_text(self, phone_e164: str, text: str) -> tuple[bool, str | None, str | None]:
        if not self.enabled:
            return False, None, f"WhatsApp provider '{self.provider}' not configured"

        if self.provider == "evolution":
            return await self._send_evolution(phone_e164, text)
        return await self._send_zapi(phone_e164, text)

    async def _send_evolution(self, phone: str, text: str):
        # Evolution wants number without '+', e.g. '351912345678'
        number = phone.lstrip("+")
        url = f"{self.evolution_base_url}/message/sendText/{self.evolution_instance}"
        headers = {"apikey": self.evolution_api_key, "Content-Type": "application/json"}
        body = {"number": number, "text": text}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(url, headers=headers, json=body)
                if 200 <= r.status_code < 300:
                    data = r.json() if r.text else {}
                    return True, str(data.get("key", {}).get("id") or data.get("id") or ""), None
                return False, None, f"HTTP {r.status_code}: {r.text[:300]}"
        except Exception as e:
            logger.error("Evolution send failed: {}", e)
            return False, None, str(e)

    async def _send_zapi(self, phone: str, text: str):
        number = phone.lstrip("+")
        url = f"https://api.z-api.io/instances/{self.zapi_instance_id}/token/{self.zapi_token}/send-text"
        headers = {"Content-Type": "application/json"}
        if self.zapi_client_token:
            headers["client-token"] = self.zapi_client_token
        body = {"phone": number, "message": text}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(url, headers=headers, json=body)
                if 200 <= r.status_code < 300:
                    data = r.json() if r.text else {}
                    return True, data.get("messageId") or data.get("id"), None
                return False, None, f"HTTP {r.status_code}: {r.text[:300]}"
        except Exception as e:
            logger.error("Z-API send failed: {}", e)
            return False, None, str(e)
