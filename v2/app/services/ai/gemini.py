"""Gemini client com auto-fallback entre modelos.

Se um modelo dá 429 (quota esgotada), tenta o seguinte na lista.
A ordem é configurável via env (GEMINI_MODEL) mas a fallback chain está aqui.
"""

import json
import time

import httpx
from loguru import logger

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Fallback chain em caso de 429.
# Ordem: lite (cheap, alta quota) → flash (mais capaz) → exp models.
_FALLBACK_CHAIN = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-lite"):
        self.api_key = api_key
        self.primary_model = model
        self.enabled = bool(api_key)
        # Cooldown por modelo quando da 429 (não martelar a API).
        self._cooldown_until: dict[str, float] = {}

    @property
    def model(self) -> str:
        """Compat alias para código existente."""
        return self.primary_model

    def _models_to_try(self) -> list[str]:
        chain = [self.primary_model] + [m for m in _FALLBACK_CHAIN if m != self.primary_model]
        now = time.time()
        return [m for m in chain if self._cooldown_until.get(m, 0) < now]

    async def generate(self, prompt: str, *, json_mode: bool = False, max_tokens: int = 512) -> str | dict | None:
        if not self.enabled:
            return None

        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json" if json_mode else "text/plain",
            },
        }

        models = self._models_to_try()
        if not models:
            logger.warning("Gemini: todos os modelos em cooldown")
            return None

        async with httpx.AsyncClient(timeout=30) as client:
            for model in models:
                endpoint = f"{_BASE}/{model}:generateContent"
                try:
                    r = await client.post(endpoint, params={"key": self.api_key}, json=body)
                    if r.status_code == 200:
                        try:
                            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                        except (KeyError, IndexError):
                            logger.warning("Gemini {} sem texto", model)
                            continue
                        if json_mode:
                            try:
                                return json.loads(text)
                            except json.JSONDecodeError:
                                logger.warning("Gemini {} JSON inválido: {}", model, text[:120])
                                return None
                        return text.strip()

                    if r.status_code == 429:
                        # Quota esgotada — 1h de cooldown para este modelo.
                        self._cooldown_until[model] = time.time() + 3600
                        logger.warning("Gemini {} 429 quota esgotada → fallback", model)
                        continue

                    logger.warning("Gemini {} HTTP {}: {}", model, r.status_code, r.text[:200])
                    continue
                except Exception as e:
                    logger.error("Gemini {} falhou: {}", model, e)
                    continue

        return None
