"""Follow-up engine — dispara mensagens reais nos dias configurados (D2/D4/D7/D10).

Cron diário pesca leads sem reply que:
1. Estão em CONTACTADO ou FOLLOWUP stage
2. Têm last_contact_at + delay_days do toque seguinte <= now
3. Têm template para esse toque na CampaignTouch

Se atingir touch_number > 5 sem resposta → ARQUIVO automaticamente.
"""

import asyncio
from datetime import timedelta
from typing import Awaitable, Callable

from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from loguru import logger

from ..config import settings
from ..models import Lead, Campaign, CampaignTouch, Message, MessageStatus, Stage, utcnow
from ..services.pipeline import build_brevo, build_whatsapp, build_gemini
from ..services.ai import personalize_message
from ..services.messaging import render_template


# Defaults para campanhas sem CampaignTouch definido (usa intervals do .env)
def _default_touches() -> list[dict]:
    return [
        {"touch": 2, "delay": settings.FOLLOWUP_D2, "channel": "whatsapp",
         "whatsapp": ("Oi {{nome}}, sou eu outra vez! 😊 Vi que não tiveste oportunidade de responder.\n"
                      "Sem stress — é mesmo uma coisa rápida que quero partilhar contigo sobre o {{nome_negocio}}.\n"
                      "Vale 5 minutos da tua semana?")},
        {"touch": 3, "delay": settings.FOLLOWUP_D3, "channel": "email",
         "subject": "Continuação · {{nome_negocio}}",
         "email": ("Olá {{nome}},\n\nQueria voltar a tocar no que partilhei sobre o {{nome_negocio}}.\n"
                   "{{personalizacao}}\n\nFica disponível este número para uma chamada de 10 min?\n\nAbraço,\nVV Traffic Data")},
        {"touch": 4, "delay": settings.FOLLOWUP_D4, "channel": "whatsapp",
         "whatsapp": ("{{nome}}, vou ser directo:\n\n"
                      "Tenho ajudado outros negócios em {{cidade}} no mesmo nicho a captar 3-5 clientes novos/semana através de Google Ads e Meta Ads.\n\n"
                      "Vale a pena uma conversa de 15 min para te mostrar? Sem compromisso.")},
        {"touch": 5, "delay": settings.FOLLOWUP_D5, "channel": "email",
         "subject": "Última mensagem · {{nome_negocio}}",
         "email": ("Olá {{nome}},\n\nTentei chegar a ti algumas vezes e percebo que estás ocupado.\n"
                   "Esta é a minha última mensagem.\n\n"
                   "Se algum dia quiseres perceber como negócios em {{cidade}} estão a aumentar clientes sem depender de boca-a-boca, "
                   "responde a este email e marcamos.\n\nBoa sorte com o {{nome_negocio}}!\nVV Traffic Data")},
    ]


def _resolve_template(touches: list[CampaignTouch], touch_num: int) -> dict | None:
    """Devolve dict {channel, whatsapp, subject, email, delay} para o toque dado.
    Cai para defaults se a campanha não tem template específico."""
    for t in touches:
        if t.touch_number == touch_num:
            return {
                "channel": t.channel,
                "whatsapp": t.template_whatsapp,
                "subject": t.template_email_subject,
                "email": t.template_email_body,
                "delay": t.delay_days,
            }
    # Fallback aos defaults
    defaults = {d["touch"]: d for d in _default_touches()}
    return defaults.get(touch_num)


async def run_followups(db: Session) -> dict:
    """Executa um ciclo de follow-up. Devolve resumo {triggered, sent, errors}."""
    now = utcnow()

    # Leads candidatos: contactados, sem reply, último contacto >= mínimo delay D2
    leads = db.execute(
        select(Lead).where(
            Lead.stage.in_([Stage.CONTACTADO.value, Stage.FOLLOWUP.value]),
            Lead.last_reply_at.is_(None),
            Lead.last_contact_at.isnot(None),
        )
    ).scalars().all()

    sent_total = 0
    errors_total = 0
    archived = 0
    triggered = 0

    brevo = build_brevo()
    whatsapp = build_whatsapp()
    gemini = build_gemini()

    # Agrupar por campanha para pre-carregar touches
    touches_by_campaign: dict[int, list[CampaignTouch]] = {}

    for lead in leads:
        next_touch = (lead.touches or 1) + 1

        # Se passou 5 toques sem resposta → arquivo
        if next_touch > 5:
            lead.stage = Stage.ARQUIVO.value
            archived += 1
            continue

        # Carrega CampaignTouches da campanha (se existir)
        cid = lead.captured_by_campaign_id
        if cid and cid not in touches_by_campaign:
            touches_by_campaign[cid] = db.execute(
                select(CampaignTouch).where(CampaignTouch.campaign_id == cid)
            ).scalars().all()
        camp_touches = touches_by_campaign.get(cid, []) if cid else []

        tmpl = _resolve_template(camp_touches, next_touch)
        if not tmpl:
            continue

        # Verifica se o delay desde último contacto já passou
        delay_days = tmpl.get("delay", 2)
        threshold = lead.last_contact_at + timedelta(days=delay_days)
        if threshold > now:
            # Ainda não é hora — marca o next_followup_at para a UI mostrar
            if lead.next_followup_at is None or lead.next_followup_at < threshold:
                lead.next_followup_at = threshold
            continue

        triggered += 1
        # Personalização IA (só se ainda não tem)
        if not lead.personalization and gemini.enabled:
            lead.personalization = await personalize_message(gemini, lead)

        # WhatsApp
        if tmpl.get("channel") in ("whatsapp", "both") and tmpl.get("whatsapp") and lead.phone_e164 and whatsapp.enabled:
            body = render_template(tmpl["whatsapp"], lead)
            ok, mid, err = await whatsapp.send_text(lead.phone_e164, body)
            db.add(Message(
                lead_id=lead.id, campaign_id=cid, channel="whatsapp", touch_number=next_touch,
                body=body, status=MessageStatus.SENT.value if ok else MessageStatus.FAILED.value,
                provider_id=mid, error=err, sent_at=utcnow() if ok else None,
            ))
            if ok:
                sent_total += 1
                lead.touches = next_touch
                lead.last_contact_at = utcnow()
                lead.stage = Stage.FOLLOWUP.value
            else:
                errors_total += 1
            await asyncio.sleep(settings.SEND_DELAY_MS / 1000)

        # Email
        if tmpl.get("channel") in ("email", "both") and tmpl.get("email") and lead.email and lead.email_valid and brevo.enabled:
            subject = render_template(tmpl.get("subject") or "Continuação", lead)
            body_text = render_template(tmpl["email"], lead)
            html = "<p>" + body_text.replace("\n", "<br>") + "</p>"
            ok, mid, err = await brevo.send(lead.email, lead.name, subject, html)
            db.add(Message(
                lead_id=lead.id, campaign_id=cid, channel="email", touch_number=next_touch,
                subject=subject, body=body_text,
                status=MessageStatus.SENT.value if ok else MessageStatus.FAILED.value,
                provider_id=mid, error=err, sent_at=utcnow() if ok else None,
            ))
            if ok:
                sent_total += 1
                if not lead.touches or lead.touches < next_touch:
                    lead.touches = next_touch
                lead.last_contact_at = utcnow()
                lead.stage = Stage.FOLLOWUP.value
            else:
                errors_total += 1

        # Calcula próximo follow-up
        tmpl_next = _resolve_template(camp_touches, next_touch + 1)
        if tmpl_next and next_touch + 1 <= 5:
            lead.next_followup_at = utcnow() + timedelta(days=tmpl_next.get("delay", 2))
        else:
            lead.next_followup_at = None  # já chegou ao breakup

    db.commit()
    summary = {"triggered": triggered, "sent": sent_total, "errors": errors_total, "archived": archived}
    logger.info("Follow-up cycle: {}", summary)
    return summary
