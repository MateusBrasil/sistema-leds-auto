"""Instagram via Apify hashtag scraper."""

import httpx
from loguru import logger

from .base import LeadCandidate

_ACTOR_ID = "apify~instagram-hashtag-scraper"
_RUN_SYNC = f"https://api.apify.com/v2/acts/{_ACTOR_ID}/run-sync-get-dataset-items"


class ApifyInstagramScraper:
    name = "instagram"

    def __init__(self, token: str):
        if not token:
            raise ValueError("APIFY_API_TOKEN missing")
        self.token = token

    async def search(self, niche: str, city: str, limit: int = 30) -> list[LeadCandidate]:
        # Use the niche itself as hashtag (without spaces)
        hashtag = niche.replace(" ", "").replace("#", "").lower()
        payload = {
            "hashtags": [hashtag],
            "resultsLimit": limit,
            "proxyConfiguration": {"useApifyProxy": True},
        }
        params = {"token": self.token, "format": "json"}

        async with httpx.AsyncClient(timeout=180) as client:
            try:
                resp = await client.post(_RUN_SYNC, params=params, json=payload)
                if resp.status_code == 401:
                    logger.warning("Apify Instagram: token inválido (401) — fonte desactivada para este run")
                    return []
                if resp.status_code != 200:
                    logger.warning("Apify Instagram HTTP {}: {}", resp.status_code, resp.text[:160])
                    return []
                items = resp.json()
            except Exception as e:
                logger.error("Apify Instagram failed: {}", e)
                return []

        return [
            LeadCandidate(
                source="instagram",
                source_id=item.get("ownerUsername") or item.get("url"),
                name=item.get("ownerFullName") or item.get("ownerUsername", ""),
                website=item.get("ownerExternalUrl"),
                city=city,
                niche=niche,
                extra={"post_url": item.get("url"), "likes": item.get("likesCount")},
            )
            for item in items
        ]
