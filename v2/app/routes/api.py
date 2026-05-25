"""Endpoints JSON e CSV — integrações + acções do dashboard."""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_user
from ..models import Lead, Campaign, Message, Stage
from ..services.pipeline import capture, send_campaign, build_brevo, build_whatsapp
from ..services.messaging import render_template
from ..services.health import all_checks
from ..services.backup import list_backups, db_stats, auto_backup_on_startup, _db_path


router = APIRouter(prefix="/api", tags=["api"])


# ────────────────────── Capture / Campaigns ──────────────────────

class CaptureRequest(BaseModel):
    niche: str
    city: str
    limit_per_source: int = 60


@router.post("/capture")
async def api_capture(req: CaptureRequest, request: Request, db: Session = Depends(get_db), user: str = Depends(require_user)):
    n = await capture(db, req.niche, req.city, req.limit_per_source)
    return {"new_leads": n}


class CampaignCreate(BaseModel):
    name: str
    niche: str
    city: str
    template_whatsapp: str
    template_email_subject: str
    template_email_body: str
    min_score: int = 0
    max_leads: int = 60
    use_ai_personalization: bool = True
    expand_variations: bool = True


@router.post("/campaigns")
def api_create_campaign(c: CampaignCreate, db: Session = Depends(get_db), user: str = Depends(require_user)):
    campaign = Campaign(**c.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return {"id": campaign.id, "status": campaign.status}


@router.post("/campaigns/{campaign_id}/send")
async def api_send_campaign(campaign_id: int, db: Session = Depends(get_db), user: str = Depends(require_user)):
    result = await send_campaign(db, campaign_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


# ────────────────────── Leads ──────────────────────

def _lead_to_dict(l: Lead) -> dict:
    return {
        "id": l.id,
        "name": l.name,
        "phone": l.phone,
        "phone_e164": l.phone_e164,
        "email": l.email,
        "email_valid": l.email_valid,
        "website": l.website,
        "address": l.address,
        "city": l.city,
        "niche": l.niche,
        "rating": l.rating,
        "reviews_count": l.reviews_count,
        "score": l.score,
        "score_reason": l.score_reason,
        "personalization": l.personalization,
        "stage": l.stage,
        "source": l.source,
        "source_id": l.source_id,
        "touches": l.touches,
        "notes": l.notes,
        "created_at": l.created_at.isoformat() if l.created_at else None,
        "last_contact_at": l.last_contact_at.isoformat() if l.last_contact_at else None,
        "last_reply_at": l.last_reply_at.isoformat() if l.last_reply_at else None,
    }


@router.get("/leads")
def api_list_leads(
    stage: str | None = None,
    source: str | None = None,
    min_score: int = 0,
    q: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: str = Depends(require_user),
):
    query = select(Lead)
    if stage: query = query.where(Lead.stage == stage)
    if source: query = query.where(Lead.source == source)
    if min_score > 0: query = query.where(Lead.score >= min_score)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Lead.name.ilike(like), Lead.email.ilike(like), Lead.phone_e164.ilike(like), Lead.website.ilike(like)))
    query = query.order_by(Lead.score.desc().nulls_last()).limit(limit)
    leads = db.execute(query).scalars().all()
    return [_lead_to_dict(l) for l in leads]


# ────────────────────── Export CSV (must be BEFORE /{lead_id}) ──────────────────────

def _fmt_dt(dt) -> str:
    """Formata datetime para `dd/MM/yyyy HH:mm` (legível em Excel PT)."""
    return dt.strftime("%d/%m/%Y %H:%M") if dt else ""


def _fmt_cell(v) -> str:
    """Normaliza valores: None→'', remove quebras de linha que quebram o CSV."""
    if v is None:
        return ""
    s = str(v)
    # Remove newlines (Excel/Sheets em coluna seguinte) e tabs (separador ambíguo)
    s = s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    # Colapsa whitespace múltiplo
    while "  " in s:
        s = s.replace("  ", " ")
    return s.strip()


@router.get("/leads/export")
def api_export_leads(
    stage: str | None = None,
    source: str | None = None,
    min_score: int = 0,
    q: str | None = None,
    campaign: int | None = None,
    db: Session = Depends(get_db),
    user: str = Depends(require_user),
):
    query = select(Lead)
    if stage: query = query.where(Lead.stage == stage)
    if source: query = query.where(Lead.source == source)
    if min_score > 0: query = query.where(Lead.score >= min_score)
    if campaign: query = query.where(Lead.captured_by_campaign_id == campaign)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Lead.name.ilike(like), Lead.email.ilike(like), Lead.phone_e164.ilike(like)))
    leads = db.execute(query.order_by(Lead.score.desc().nulls_last())).scalars().all()

    # Pre-fetch campaign names para juntar a cada linha
    campaign_ids = {l.captured_by_campaign_id for l in leads if l.captured_by_campaign_id}
    campaign_names: dict[int, str] = {}
    if campaign_ids:
        for cid, cname in db.execute(select(Campaign.id, Campaign.name).where(Campaign.id.in_(campaign_ids))).all():
            campaign_names[cid] = cname

    buf = io.StringIO()
    # Separador `;` (Excel PT default), aspas em TODOS os campos → robusto a vírgulas e ponto-e-vírgula no texto
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")

    headers = [
        "ID",
        "Nome / Empresa",
        "Telefone",
        "Email",
        "Email Válido",
        "Website",
        "Cidade",
        "Nicho",
        "Morada",
        "Rating",
        "Nº Reviews",
        "Score IA",
        "Motivo do Score",
        "Personalização IA",
        "Etapa",
        "Fonte",
        "Campanha de Origem",
        "Nº Toques",
        "Último Contacto",
        "Última Resposta",
        "Capturado em",
        "Notas",
    ]
    w.writerow(headers)

    for l in leads:
        w.writerow([
            _fmt_cell(l.id),
            _fmt_cell(l.name),
            _fmt_cell(l.phone_e164 or l.phone),
            _fmt_cell(l.email),
            "Sim" if l.email_valid else ("Não" if l.email else ""),
            _fmt_cell(l.website),
            _fmt_cell(l.city),
            _fmt_cell(l.niche),
            _fmt_cell(l.address),
            _fmt_cell(l.rating),
            _fmt_cell(l.reviews_count),
            _fmt_cell(l.score if l.score is not None else ""),
            _fmt_cell(l.score_reason),
            _fmt_cell(l.personalization),
            _fmt_cell(l.stage),
            _fmt_cell(l.source),
            _fmt_cell(campaign_names.get(l.captured_by_campaign_id, "")),
            _fmt_cell(l.touches),
            _fmt_dt(l.last_contact_at),
            _fmt_dt(l.last_reply_at),
            _fmt_dt(l.created_at),
            _fmt_cell(l.notes),
        ])

    # Prefix BOM UTF-8 para Excel PT abrir com acentos correctos
    content = "﻿" + buf.getvalue()
    filename = f"vvtraffic_leads_{utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/leads/{lead_id}")
def api_get_lead(lead_id: int, db: Session = Depends(get_db), user: str = Depends(require_user)):
    lead = db.get(Lead, lead_id)
    if not lead: raise HTTPException(404)
    return _lead_to_dict(lead)


# ────────────────────── Bulk actions ──────────────────────

class BulkAction(BaseModel):
    ids: list[int]
    action: str  # "stage" | "delete"
    value: str = ""


@router.post("/leads/bulk")
def api_bulk(body: BulkAction, db: Session = Depends(get_db), user: str = Depends(require_user)):
    if not body.ids:
        return {"updated": 0}
    rows = db.execute(select(Lead).where(Lead.id.in_(body.ids))).scalars().all()
    n = 0
    if body.action == "stage":
        if body.value not in {s.value for s in Stage}:
            raise HTTPException(400, "Stage inválida")
        for l in rows:
            l.stage = body.value
            n += 1
    elif body.action == "delete":
        for l in rows:
            db.delete(l); n += 1
    else:
        raise HTTPException(400, "Acção desconhecida")
    db.commit()
    return {"updated": n, "action": body.action, "value": body.value}


# ────────────────────── Notes & manual send ──────────────────────

class NotePayload(BaseModel):
    notes: str


@router.post("/leads/{lead_id}/notes")
def api_update_notes(lead_id: int, body: NotePayload, db: Session = Depends(get_db), user: str = Depends(require_user)):
    lead = db.get(Lead, lead_id)
    if not lead: raise HTTPException(404)
    lead.notes = body.notes
    db.commit()
    return {"ok": True}


class QuickSend(BaseModel):
    channel: str  # "whatsapp" | "email"
    subject: str | None = None
    body: str


@router.post("/leads/{lead_id}/send")
async def api_quick_send(lead_id: int, payload: QuickSend, db: Session = Depends(get_db), user: str = Depends(require_user)):
    lead = db.get(Lead, lead_id)
    if not lead: raise HTTPException(404)

    body_rendered = render_template(payload.body, lead)
    subj_rendered = render_template(payload.subject or "", lead)

    if payload.channel == "whatsapp":
        if not lead.phone_e164:
            raise HTTPException(400, "Lead sem telefone normalizado")
        wa = build_whatsapp()
        if not wa.enabled:
            raise HTTPException(400, "WhatsApp provider não configurado")
        ok, mid, err = await wa.send_text(lead.phone_e164, body_rendered)
        msg = Message(
            lead_id=lead.id, channel="whatsapp", touch_number=(lead.touches or 0) + 1,
            body=body_rendered,
            status="sent" if ok else "failed", provider_id=mid, error=err,
            sent_at=utcnow() if ok else None,
        )
        db.add(msg)
        if ok:
            lead.touches = (lead.touches or 0) + 1
            lead.last_contact_at = utcnow()
            if lead.stage == Stage.NOVO.value:
                lead.stage = Stage.CONTACTADO.value
        db.commit()
        return {"ok": ok, "error": err}

    if payload.channel == "email":
        if not lead.email:
            raise HTTPException(400, "Lead sem email")
        brevo = build_brevo()
        if not brevo.enabled:
            raise HTTPException(400, "Brevo não configurado")
        html = "<p>" + body_rendered.replace("\n", "<br>") + "</p>"
        ok, mid, err = await brevo.send(lead.email, lead.name, subj_rendered or "(sem assunto)", html)
        msg = Message(
            lead_id=lead.id, channel="email", touch_number=(lead.touches or 0) + 1,
            subject=subj_rendered, body=body_rendered,
            status="sent" if ok else "failed", provider_id=mid, error=err,
            sent_at=utcnow() if ok else None,
        )
        db.add(msg)
        if ok:
            lead.touches = (lead.touches or 0) + 1
            lead.last_contact_at = utcnow()
            if lead.stage == Stage.NOVO.value:
                lead.stage = Stage.CONTACTADO.value
        db.commit()
        return {"ok": ok, "error": err}

    raise HTTPException(400, "Canal desconhecido")


# ────────────────────── Database backup ──────────────────────

@router.get("/db/stats")
def api_db_stats(user: str = Depends(require_user)):
    return {"stats": db_stats(), "backups": list_backups()}


@router.post("/db/backup")
def api_db_backup_now(user: str = Depends(require_user)):
    """Força um backup imediato (ignora o cooldown de 20h)."""
    from pathlib import Path
    import sqlite3
    from datetime import datetime

    db_path = _db_path()
    if not db_path or not db_path.exists():
        raise HTTPException(404, "DB não encontrada")

    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"leads_{ts}.db"
    try:
        with sqlite3.connect(str(db_path)) as src:
            with sqlite3.connect(str(backup_file)) as dst:
                src.backup(dst)
    except Exception as e:
        raise HTTPException(500, f"Backup falhou: {e}")
    return {"ok": True, "name": backup_file.name, "size_bytes": backup_file.stat().st_size}


@router.get("/db/download")
def api_db_download(user: str = Depends(require_user)):
    """Descarrega a DB SQLite actual como ficheiro."""
    from datetime import datetime
    db_path = _db_path()
    if not db_path or not db_path.exists():
        raise HTTPException(404, "DB não encontrada")

    ts = utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"vvtraffic_leads_{ts}.db"

    def _iter():
        with open(db_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        _iter(),
        media_type="application/x-sqlite3",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ────────────────────── Health ──────────────────────

@router.get("/health/detailed")
async def api_health(user: str = Depends(require_user)):
    checks = await all_checks()
    overall = "ok"
    for c in checks:
        if c["status"] == "fail":
            overall = "fail"; break
        if c["status"] == "disabled" and overall != "fail":
            overall = "partial"
    return {"overall": overall, "checks": checks}
