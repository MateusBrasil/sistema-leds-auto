from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class LeadCandidate:
    source: str
    source_id: Optional[str] = None
    name: str = ""
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    niche: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    extra: dict = field(default_factory=dict)


class Scraper(Protocol):
    name: str

    async def search(self, niche: str, city: str, limit: int = 50) -> list[LeadCandidate]:
        ...
