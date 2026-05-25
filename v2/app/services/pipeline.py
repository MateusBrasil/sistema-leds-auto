"""Pipeline central: captação → dedup → enriquecimento → qualificação → save."""

import asyncio
from typing import Awaitable, Callable

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from loguru import logger

from ..config import settings
from ..models import Lead, Campaign, Message, MessageStatus, Stage, utcnow
from ..utils import dedup_hash, normalize_phone, normalize_website
from .scrapers.base import LeadCandidate
from .scrapers import (
    GoogleMapsScraper, ApifyLinkedInScraper, ApifyInstagramScraper,
    PaginasAmarelasScraper, RaciusScraper,
)
from .enrichment import HunterClient, EmailValidator
from .ai import GeminiClient, qualify_lead, personalize_message
from .ai.niche_expander import expand_niche
from .messaging import BrevoClient, WhatsAppClient, render_template


EventCallback = Callable[[dict], Awaitable[None]] | None


# ───────────────────────── Factories ─────────────────────────

def build_scrapers() -> list:
    available = []
    if settings.GOOGLE_PLACES_API_KEY:
        available.append(GoogleMapsScraper(settings.GOOGLE_PLACES_API_KEY))
    if settings.APIFY_API_TOKEN:
        available.append(ApifyLinkedInScraper(settings.APIFY_API_TOKEN))
        available.append(ApifyInstagramScraper(settings.APIFY_API_TOKEN))
    # Sempre disponíveis (scraping HTML directo, sem chave)
    available.append(PaginasAmarelasScraper())
    available.append(RaciusScraper())
    return available


def build_hunter() -> HunterClient: return HunterClient(settings.HUNTER_API_KEY)
def build_validator() -> EmailValidator: return EmailValidator(settings.ZEROBOUNCE_API_KEY)
def build_gemini() -> GeminiClient: return GeminiClient(settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
def build_brevo() -> BrevoClient: return BrevoClient(settings.BREVO_API_KEY, settings.SENDER_NAME, settings.SENDER_EMAIL)


def build_whatsapp() -> WhatsAppClient:
    return WhatsAppClient(
        provider=settings.WHATSAPP_PROVIDER,
        evolution_base_url=settings.EVOLUTION_BASE_URL,
        evolution_api_key=settings.EVOLUTION_API_KEY,
        evolution_instance=settings.EVOLUTION_INSTANCE,
        zapi_instance_id=settings.ZAPI_INSTANCE_ID,
        zapi_token=settings.ZAPI_TOKEN,
        zapi_client_token=settings.ZAPI_CLIENT_TOKEN,
    )


# Helper para chamar callback sem partir se for None
async def _emit(cb: EventCallback, event: str, **data) -> None:
    if cb is None:
        return
    try:
        await cb({"event": event, **data})
    except Exception as e:
        logger.warning("event callback failed for {}: {}", event, e)


# ───────────────────────── Capture ─────────────────────────

async def capture(
    db: Session,
    niche: str,
    city: str,
    max_leads: int = 60,
    *,
    expand_variations: bool = True,
    campaign_id: int | None = None,
    on_event: EventCallback = None,
) -> int:
    """Captura leads em múltiplas fontes, com expansão semântica do nicho.

    `max_leads` é o teto total (não por fonte/variação).
    Emite eventos via `on_event` para feedback live (SSE).
    """
    scrapers = build_scrapers()
    if not scrapers:
        await _emit(on_event, "error", message="Sem APIs de captura configuradas")
        return 0

    hunter = build_hunter()
    validator = build_validator()
    gemini = build_gemini()

    # ── 1. Expand niche
    if expand_variations:
        await _emit(on_event, "step", label="A expandir o nicho com IA...", progress=5)
        variations = await expand_niche(gemini, niche, max_variations=4)
        await _emit(on_event, "niche-expanded", variations=variations)
    else:
        variations = [niche]

    # Distribuir o orçamento por variação
    per_variation = max(5, max_leads // len(variations))

    # ── 2. Run all scrapers × variations in parallel
    await _emit(on_event, "step", label=f"A procurar em {len(scrapers)} fonte(s) × {len(variations)} variação(ões)...", progress=12)

    tasks = []
    task_meta = []
    for scraper in scrapers:
        for var in variations:
            tasks.append(scraper.search(var, city, per_variation))
            task_meta.append({"source": scraper.name, "query": f"{var} {city}"})

    raw_lists = await asyncio.gather(*tasks, return_exceptions=True)

    candidates: list[LeadCandidate] = []
    for meta, result in zip(task_meta, raw_lists):
        if isinstance(result, Exception):
            await _emit(on_event, "source-failed", **meta, error=str(result)[:200])
            continue
        await _emit(on_event, "source-done", **meta, count=len(result))
        candidates.extend(result)

    await _emit(on_event, "step", label=f"Encontrei {len(candidates)} candidatos brutos. A fazer deduplicação...", progress=35)

    # ── 3. Dedup (in-batch)
    seen: set[str] = set()
    deduped: list[LeadCandidate] = []
    for c in candidates:
        h = dedup_hash(c.name, c.phone, c.website, c.email)
        if h in seen:
            continue
        seen.add(h)
        c.extra["_hash"] = h
        deduped.append(c)

    # Cross-batch dedup (já em DB)
    existing_hashes = set(
        row[0]
        for row in db.execute(select(Lead.dedup_hash).where(Lead.dedup_hash.in_(seen))).all()
    )
    new_candidates = [c for c in deduped if c.extra["_hash"] not in existing_hashes]

    await _emit(on_event, "step", label=f"{len(new_candidates)} novos (de {len(deduped)} únicos). A enriquecer e qualificar...", progress=45, total=len(new_candidates))

    if not new_candidates:
        await _emit(on_event, "done", captured=0, message="Todos os leads encontrados já existiam na base.")
        return 0

    # Cap to max_leads
    new_candidates = new_candidates[:max_leads]

    # ── 4. Enrich + qualify each (one-by-one para emitir eventos)
    new_count = 0
    for i, c in enumerate(new_candidates):
        # Enrich email if missing
        if not c.email and c.website:
            c.email = await hunter.find_email(c.name, c.website)

        email_valid = await validator.is_valid(c.email) if c.email else False
        phone_e164 = normalize_phone(c.phone, settings.SENDER_COUNTRY_CODE)
        qual = await qualify_lead(gemini, c)

        lead = Lead(
            source=c.source,
            source_id=c.source_id,
            dedup_hash=c.extra["_hash"],
            captured_by_campaign_id=campaign_id,
            name=c.name,
            website=normalize_website(c.website),
            phone=c.phone,
            phone_e164=phone_e164,
            email=c.email,
            email_valid=email_valid,
            address=c.address,
            city=c.city or city,
            niche=c.niche or niche,
            rating=c.rating,
            reviews_count=c.reviews_count,
            score=qual["score"],
            score_reason=qual["reason"],
            stage=Stage.NOVO.value,
        )
        db.add(lead)
        db.flush()  # populate id
        new_count += 1

        await _emit(on_event, "lead", **{
            "id": lead.id,
            "name": lead.name,
            "phone_e164": lead.phone_e164,
            "email": lead.email,
            "city": lead.city,
            "score": lead.score,
            "stage": lead.stage,
            "source": lead.source,
            "rating": lead.rating,
            "index": i + 1,
            "total": len(new_candidates),
            "progress": 45 + int((i + 1) / len(new_candidates) * 45),
        })

    db.commit()
    await _emit(on_event, "step", label=f"Capturados {new_count} leads novos.", progress=95)
    logger.info("Capturados {} leads novos (de {} candidatos)", new_count, len(deduped))
    return new_count


# ───────────────────────── Send ─────────────────────────

async def send_campaign(db: Session, campaign_id: int, *, on_event: EventCallback = None) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        return {"error": "campaign not found"}

    gemini = build_gemini()
    brevo = build_brevo()
    whatsapp = build_whatsapp()

    today_email_count = _count_today(db, "email")
    today_whatsapp_count = _count_today(db, "whatsapp")
    email_budget = max(0, settings.EMAIL_MAX_PER_DAY - today_email_count)
    whatsapp_budget = max(0, settings.WHATSAPP_MAX_PER_DAY - today_whatsapp_count)

    candidates = db.execute(
        select(Lead)
        .where(Lead.stage == Stage.NOVO.value)
        .where(Lead.niche == campaign.niche)
        .where(Lead.city == campaign.city)
        .where(Lead.score >= campaign.min_score)
        .order_by(Lead.score.desc().nulls_last())
    ).scalars().all()

    dry = bool(campaign.dry_run)
    label = f"DRY-RUN: simular envio para {len(candidates)} leads" if dry else f"A enviar para {len(candidates)} leads (score ≥ {campaign.min_score})..."
    await _emit(on_event, "step", label=label, progress=50)

    sent_email = sent_whatsapp = errors = 0

    for i, lead in enumerate(candidates):
        if campaign.use_ai_personalization and not lead.personalization:
            lead.personalization = await personalize_message(gemini, lead)

        if lead.phone_e164 and sent_whatsapp < whatsapp_budget:
            body = render_template(campaign.template_whatsapp, lead)
            if dry:
                ok, mid, err = True, f"dry-{lead.id}", None
            else:
                ok, mid, err = await whatsapp.send_text(lead.phone_e164, body)
            db.add(Message(
                lead_id=lead.id, campaign_id=campaign.id, channel="whatsapp", touch_number=1,
                body=body, status=MessageStatus.SENT.value if ok else MessageStatus.FAILED.value,
                provider_id=mid, error=err, sent_at=utcnow() if ok else None,
            ))
            if ok:
                sent_whatsapp += 1
                _mark_contacted(lead)
                await _emit(on_event, "sent", channel="whatsapp", lead_id=lead.id, lead_name=lead.name)
            else:
                errors += 1
                await _emit(on_event, "failed", channel="whatsapp", lead_id=lead.id, error=err or "?")
            await asyncio.sleep(settings.SEND_DELAY_MS / 1000)

        if lead.email and lead.email_valid and sent_email < email_budget:
            subject = render_template(campaign.template_email_subject, lead)
            body_text = render_template(campaign.template_email_body, lead)
            html = "<p>" + body_text.replace("\n", "<br>") + "</p>"
            if dry:
                ok, mid, err = True, f"dry-{lead.id}-em", None
            else:
                ok, mid, err = await brevo.send(lead.email, lead.name, subject, html)
            db.add(Message(
                lead_id=lead.id, campaign_id=campaign.id, channel="email", touch_number=1,
                subject=subject, body=body_text,
                status=MessageStatus.SENT.value if ok else MessageStatus.FAILED.value,
                provider_id=mid, error=err, sent_at=utcnow() if ok else None,
            ))
            if ok:
                sent_email += 1
                _mark_contacted(lead)
                await _emit(on_event, "sent", channel="email", lead_id=lead.id, lead_name=lead.name)
            else:
                errors += 1
                await _emit(on_event, "failed", channel="email", lead_id=lead.id, error=err or "?")

        if sent_email >= email_budget and sent_whatsapp >= whatsapp_budget:
            break

    campaign.messages_sent += sent_email + sent_whatsapp
    campaign.status = "sending"
    db.commit()

    return {
        "campaign_id": campaign_id,
        "sent_whatsapp": sent_whatsapp,
        "sent_email": sent_email,
        "errors": errors,
        "remaining_in_pool": len(candidates) - sent_whatsapp - sent_email,
    }


def _count_today(db: Session, channel: str) -> int:
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.execute(
        select(func.count(Message.id))
        .where(Message.channel == channel)
        .where(Message.status == MessageStatus.SENT.value)
        .where(Message.sent_at >= today_start)
    ).scalar_one() or 0


def _mark_contacted(lead: Lead) -> None:
    if lead.stage == Stage.NOVO.value:
        lead.stage = Stage.CONTACTADO.value
    lead.last_contact_at = utcnow()
    lead.touches = (lead.touches or 0) + 1


# run_followups foi movido para services/followup.py (envia mensagens REAIS).
