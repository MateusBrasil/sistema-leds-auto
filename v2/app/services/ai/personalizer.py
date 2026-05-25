"""Gera UMA frase de abertura específica para cada lead.
A frase é injectada no template como {{personalizacao}}.
"""

from ...services.ai.gemini import GeminiClient
from ...models import Lead


_PROMPT = """És copywriter de prospecção para uma agência de tráfego pago em Portugal (VV TRAFFIC DATA).

Escreve UMA frase de abertura (15-30 palavras) em PT-PT, tom informal e curioso, dirigida ao dono de um negócio chamado "{name}" do nicho "{niche}" em "{city}".

REGRAS:
- A frase deve criar curiosidade sem revelar que vendes tráfego pago.
- Mencionar algo específico do negócio se possível (rating, reviews, cidade).
- Nunca dizer "vi que precisam de…" — usa "reparei numa coisa".
- Não usar emojis no início.
- Não vender directamente.

Contexto extra do negócio:
- Website: {website}
- Rating Google: {rating}
- Nº reviews: {reviews_count}
- Morada: {address}

Devolve APENAS a frase, sem aspas, sem prefixos.
"""


async def personalize_message(client: GeminiClient, lead: Lead) -> str | None:
    if not client.enabled:
        return None

    prompt = _PROMPT.format(
        name=lead.name or "",
        niche=lead.niche or "",
        city=lead.city or "",
        website=lead.website or "—",
        rating=lead.rating if lead.rating is not None else "—",
        reviews_count=lead.reviews_count if lead.reviews_count is not None else "—",
        address=lead.address or "—",
    )

    text = await client.generate(prompt, max_tokens=120)
    if isinstance(text, str):
        return text.strip().strip('"').strip("'")
    return None
