"""Páginas HTML — painel, leads, campanhas, status, settings."""

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_user
from ..models import Lead, Campaign, Message, MessageStatus, Stage, utcnow
from ..services.pipeline import capture, send_campaign

router = APIRouter()

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# ──────────────────────── Helpers ────────────────────────

def _daily_series(db: Session, days: int = 14) -> list[dict]:
    """Returns list of {date, total_leads, sent_whatsapp, sent_email, replies} for last `days` days."""
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=days - 1)

    # Leads created per day
    rows_leads = db.execute(
        select(func.date(Lead.created_at), func.count(Lead.id))
        .where(Lead.created_at >= start)
        .group_by(func.date(Lead.created_at))
    ).all()
    leads_by_day = {str(d): n for d, n in rows_leads}

    # Messages sent per day per channel
    rows_msg = db.execute(
        select(func.date(Message.sent_at), Message.channel, func.count(Message.id))
        .where(Message.sent_at >= start, Message.direction == "out", Message.status == "sent")
        .group_by(func.date(Message.sent_at), Message.channel)
    ).all()
    msgs_by_day = {}
    for d, ch, n in rows_msg:
        msgs_by_day.setdefault(str(d), {})[ch] = n

    # Replies per day
    rows_replies = db.execute(
        select(func.date(Message.created_at), func.count(Message.id))
        .where(Message.created_at >= start, Message.direction == "in")
        .group_by(func.date(Message.created_at))
    ).all()
    replies_by_day = {str(d): n for d, n in rows_replies}

    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).date()
        ds = str(d)
        out.append({
            "date": d,
            "leads": leads_by_day.get(ds, 0),
            "whatsapp": msgs_by_day.get(ds, {}).get("whatsapp", 0),
            "email": msgs_by_day.get(ds, {}).get("email", 0),
            "replies": replies_by_day.get(ds, 0),
        })
    return out


# ──────────────────────── Dashboard ────────────────────────

@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db), user: str = Depends(require_user)):
    total = db.execute(select(func.count(Lead.id))).scalar_one()
    by_stage = dict(db.execute(select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage)).all())
    by_source = dict(db.execute(select(Lead.source, func.count(Lead.id)).group_by(Lead.source)).all())

    # Today aggregates
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today_email = db.execute(
        select(func.count(Message.id))
        .where(Message.channel == "email", Message.status == "sent", Message.sent_at >= today)
    ).scalar_one()
    sent_today_whatsapp = db.execute(
        select(func.count(Message.id))
        .where(Message.channel == "whatsapp", Message.status == "sent", Message.sent_at >= today)
    ).scalar_one()
    replies_today = db.execute(
        select(func.count(Message.id))
        .where(Message.direction == "in", Message.created_at >= today)
    ).scalar_one()

    # 14-day series for sparklines / chart
    series = _daily_series(db, days=14)

    # Top niches
    top_niches = db.execute(
        select(Lead.niche, func.count(Lead.id), func.avg(Lead.score))
        .where(Lead.niche.isnot(None))
        .group_by(Lead.niche)
        .order_by(desc(func.count(Lead.id)))
        .limit(5)
    ).all()

    # Top cities
    top_cities = db.execute(
        select(Lead.city, func.count(Lead.id))
        .where(Lead.city.isnot(None))
        .group_by(Lead.city)
        .order_by(desc(func.count(Lead.id)))
        .limit(5)
    ).all()

    # Conversion: contacted vs replied
    contacted = db.execute(
        select(func.count(Lead.id)).where(Lead.last_contact_at.isnot(None))
    ).scalar_one()
    replied = db.execute(
        select(func.count(Lead.id)).where(Lead.last_reply_at.isnot(None))
    ).scalar_one()
    reply_rate = (replied / contacted * 100) if contacted else 0

    recent_leads = db.execute(
        select(Lead).order_by(desc(Lead.created_at)).limit(10)
    ).scalars().all()

    campaigns = db.execute(
        select(Campaign).order_by(desc(Campaign.created_at)).limit(5)
    ).scalars().all()

    return templates.TemplateResponse(request, "dashboard.html", {
        "total": total,
        "by_stage": by_stage,
        "by_source": by_source,
        "sent_today_email": sent_today_email,
        "sent_today_whatsapp": sent_today_whatsapp,
        "replies_today": replies_today,
        "series": series,
        "top_niches": top_niches,
        "top_cities": top_cities,
        "contacted": contacted,
        "replied": replied,
        "reply_rate": reply_rate,
        "recent_leads": recent_leads,
        "campaigns": campaigns,
    })


# ──────────────────────── Leads ────────────────────────

@router.get("/leads", response_class=HTMLResponse)
def list_leads(
    request: Request,
    stage: str | None = None,
    source: str | None = None,
    min_score: int = 0,
    q: str | None = None,
    campaign: int | None = None,
    tag: str | None = None,
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
    user: str = Depends(require_user),
):
    per_page = max(10, min(200, per_page))
    page = max(1, page)

    base = select(Lead)
    if stage: base = base.where(Lead.stage == stage)
    if source: base = base.where(Lead.source == source)
    if min_score > 0: base = base.where(Lead.score >= min_score)
    if campaign: base = base.where(Lead.captured_by_campaign_id == campaign)
    if tag: base = base.where(Lead.tags.ilike(f"%{tag}%"))
    if q:
        like = f"%{q}%"
        base = base.where(or_(
            Lead.name.ilike(like), Lead.email.ilike(like),
            Lead.phone_e164.ilike(like), Lead.website.ilike(like),
            Lead.notes.ilike(like),
        ))

    # Total para paginação
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    leads = db.execute(
        base.order_by(Lead.score.desc().nulls_last(), desc(Lead.created_at))
            .offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()

    stages = [s.value for s in Stage]
    sources_rows = db.execute(select(Lead.source).distinct()).all()
    sources = [row[0] for row in sources_rows]

    campaigns_with_leads = db.execute(
        select(Campaign.id, Campaign.name, Campaign.niche, Campaign.city, Campaign.created_at, func.count(Lead.id))
        .join(Lead, Lead.captured_by_campaign_id == Campaign.id)
        .group_by(Campaign.id)
        .order_by(desc(Campaign.created_at))
    ).all()

    # Tags únicas (para autocomplete simples)
    tag_rows = db.execute(select(Lead.tags).where(Lead.tags.isnot(None))).all()
    all_tags = set()
    for (t,) in tag_rows:
        if t:
            for one in t.split(","):
                one = one.strip()
                if one:
                    all_tags.add(one)

    return templates.TemplateResponse(request, "leads.html", {
        "leads": leads,
        "stages": stages,
        "sources": sources,
        "campaigns_with_leads": campaigns_with_leads,
        "all_tags": sorted(all_tags),
        "selected_stage": stage or "",
        "selected_source": source or "",
        "selected_campaign": campaign or "",
        "selected_tag": tag or "",
        "min_score": min_score,
        "search_q": q or "",
        "total_filtered": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    })


@router.get("/leads/{lead_id}", response_class=HTMLResponse)
def lead_detail(lead_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(require_user)):
    lead = db.get(Lead, lead_id)
    if not lead: raise HTTPException(404, "Lead não encontrado")
    messages = db.execute(
        select(Message).where(Message.lead_id == lead_id).order_by(Message.created_at)
    ).scalars().all()
    return templates.TemplateResponse(request, "lead_detail.html", {
        "lead": lead,
        "messages": messages,
        "stages": [s.value for s in Stage],
    })


@router.post("/leads/{lead_id}/stage")
def update_stage(lead_id: int, stage: str = Form(...), db: Session = Depends(get_db), user: str = Depends(require_user)):
    lead = db.get(Lead, lead_id)
    if not lead: raise HTTPException(404)
    lead.stage = stage
    db.commit()
    return RedirectResponse(f"/leads/{lead_id}?toast=Etapa+actualizada", status_code=303)


# ──────────────────────── Campaigns ────────────────────────

@router.get("/campaigns", response_class=HTMLResponse)
def list_campaigns(request: Request, db: Session = Depends(get_db), user: str = Depends(require_user)):
    campaigns = db.execute(select(Campaign).order_by(desc(Campaign.created_at))).scalars().all()
    return templates.TemplateResponse(request, "campaigns.html", {"campaigns": campaigns})


@router.get("/campaigns/new", response_class=HTMLResponse)
def new_campaign_form(request: Request, user: str = Depends(require_user)):
    return templates.TemplateResponse(request, "campaign_new.html", {})


@router.post("/campaigns/new")
async def new_campaign_submit(
    request: Request,
    name: str = Form(...),
    niche: str = Form(...),
    city: str = Form(...),
    template_whatsapp: str = Form(...),
    template_email_subject: str = Form(...),
    template_email_body: str = Form(...),
    min_score: int = Form(0),
    max_leads: int = Form(60),
    use_ai: bool = Form(False),
    expand_variations: bool = Form(False),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
    user: str = Depends(require_user),
):
    """Cria a campanha e redirecciona para a vista live, que abre o stream SSE."""
    campaign = Campaign(
        name=name, niche=niche, city=city,
        template_whatsapp=template_whatsapp,
        template_email_subject=template_email_subject,
        template_email_body=template_email_body,
        min_score=min_score,
        max_leads=max(5, min(300, max_leads)),
        use_ai_personalization=use_ai,
        expand_variations=expand_variations,
        dry_run=dry_run,
    )
    db.add(campaign); db.commit(); db.refresh(campaign)
    return RedirectResponse(f"/campaigns/{campaign.id}/run", status_code=303)


@router.get("/campaigns/{campaign_id}/run", response_class=HTMLResponse)
def campaign_run_live(campaign_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(require_user)):
    c = db.get(Campaign, campaign_id)
    if not c: raise HTTPException(404, "Campanha não encontrada")
    return templates.TemplateResponse(request, "campaign_run.html", {"c": c})


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_detail(campaign_id: int, request: Request, db: Session = Depends(get_db), user: str = Depends(require_user)):
    c = db.get(Campaign, campaign_id)
    if not c: raise HTTPException(404, "Campanha não encontrada")
    # Stats from messages of this campaign
    sent_email = db.execute(select(func.count(Message.id)).where(Message.campaign_id == campaign_id, Message.channel == "email", Message.status == "sent")).scalar_one()
    sent_whatsapp = db.execute(select(func.count(Message.id)).where(Message.campaign_id == campaign_id, Message.channel == "whatsapp", Message.status == "sent")).scalar_one()
    failed = db.execute(select(func.count(Message.id)).where(Message.campaign_id == campaign_id, Message.status == "failed")).scalar_one()
    return templates.TemplateResponse(request, "campaign_detail.html", {
        "c": c, "sent_email": sent_email, "sent_whatsapp": sent_whatsapp, "failed": failed,
    })


# ──────────────────────── Status & Settings ────────────────────────

@router.get("/status", response_class=HTMLResponse)
def status_page(request: Request, user: str = Depends(require_user)):
    return templates.TemplateResponse(request, "status.html", {})


@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, user: str = Depends(require_user)):
    return templates.TemplateResponse(request, "analytics.html", {})


@router.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request, user: str = Depends(require_user)):
    return templates.TemplateResponse(request, "audit.html", {})


@router.get("/templates", response_class=HTMLResponse)
def templates_page(request: Request, db: Session = Depends(get_db), user: str = Depends(require_user)):
    from ..models import MessageTemplate
    rows = db.execute(select(MessageTemplate).order_by(desc(MessageTemplate.created_at))).scalars().all()
    return templates.TemplateResponse(request, "templates.html", {"templates": rows})


@router.get("/import", response_class=HTMLResponse)
def import_page(request: Request, user: str = Depends(require_user)):
    return templates.TemplateResponse(request, "import.html", {})


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, user: str = Depends(require_user)):
    from ..services.backup import db_stats, list_backups
    return templates.TemplateResponse(request, "settings.html", {
        "settings": settings,
        "db_stats": db_stats(),
        "backups": list_backups(),
    })
