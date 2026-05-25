"""Scraper Páginas Amarelas PT — directo, sem Apify.

Scraping é "best-effort" — se o site mudar o HTML, este scraper degrada
graciosamente e devolve [] sem partir o pipeline.
"""

import asyncio
import re
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from .base import LeadCandidate


_BASE = "https://www.pai.pt"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


class PaginasAmarelasScraper:
    name = "paginas_amarelas"

    def __init__(self):
        pass

    @property
    def enabled(self) -> bool:
        return True  # sem chave necessária

    async def search(self, niche: str, city: str, limit: int = 30) -> list[LeadCandidate]:
        url = f"{_BASE}/{quote(niche)}/{quote(city)}"
        candidates: list[LeadCandidate] = []

        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "pt-PT,pt;q=0.9"}
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    logger.warning("PaginasAmarelas {} → HTTP {}", url, r.status_code)
                    return []
                soup = BeautifulSoup(r.text, "html.parser")

                # Procura blocos de resultado — vários selectors tentativos para resistir a HTML changes
                items = soup.select("[class*=result], [class*=listing], [class*=card]") or soup.find_all("article")

                for item in items[: limit * 2]:  # over-collect, filter depois
                    name = _first_text(item, ["h2", "h3", "[class*=name]", "[class*=title]"])
                    if not name or len(name) < 3:
                        continue

                    phone = _extract_phone(item)
                    address = _first_text(item, ["[class*=address]", "[class*=morada]", "address"])
                    website = _extract_website(item)

                    candidates.append(LeadCandidate(
                        source="paginas_amarelas",
                        source_id=f"pa:{name[:60]}",
                        name=name,
                        phone=phone,
                        address=address,
                        website=website,
                        city=city,
                        niche=niche,
                    ))
                    if len(candidates) >= limit:
                        break
        except Exception as e:
            logger.warning("PaginasAmarelas falhou para '{}' em '{}': {}", niche, city, e)
            return []

        await asyncio.sleep(0.5)  # courtesy delay
        return candidates


# ───────────────────────── Helpers ─────────────────────────

_PHONE_RE = re.compile(r"(\+?351)?\s*\d{9}\b|\b2\d{8}\b|\b9[1236]\d{7}\b")


def _first_text(node, selectors: list[str]) -> str | None:
    for sel in selectors:
        el = node.select_one(sel) if hasattr(node, "select_one") else None
        if el and el.get_text(strip=True):
            return el.get_text(" ", strip=True)
    return None


def _extract_phone(node) -> str | None:
    # Procura href tel: primeiro
    for a in node.find_all("a", href=True):
        if a["href"].startswith("tel:"):
            return a["href"].replace("tel:", "").strip()
    # Texto livre
    text = node.get_text(" ", strip=True)
    m = _PHONE_RE.search(text)
    return m.group(0) if m else None


def _extract_website(node) -> str | None:
    for a in node.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "pai.pt" not in href and "paginasamarelas" not in href:
            return href
    return None
