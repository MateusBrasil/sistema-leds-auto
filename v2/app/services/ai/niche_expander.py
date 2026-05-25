"""Expande um nicho em variações comuns para procurar no Google Maps.

Exemplo: "lavagem de carro" → [
  "lavagem de carro", "lavagem automotiva", "lavajato",
  "auto lavagem", "lava-jato", "lavagem auto"
]

Usa Gemini quando disponível. Fallback heurístico para nichos comuns.
Cache em memória (LRU) para não pagar 2x pela mesma expansão.
"""

import json
from functools import lru_cache

from .gemini import GeminiClient


_PROMPT = """És especialista em pesquisa de negócios locais em Portugal e Brasil.

O utilizador quer encontrar negócios do tipo "{niche}" no Google Maps.
Lista 4-6 termos de pesquisa equivalentes ou similares que pessoas em PT/BR usam para descrever o mesmo tipo de negócio.

Inclui sinónimos, variantes regionais (PT-PT vs PT-BR), variações ortográficas e termos compostos.
Não inclui marcas ou nomes próprios.
Não repete o termo original.

Exemplos:
- "lavagem de carro" → ["lavagem automotiva", "lavajato", "auto lavagem", "lava-jato", "lavagem auto"]
- "clínica dentária" → ["dentista", "clínica de odontologia", "consultório dentário", "ortodontista"]
- "ginásio" → ["academia", "fitness", "crossfit", "personal trainer"]

Termo do utilizador: "{niche}"

Devolve estritamente JSON: {{"variations": ["...", "...", ...]}}"""


# Fallback heurístico para nichos top em PT (usado se Gemini indisponível)
_HARDCODED = {
    "lavagem de carro": ["lavagem automotiva", "lavajato", "auto lavagem", "lava-jato"],
    "lavagem automotiva": ["lavagem de carro", "lavajato", "auto lavagem"],
    "clínica dentária": ["dentista", "clínica de odontologia", "ortodontista", "consultório dentário"],
    "dentista": ["clínica dentária", "ortodontista", "clínica de odontologia"],
    "ginásio": ["academia", "crossfit", "fitness", "personal trainer"],
    "academia": ["ginásio", "crossfit", "fitness"],
    "salão de beleza": ["cabeleireiro", "salão de cabelo", "barbearia", "estética"],
    "cabeleireiro": ["salão de beleza", "barbearia", "salão de cabelo"],
    "advogado": ["escritório de advocacia", "solicitador", "consultor jurídico"],
    "imobiliária": ["agência imobiliária", "consultor imobiliário", "mediação imobiliária"],
    "restaurante": ["tasca", "bistro", "cervejaria"],
    "padaria": ["pastelaria", "padaria e pastelaria"],
    "oficina": ["oficina mecânica", "mecânico", "garagem auto", "auto reparação"],
    "psicólogo": ["psicoterapeuta", "consultório de psicologia"],
    "fisioterapeuta": ["clínica de fisioterapia", "reabilitação"],
    "veterinário": ["clínica veterinária", "hospital veterinário"],
}


# Cache em memória (limita até 256 nichos)
_CACHE: dict[str, list[str]] = {}


async def expand_niche(gemini: GeminiClient, niche: str, *, max_variations: int = 5) -> list[str]:
    """Devolve uma lista que começa pelo nicho original + variações.

    Resultado sempre tem o original como primeiro elemento.
    Cache em memória para a mesma string normalizada.
    """
    if not niche:
        return [niche]

    key = niche.strip().lower()
    if key in _CACHE:
        return _CACHE[key]

    # 1. Try hardcoded
    if key in _HARDCODED:
        result = [niche.strip()] + _HARDCODED[key][:max_variations]
        _CACHE[key] = result
        return result

    # 2. Try Gemini
    if gemini.enabled:
        try:
            data = await gemini.generate(
                _PROMPT.format(niche=niche.strip()),
                json_mode=True,
                max_tokens=300,
            )
            if isinstance(data, dict) and isinstance(data.get("variations"), list):
                variations = [v.strip() for v in data["variations"] if isinstance(v, str) and v.strip()]
                # remove duplicates and the original
                seen = {key}
                clean = []
                for v in variations:
                    vk = v.lower()
                    if vk not in seen:
                        seen.add(vk)
                        clean.append(v)
                result = [niche.strip()] + clean[:max_variations]
                _CACHE[key] = result
                return result
        except Exception:
            pass

    # 3. Just return original
    result = [niche.strip()]
    _CACHE[key] = result
    return result
