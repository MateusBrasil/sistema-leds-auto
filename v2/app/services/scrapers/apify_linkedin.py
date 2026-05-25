"""LinkedIn via Apify actor (sync mode — runs and waits for result)."""

import httpx
from loguru import logger

from .base import LeadCandidate

_ACTOR_ID = "curious_coder~linkedin-profile-scraper"
_RUN_SYNC = f"https://api.apify.com/v2/acts/{_ACTOR_ID}/run-sync-get-dataset-items"


class ApifyLinkedInScraper:
    name = "linkedin"

    def __init__(self, token: str):
        if not token:
            raise ValueError("APIFY_API_TOKEN missing")
        self.token = token

    async def search(self, niche: str, city: str, limit: int = 20) -> list[LeadCandidate]:
        payload = {
            "searchQueries": [f"{niche} {city}"],
            "maxResults": limit,
            "proxyConfiguration": {"useApifyProxy": True},
        }
        params = {"token": self.token, "format": "json"}

        async with httpx.AsyncClient(timeout=180) as client:
            try:
                resp = await client.post(_RUN_SYNC, params=params, json=payload)
                if resp.status_code == 401:
                    logger.warning("Apify LinkedIn: token inválido (401) — fonte desactivada para este run")
                    return []
                if resp.status_code != 200:
                    logger.warning("Apify LinkedIn HTTP {}: {}", resp.status_code, resp.text[:160])
                    return []
                items = resp.json()
            except Exception as e:
                logger.error("Apify LinkedIn failed: {}", e)
                return []

        return [
            LeadCandidate(
                source="linkedin",
                source_id=item.get("profileUrl"),
                name=f"{item.get('firstName', '')} {item.get('lastName', '')}".strip(),
                website=item.get("companyWebsite") or item.get("currentCompanyUrl"),
                phone=item.get("phoneNumber"),
                email=item.get("email"),
                address=item.get("location"),
                city=city,
                niche=niche,
                extra={"headline": item.get("headline"), "company": item.get("currentCompany")},
            )
            for item in items
        ]
