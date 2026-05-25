"""Classifica respostas de leads para encaminhar para a stage certa."""

from ...services.ai.gemini import GeminiClient

_PROMPT = """Classifica esta resposta de prospecção (de prospect a uma mensagem de outreach de uma agência de tráfego pago).

Mensagem: "{text}"

Categorias possíveis:
- interessado: mostra abertura, faz pergunta, pede mais info, quer marcar reunião
- pedir_remover: pede para parar contactos, "remover", "stop", "não quero", reclamação
- irrelevante: erro número, autoresposta, mensagem sem sentido, "obrigado pela mensagem" genérico
- objeção: tem dúvidas/objecções concretas mas ainda não fechou (preço, tempo, dúvida sobre serviço)

Devolve JSON: {{"category": "<uma das 4>", "next_action": "<frase curta a explicar próximo passo>"}}"""


async def classify_reply(client: GeminiClient, text: str) -> dict:
    if not client.enabled:
        lower = text.lower()
        if any(w in lower for w in ["remover", "stop", "parar", "não quero", "nao quero"]):
            return {"category": "pedir_remover", "next_action": "mover para blacklist"}
        return {"category": "interessado", "next_action": "rever manualmente"}

    result = await client.generate(_PROMPT.format(text=text[:1000]), json_mode=True, max_tokens=200)
    if isinstance(result, dict) and "category" in result:
        return result
    return {"category": "interessado", "next_action": "rever manualmente"}
