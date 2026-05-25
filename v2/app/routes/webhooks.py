"""Webhooks: Brevo (email events) e Evolution/Z-API (WhatsApp incoming).

Suporta validação HMAC opcional via .env secrets. Sem secret, aceita públicos.
"""

import hashlib
import hmac
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from loguru import logger

from ..config import settings
from ..database import get_db
from ..models import Lead, Message, MessageStatus, Stage, EventLog, utcnow
from ..services.pipeline import build_gemini
from ..services.ai.classifier import classify_reply
from ..services.notify import notify_reply


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_hmac(secret: str, payload: bytes, signature: str | None) -> bool:
    """Verifica assinatura HMAC-SHA256 (formato: 'sha256=<hex>')."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    received = signature.replace("sha256=", "").strip()
    return hmac.compare_digest(expected, received)


async def _audit(db: Session, source: str, level: str, msg: str, payload: dict | None = None):
    """Regista no event_log."""
    db.add(EventLog(level=level, source=source, actor="webhook", message=msg,
                    payload=str(payload)[:2000] if payload else None))
    db.commit()


# ───────────────────────── Brevo ─────────────────────────

@router.post("/brevo")
async def brevo_event(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()

    # HMAC opcional
    if settings.BREVO_WEBHOOK_SECRET:
        sig = request.headers.get("X-Brevo-Signature") or request.headers.get("X-Webhook-Signature")
        if not _verify_hmac(settings.BREVO_WEBHOOK_SECRET, raw, sig):
            await _audit(db, "brevo_webhook", "WARNING", "Brevo: HMAC inválido")
            raise HTTPException(403, "Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        await _audit(db, "brevo_webhook", "ERROR", "Brevo: JSON inválido")
        raise HTTPException(400, "Invalid JSON")

    event = payload.get("event")
    message_id = payload.get("message-id") or payload.get("messageId")

    await _audit(db, "brevo_webhook", "INFO", f"Brevo event: {event}", payload)

    if not message_id:
        return {"ok": True}

    msg = db.execute(select(Message).where(Message.provider_id == message_id)).scalar_one_or_none()
    if not msg:
        return {"ok": True, "matched": False}

    if event in ("hard_bounce", "soft_bounce", "spam", "blocked"):
        msg.status = MessageStatus.FAILED.value
        msg.error = event
        lead = db.get(Lead, msg.lead_id)
        if lead and event in ("hard_bounce", "spam", "blocked"):
            lead.email_valid = False
            if event == "spam":
                # Auto-pause: marca o lead como blacklist se vier spam (defensivo)
                lead.stage = Stage.BLACKLIST.value
                await _audit(db, "brevo_webhook", "WARNING",
                             f"Lead {lead.id} ({lead.name}) marcado spam → BLACKLIST")
    elif event in ("delivered", "opened", "clicks"):
        # Tracking — apenas regista
        pass

    db.commit()
    return {"ok": True, "matched": True}


# ───────────────────────── WhatsApp ─────────────────────────

@router.post("/whatsapp")
async def whatsapp_event(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()

    # HMAC opcional
    if settings.WHATSAPP_WEBHOOK_SECRET:
        sig = request.headers.get("X-Webhook-Signature") or request.headers.get("X-Hub-Signature-256")
        if not _verify_hmac(settings.WHATSAPP_WEBHOOK_SECRET, raw, sig):
            await _audit(db, "whatsapp_webhook", "WARNING", "WhatsApp: HMAC inválido")
            raise HTTPException(403, "Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        await _audit(db, "whatsapp_webhook", "ERROR", "WhatsApp: JSON inválido")
        raise HTTPException(400, "Invalid JSON")

    await _audit(db, "whatsapp_webhook", "INFO", "WhatsApp event received", payload)

    phone_raw, text = _extract_whatsapp_payload(payload)
    if not phone_raw or not text:
        return {"ok": True, "ignored": "missing phone/text"}

    # Normalize phone para E.164 e match EXACTO (não substring) — fix bug C4
    phone_digits = re.sub(r"\D", "", str(phone_raw))
    e164_candidate = "+" + phone_digits

    # Match exacto first, depois match parcial só se único.
    lead = db.execute(select(Lead).where(Lead.phone_e164 == e164_candidate)).scalar_one_or_none()
    if not lead:
        # Fallback: procura por endswith mas só se houver exactamente 1 match (evita ambiguidade)
        candidates = db.execute(
            select(Lead).where(Lead.phone_e164.endswith(phone_digits[-9:]))
        ).scalars().all()
        if len(candidates) == 1:
            lead = candidates[0]
        elif len(candidates) > 1:
            await _audit(db, "whatsapp_webhook", "WARNING",
                         f"Resposta ambígua de {e164_candidate}: {len(candidates)} leads coincidem nos últimos 9 dígitos")
            return {"ok": True, "ambiguous": [l.id for l in candidates]}

    if not lead:
        logger.info("WhatsApp reply from unknown number {}", e164_candidate)
        return {"ok": True, "matched": False}

    # Save inbound message
    db.add(Message(
        lead_id=lead.id, channel="whatsapp", direction="in",
        body=text, status=MessageStatus.REPLIED.value, sent_at=utcnow(),
    ))
    lead.last_reply_at = utcnow()
    lead.next_followup_at = None  # responder pára a sequência

    # AI classify
    gemini = build_gemini()
    classification = await classify_reply(gemini, text)
    cat = classification.get("category", "interessado")

    stage_before = lead.stage
    if cat == "pedir_remover":
        lead.stage = Stage.BLACKLIST.value
    elif cat == "interessado":
        lead.stage = Stage.REUNIAO.value
    elif cat == "objeção":
        lead.stage = Stage.FOLLOWUP.value

    db.commit()

    # Notifica
    try:
        await notify_reply(lead, text, classification)
    except Exception as e:
        logger.warning("notify_reply falhou: {}", e)

    await _audit(db, "whatsapp_webhook", "INFO",
                 f"Lead {lead.id} ({lead.name}): {stage_before} → {lead.stage} (classificação: {cat})")

    return {"ok": True, "matched": True, "lead_id": lead.id, "classification": classification}


def _extract_whatsapp_payload(payload: dict) -> tuple[str | None, str | None]:
    """Extrai (phone, text) — suporta formato Evolution e Z-API."""
    # Evolution: { "data": { "key": { "remoteJid": "351...@s.whatsapp.net" }, "message": { "conversation": "..." } } }
    if "data" in payload and isinstance(payload["data"], dict):
        data = payload["data"]
        remote = data.get("key", {}).get("remoteJid", "")
        phone = remote.split("@")[0] if remote else None
        msg = data.get("message", {}) or {}
        text = msg.get("conversation") or (msg.get("extendedTextMessage") or {}).get("text")
        if phone and text:
            return phone, text

    # Z-API: { "phone": "351...", "text": { "message": "..." } } OR { "message": "..." }
    phone = payload.get("phone") or payload.get("from")
    text = None
    if isinstance(payload.get("text"), dict):
        text = payload["text"].get("message")
    text = text or payload.get("message") or payload.get("body")
    return phone, text
