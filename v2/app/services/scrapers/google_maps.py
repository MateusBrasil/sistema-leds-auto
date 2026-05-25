"""Google Maps Places API scraper (Text Search + Place Details)."""

import asyncio
from typing import Optional

import httpx
from loguru import logger

from .base import LeadCandidate

_TEXTSEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"
_NEXT_TOKEN_DELAY = 2.1  # Google requires ~2s before next_page_token is valid


class GoogleMapsScraper:
    name = "google_maps"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY missing")
        self.api_key = api_key

    async def search(self, niche: str, city: str, limit: int = 60) -> list[LeadCandidate]:
        query = f"{niche} {city}".strip()
        results: list[LeadCandidate] = []

        async with httpx.AsyncClient(timeout=20) as client:
            next_token: Optional[str] = None
            for _ in range(3):  # Places returns up to 60 (3 pages of 20)
                params = {"key": self.api_key, "language": "pt"}
                if next_token:
                    params["pagetoken"] = next_token
                    await asyncio.sleep(_NEXT_TOKEN_DELAY)
                else:
                    params["query"] = query

                resp = await client.get(_TEXTSEARCH, params=params)
                data = resp.json()

                if data.get("status") not in ("OK", "ZERO_RESULTS"):
                    logger.warning("Places API status={} msg={}", data.get("status"), data.get("error_message"))
                    break

                for place in data.get("results", []):
                    details = await self._details(client, place["place_id"])
                    results.append(self._to_candidate(place, details, niche, city))
                    if len(results) >= limit:
                        return results

                next_token = data.get("next_page_token")
                if not next_token:
                    break

        return results

    async def _details(self, client: httpx.AsyncClient, place_id: str) -> dict:
        params = {
            "place_id": place_id,
            "fields": "formatted_phone_number,international_phone_number,website,formatted_address",
            "key": self.api_key,
            "language": "pt",
        }
        try:
            resp = await client.get(_DETAILS, params=params)
            return resp.json().get("result", {}) or {}
        except Exception as e:
            logger.warning("Place details failed for {}: {}", place_id, e)
            return {}

    @staticmethod
    def _to_candidate(place: dict, details: dict, niche: str, city: str) -> LeadCandidate:
        phone = details.get("international_phone_number") or details.get("formatted_phone_number")
        return LeadCandidate(
            source="google_maps",
            source_id=place.get("place_id"),
            name=place.get("name", ""),
            website=details.get("website"),
            phone=phone,
            address=place.get("formatted_address") or details.get("formatted_address"),
            city=city,
            niche=niche,
            rating=place.get("rating"),
            reviews_count=place.get("user_ratings_total"),
            extra={"types": place.get("types", [])},
        )
