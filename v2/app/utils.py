import hashlib
import re
from typing import Optional

import phonenumbers
from loguru import logger


_DEFAULT_REGION = "PT"


def normalize_phone(raw: str | None, country_code: str = "351") -> Optional[str]:
    """Return phone in E.164 (e.g. '+351912345678') or None if invalid."""
    if not raw:
        return None

    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return None

    if len(digits) == 9 and not digits.startswith(country_code):
        digits = country_code + digits

    candidate = "+" + digits

    try:
        parsed = phonenumbers.parse(candidate, _DEFAULT_REGION)
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None


def normalize_website(url: str | None) -> Optional[str]:
    if not url:
        return None
    url = url.strip().lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.split("/")[0].split("?")[0]
    return url or None


def extract_domain(url: str | None) -> Optional[str]:
    return normalize_website(url)


def dedup_hash(name: str, phone: str | None, website: str | None, email: str | None) -> str:
    parts = [
        re.sub(r"\W+", "", (name or "").lower()),
        re.sub(r"\D", "", (phone or "")),
        normalize_website(website) or "",
        (email or "").lower().strip(),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        "data/app.log",
        rotation="10 MB",
        retention="14 days",
        level=level,
        encoding="utf-8",
    )
    import sys
    logger.add(sys.stderr, level=level, colorize=True)
