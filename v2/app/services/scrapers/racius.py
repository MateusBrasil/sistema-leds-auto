"""Scraper racius.com — registo público de empresas PT com NIF/CAE/gerentes.

Tem mais info "qualificada" (NIF, capital social, gerentes) que páginas amarelas.
Usa-se via search query → lista → detalhe.
"""

import asyncio
import re
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from .base import LeadCandidate


_BASE = "https://www.racius.com"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


class RaciusScraper:
    name = "racius"

    def __init__(self):
        pass

    @property
    def enabled(self) -> bool:
        return True

    async def search(self, niche: str, city: str, limit: int = 15) -> list[LeadCandidate]:
        # Combinar termo + localidade no search query do racius
        q = f"{niche} {city}".strip()
        url = f"{_BASE}/search.html?q={quote(q)}"

        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "pt-PT,pt;q=0.9"}
        candidates: list[LeadCandidate] = []

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    logger.warning("Racius {} → HTTP {}", url, r.status_code)
                    return []
                soup = BeautifulSoup(r.text, "html.parser")

                # Lista de resultados — racius usa class "result" ou similar
                results = soup.select("a[href*='/empresa/']") or soup.select("[class*=result]")

                for link in results[: limit * 2]:
                    name = link.get_text(" ", strip=True)
                    if not name or len(name) < 3:
                        continue
                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = _BASE + href

                    candidates.append(LeadCandidate(
                        source="racius",
                        source_id=href,
                        name=name,
                        website=None,  # preenchido em opt-in via detalhe
                        city=city,
                        niche=niche,
                        extra={"racius_url": href},
                    ))
                    if len(candidates) >= limit:
                        break

        except Exception as e:
            logger.warning("Racius falhou para '{}' em '{}': {}", niche, city, e)
            return []

        await asyncio.sleep(0.5)
        return candidates
