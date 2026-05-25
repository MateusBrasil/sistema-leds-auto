"""Qualifica um lead (score 0-100) — quanto maior, melhor encaixe para tráfego pago."""

from ...services.ai.gemini import GeminiClient
from ...services.scrapers.base import LeadCandidate


_PROMPT = """És um analista de vendas para uma agência de tráfego pago em Portugal.
A agência vende Google Ads e Meta Ads para negócios locais.

Avalia o lead abaixo numa escala 0-100 (quanto maior, mais provável de comprar).

Critérios (peso):
- Tem website próprio (+15)
- Rating Google ≥ 4.0 (+10)
- Reviews ≥ 30 (+15) — indica volume e maturidade
- Nicho dependente de captação local: dentista, estética, ginásio, imobiliária, advogado, oficina, restaurante (+20)
- Cidade com boa procura: Lisboa, Porto, Braga, Coimbra, Faro, Aveiro, Funchal (+10)
- Telefone listado (+10)
- Tem email contactável (+10)
- Penaliza se for franchise nacional ou multinacional (-30)

Lead:
- Nome: {name}
- Nicho: {niche}
- Cidade: {city}
- Website: {website}
- Telefone: {phone}
- Email: {email}
- Rating Google: {rating}
- Nº reviews: {reviews_count}
- Morada: {address}

Devolve estritamente JSON com este formato:
{{"score": <0-100>, "reason": "<frase curta em PT a explicar o score>"}}
"""


async def qualify_lead(client: GeminiClient, lead: LeadCandidate) -> dict:
    if not client.enabled:
        return {"score": _heuristic_score(lead), "reason": "heurística local (Gemini desactivado)"}

    prompt = _PROMPT.format(
        name=lead.name or "",
        niche=lead.niche or "",
        city=lead.city or "",
        website=lead.website or "—",
        phone=lead.phone or "—",
        email=lead.email or "—",
        rating=lead.rating if lead.rating is not None else "—",
        reviews_count=lead.reviews_count if lead.reviews_count is not None else "—",
        address=lead.address or "—",
    )

    result = await client.generate(prompt, json_mode=True, max_tokens=200)
    if isinstance(result, dict) and "score" in result:
        try:
            score = max(0, min(100, int(result["score"])))
            return {"score": score, "reason": result.get("reason", "")[:300]}
        except (TypeError, ValueError):
            pass

    return {"score": _heuristic_score(lead), "reason": "fallback heurístico"}


def _heuristic_score(lead: LeadCandidate) -> int:
    score = 0
    if lead.website:
        score += 15
    if lead.phone:
        score += 10
    if lead.email:
        score += 10
    if lead.rating and lead.rating >= 4.0:
        score += 10
    if lead.reviews_count and lead.reviews_count >= 30:
        score += 15
    local_niches = {"dentista", "estética", "estetica", "ginásio", "ginasio", "imobiliária", "imobiliaria",
                    "advogado", "oficina", "restaurante", "clínica", "clinica", "salão", "salao"}
    if lead.niche and any(t in lead.niche.lower() for t in local_niches):
        score += 20
    good_cities = {"lisboa", "porto", "braga", "coimbra", "faro", "aveiro", "funchal"}
    if lead.city and lead.city.lower() in good_cities:
        score += 10
    return min(100, score)
