"""Testes do qualifier IA — fallback heurístico (sem chamadas reais)."""

from app.services.ai.qualifier import _heuristic_score
from app.services.scrapers.base import LeadCandidate


def _lead(**kw):
    defaults = {"source": "google_maps", "name": "X", "niche": "geral", "city": "x"}
    defaults.update(kw)
    return LeadCandidate(**defaults)


def test_baseline_zero():
    # Lead sem nada → score 0
    lead = _lead(niche="aleatorio", city="aleatorio")
    assert _heuristic_score(lead) == 0


def test_website_bonus():
    lead = _lead(website="x.pt", niche="z", city="z")
    assert _heuristic_score(lead) == 15


def test_full_local_niche_with_city():
    lead = _lead(
        website="x.pt", phone="+351912345678", email="x@x.pt",
        rating=4.5, reviews_count=100, niche="dentista", city="Lisboa",
    )
    s = _heuristic_score(lead)
    # website 15 + phone 10 + email 10 + rating 10 + reviews 15 + nicho local 20 + cidade 10 = 90
    assert s == 90


def test_capped_at_100():
    lead = _lead(
        website="x.pt", phone="+351912345678", email="x@x.pt",
        rating=5.0, reviews_count=10000, niche="clínica dentária", city="Porto",
    )
    s = _heuristic_score(lead)
    assert s <= 100
