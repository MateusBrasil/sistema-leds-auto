"""Notificações para o operador quando um lead responde.

Suporta Telegram e Slack via webhooks. Activado se a env var estiver preenchida.
"""

import asyncio

import httpx
from loguru import logger

from ..config import settings
from ..models import Lead


def _fmt_lead_reply(lead: Lead, text: str, classification: dict) -> str:
    cat = classification.get("category", "?")
    action = classification.get("next_action", "")
    score = lead.score if lead.score is not None else "—"
    emoji = "🟢" if cat == "interessado" else "🟠" if cat == "objeção" else "🔴" if cat == "pedir_remover" else "⚪"

    return (
        f"{emoji} *Novo reply* — *{lead.name}* (score {score})\n"
        f"_{lead.city or '?'} · {lead.niche or '?'} · {lead.phone_e164 or lead.email or ''}_\n\n"
        f"💬 \"{text[:280]}\"\n\n"
        f"*Classificação:* {cat}\n"
        f"*Próxima acção:* {action}"
    )


async def _send_telegram(message: str) -> bool:
    if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            })
            return r.status_code == 200
    except Exception as e:
        logger.warning("Telegram notify failed: {}", e)
        return False


async def _send_slack(message: str) -> bool:
    if not settings.SLACK_WEBHOOK_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(settings.SLACK_WEBHOOK_URL, json={"text": message})
            return 200 <= r.status_code < 300
    except Exception as e:
        logger.warning("Slack notify failed: {}", e)
        return False


async def notify_reply(lead: Lead, text: str, classification: dict) -> dict:
    """Notifica todos os providers configurados (paralelo)."""
    message = _fmt_lead_reply(lead, text, classification)
    results = await asyncio.gather(
        _send_telegram(message),
        _send_slack(message),
        return_exceptions=True,
    )
    return {
        "telegram": results[0] if not isinstance(results[0], Exception) else False,
        "slack": results[1] if not isinstance(results[1], Exception) else False,
    }


async def notify_test(message: str = "🧪 Teste de notificação VV Traffic Data") -> dict:
    """Endpoint útil para o utilizador validar a config."""
    return {
        "telegram": await _send_telegram(message),
        "slack": await _send_slack(message),
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        "slack_configured": bool(settings.SLACK_WEBHOOK_URL),
    }
