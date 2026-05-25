"""Hunter.io enrichment — domain search + email finder."""

import httpx
from loguru import logger

from ...utils import extract_domain


class HunterClient:
    BASE = "https://api.hunter.io/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.enabled = bool(api_key)

    async def find_email(self, name: str | None, website: str | None) -> str | None:
        if not self.enabled or not website:
            return None
        domain = extract_domain(website)
        if not domain:
            return None

        async with httpx.AsyncClient(timeout=15) as client:
            email = await self._domain_search(client, domain)
            if email:
                return email
            if name:
                email = await self._email_finder(client, domain, name)
            return email

    async def _domain_search(self, client: httpx.AsyncClient, domain: str) -> str | None:
        try:
            r = await client.get(
                f"{self.BASE}/domain-search",
                params={"domain": domain, "api_key": self.api_key, "limit": 1},
            )
            data = r.json().get("data", {})
            emails = data.get("emails") or []
            return emails[0].get("value") if emails else None
        except Exception as e:
            logger.warning("Hunter domain-search failed for {}: {}", domain, e)
            return None

    async def _email_finder(self, client: httpx.AsyncClient, domain: str, full_name: str) -> str | None:
        parts = full_name.strip().split()
        if not parts:
            return None
        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""
        try:
            r = await client.get(
                f"{self.BASE}/email-finder",
                params={
                    "domain": domain,
                    "first_name": first,
                    "last_name": last,
                    "api_key": self.api_key,
                },
            )
            data = r.json().get("data", {})
            return data.get("email") or None
        except Exception as e:
            logger.warning("Hunter email-finder failed for {}: {}", domain, e)
            return None
