"""Endpoints API adicionais (Sprint 3+):
- Notas append-only com histórico
- Tags
- Templates library
- Filtros guardados
- CSV upload
- Métricas avançadas
- Trigger follow-up manual
- Test notify
- AI objection handling
"""

import csv
import io
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_user
from ..models import (
    Lead, Campaign, Message, LeadNote, MessageTemplate, SavedFilter, EventLog,
    Stage, MessageStatus, utcnow,
)
from ..utils import dedup_hash, normalize_phone, normalize_website
from ..config import settings


router = APIRouter(prefix="/api", tags=["extras"])


# ────────────────────── Notas histórico ──────────────────────

class NoteCreate(BaseModel):
    body: str


@router.get("/leads/{lead_id}/notes/history")
def list_notes(lead_id: int, db: Session = Depends(get_db), user: str = Depends(require_user)):
    rows = db.execute(
        select(LeadNote).where(LeadNote.lead_id == lead_id).order_by(desc(LeadNote.created_at))
    ).scalars().all()
    return [
        {"id": n.id, "body": n.body, "author": n.author, "created_at": n.created_at.isoformat()}
        for n in rows
    ]


@router.post("/leads/{lead_id}/notes/history")
def add_note(lead_id: int, payload: NoteCreate, db: Session = Depends(get_db), user: str = Depends(require_user)):
    if not db.get(Lead, lead_id):
        raise HTTPException(404, "Lead não encontrado")
    note = LeadNote(lead_id=lead_id, body=payload.body.strip(), author=user)
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"id": note.id, "created_at": note.created_at.isoformat()}


# ────────────────────── Tags ──────────────────────

class TagsPayload(BaseModel):
    tags: list[str]


@router.post("/leads/{lead_id}/tags")
def set_tags(lead_id: int, payload: TagsPayload, db: Session = Depends(get_db), user: str = Depends(require_user)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404)
    clean = sorted({t.strip().lower() for t in payload.tags if t.strip()})
    lead.tags = ",".join(clean) if clean else None
    db.commit()
    return {"tags": clean}


# ────────────────────── Templates library ──────────────────────

class TemplateCreate(BaseModel):
    name: str
    niche: str | None = None
    channel: str  # whatsapp/email
    touch_number: int = 1
    subject: str | None = None
    body: str


@router.get("/templates")
def list_templates(channel: str | None = None, niche: str | None = None,
                   db: Session = Depends(get_db), user: str = Depends(require_user)):
    q = select(MessageTemplate)
    if channel: q = q.where(MessageTemplate.channel == channel)
    if niche: q = q.where(MessageTemplate.niche == niche)
    q = q.order_by(desc(MessageTemplate.created_at))
    rows = db.execute(q).scalars().all()
    return [
        {"id": t.id, "name": t.name, "niche": t.niche, "channel": t.channel,
         "touch_number": t.touch_number, "subject": t.subject, "body": t.body,
         "created_at": t.created_at.isoformat()}
        for t in rows
    ]


@router.post("/templates")
def create_template(payload: TemplateCreate, db: Session = Depends(get_db), user: str = Depends(require_user)):
    t = MessageTemplate(**payload.model_dump())
    db.add(t); db.commit(); db.refresh(t)
    return {"id": t.id}


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db), user: str = Depends(require_user)):
    t = db.get(MessageTemplate, template_id)
    if not t: raise HTTPException(404)
    db.delete(t); db.commit()
    return {"ok": True}


# ────────────────────── Filtros guardados ──────────────────────

class SavedFilterCreate(BaseModel):
    name: str
    params: dict


@router.get("/filters")
def list_filters(db: Session = Depends(get_db), user: str = Depends(require_user)):
    rows = db.execute(select(SavedFilter).order_by(desc(SavedFilter.created_at))).scalars().all()
    return [
        {"id": f.id, "name": f.name, "params": json.loads(f.params or "{}"),
         "created_at": f.created_at.isoformat()}
        for f in rows
    ]


@router.post("/filters")
def create_filter(payload: SavedFilterCreate, db: Session = Depends(get_db), user: str = Depends(require_user)):
    f = SavedFilter(name=payload.name, params=json.dumps(payload.params))
    db.add(f); db.commit(); db.refresh(f)
    return {"id": f.id}


@router.delete("/filters/{filter_id}")
def delete_filter(filter_id: int, db: Session = Depends(get_db), user: str = Depends(require_user)):
    f = db.get(SavedFilter, filter_id)
    if not f: raise HTTPException(404)
    db.delete(f); db.commit()
    return {"ok": True}


# ────────────────────── CSV Upload ──────────────────────

@router.post("/leads/import")
async def import_leads_csv(file: UploadFile = File(...), db: Session = Depends(get_db), user: str = Depends(require_user)):
    """Importa leads de CSV. Aceita colunas comuns (nome, telefone, email, website, etc.)
    Detecção heurística do separador (`,` ou `;`) e dos nomes de coluna PT/EN."""
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # remove BOM if present
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # Detecta delimiter
    sniffer = csv.Sniffer()
    sample = text[:4096]
    try:
        dialect = sniffer.sniff(sample, delimiters=";,\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    # Mapping case-insensitive de cabeçalhos
    field_map = {
        "name": ["nome", "nome / empresa", "empresa", "name", "company"],
        "phone": ["telefone", "phone", "telemovel", "tel", "whatsapp"],
        "email": ["email", "e-mail", "mail"],
        "website": ["website", "site", "url", "web"],
        "city": ["cidade", "city", "localidade"],
        "niche": ["nicho", "niche", "categoria"],
        "address": ["morada", "address", "endereço", "endereco"],
    }

    def find_value(row: dict, keys: list[str]) -> str | None:
        for k in keys:
            for col, val in row.items():
                if col and col.strip().lower() == k:
                    return val.strip() if val else None
        return None

    added = skipped = errors = 0
    rows_processed = 0
    for row in reader:
        rows_processed += 1
        try:
            name = find_value(row, field_map["name"])
            if not name or len(name) < 2:
                skipped += 1; continue
            phone = find_value(row, field_map["phone"])
            email = find_value(row, field_map["email"])
            website = normalize_website(find_value(row, field_map["website"]))
            phone_e164 = normalize_phone(phone, settings.SENDER_COUNTRY_CODE)
            email = email.lower() if email else None
            h = dedup_hash(name, phone, website, email)

            # Dedup
            exists = db.execute(select(Lead.id).where(Lead.dedup_hash == h)).scalar_one_or_none()
            if exists:
                skipped += 1; continue

            lead = Lead(
                source="csv_import",
                source_id=None,
                dedup_hash=h,
                name=name,
                phone=phone,
                phone_e164=phone_e164,
                email=email,
                email_valid=bool(email and "@" in email),
                website=website,
                address=find_value(row, field_map["address"]),
                city=find_value(row, field_map["city"]),
                niche=find_value(row, field_map["niche"]),
                stage=Stage.NOVO.value,
            )
            db.add(lead)
            added += 1
        except Exception:
            errors += 1
    db.commit()

    # Audit
    db.add(EventLog(level="INFO", source="csv_import", actor=user,
                    message=f"Import CSV '{file.filename}': {added} novos, {skipped} duplicados, {errors} erros"))
    db.commit()

    return {"added": added, "skipped": skipped, "errors": errors, "rows": rows_processed}


# ────────────────────── Métricas avançadas ──────────────────────

@router.get("/metrics")
def metrics(period_days: int = 30, db: Session = Depends(get_db), user: str = Depends(require_user)):
    """Métricas para a página /analytics."""
    cutoff = utcnow() - timedelta(days=period_days)

    total = db.execute(select(func.count(Lead.id))).scalar_one()
    new = db.execute(select(func.count(Lead.id)).where(Lead.created_at >= cutoff)).scalar_one()
    contacted = db.execute(select(func.count(Lead.id)).where(Lead.last_contact_at >= cutoff)).scalar_one()
    replied = db.execute(select(func.count(Lead.id)).where(Lead.last_reply_at >= cutoff)).scalar_one()

    # Time-to-reply (em horas)
    ttr_rows = db.execute(
        select(Lead.last_contact_at, Lead.last_reply_at)
        .where(Lead.last_contact_at.isnot(None), Lead.last_reply_at.isnot(None))
        .where(Lead.last_reply_at >= cutoff)
    ).all()
    ttr_hours = [(r[1] - r[0]).total_seconds() / 3600 for r in ttr_rows if r[1] > r[0]]
    avg_ttr = sum(ttr_hours) / len(ttr_hours) if ttr_hours else 0
    median_ttr = sorted(ttr_hours)[len(ttr_hours) // 2] if ttr_hours else 0

    # Reply rate por nicho
    by_niche = db.execute(
        select(
            Lead.niche,
            func.count(Lead.id).label("total"),
            func.sum(func.iif(Lead.last_reply_at.isnot(None), 1, 0)).label("replied"),
        )
        .where(Lead.niche.isnot(None), Lead.created_at >= cutoff)
        .group_by(Lead.niche)
        .order_by(desc(func.count(Lead.id)))
        .limit(10)
    ).all()

    # Funnel
    funnel_stages = [s.value for s in Stage]
    funnel = dict(db.execute(
        select(Lead.stage, func.count(Lead.id))
        .group_by(Lead.stage)
    ).all())

    # Por fonte
    by_source = dict(db.execute(
        select(Lead.source, func.count(Lead.id))
        .where(Lead.created_at >= cutoff)
        .group_by(Lead.source)
    ).all())

    return {
        "period_days": period_days,
        "total_leads": total,
        "new_leads": new,
        "contacted": contacted,
        "replied": replied,
        "reply_rate": (replied / contacted * 100) if contacted else 0,
        "avg_time_to_reply_hours": round(avg_ttr, 1),
        "median_time_to_reply_hours": round(median_ttr, 1),
        "by_niche": [
            {"niche": n, "total": t, "replied": r or 0, "reply_rate": (r / t * 100) if t else 0}
            for n, t, r in by_niche
        ],
        "by_source": by_source,
        "funnel": {s: funnel.get(s, 0) for s in funnel_stages},
    }


# ────────────────────── Follow-up manual ──────────────────────

@router.post("/followups/run")
async def trigger_followups(user: str = Depends(require_user)):
    """Dispara o ciclo de follow-up imediatamente (em vez de esperar 9h Lisboa)."""
    from ..workers.scheduler import run_followups_now
    result = await run_followups_now()
    return result


# ────────────────────── Test notifications ──────────────────────

@router.post("/notify/test")
async def test_notify(user: str = Depends(require_user)):
    from ..services.notify import notify_test
    return await notify_test()


# ────────────────────── AI: Objection handling ──────────────────────

class ObjectionPayload(BaseModel):
    objection: str
    lead_id: int | None = None


@router.post("/ai/objection-handler")
async def ai_objection_handler(payload: ObjectionPayload, db: Session = Depends(get_db), user: str = Depends(require_user)):
    """Gera resposta sugerida para uma objeção do lead."""
    from ..services.pipeline import build_gemini
    gemini = build_gemini()
    if not gemini.enabled:
        return {"response": "(Gemini não configurado — adiciona GEMINI_API_KEY no .env)"}

    lead_context = ""
    if payload.lead_id:
        lead = db.get(Lead, payload.lead_id)
        if lead:
            lead_context = f"\nContexto do lead: {lead.name} · {lead.niche or '?'} · {lead.city or '?'}"

    prompt = f"""És copywriter de prospecção numa agência de tráfego pago em Portugal.
Um lead respondeu com a seguinte OBJEÇÃO:

"{payload.objection}"
{lead_context}

Escreve UMA resposta curta (40-80 palavras), tom profissional mas próximo, em PT-PT, que:
- Reconheça a objeção sem ser defensivo
- Reframe a perspectiva (custo → investimento, sem tempo → 15min, "já tenho marketing" → "complemento")
- Termina com uma micro-pergunta concreta para reativar o diálogo

Devolve APENAS o texto da resposta, sem aspas, sem prefixos."""

    response = await gemini.generate(prompt, max_tokens=300)
    return {"response": response or "(IA não respondeu — tenta novamente)"}


# ────────────────────── Pesquisa avançada ──────────────────────

@router.get("/search/leads")
def advanced_search(q: str, limit: int = 50, db: Session = Depends(get_db), user: str = Depends(require_user)):
    """Pesquisa com operadores: `score>70 city:Lisboa niche:dentista`.

    Suporta:
    - `score>N` / `score<N` / `score>=N`
    - `city:X`, `niche:X`, `source:X`, `stage:X`, `tag:X`
    - `has:phone` / `has:email`
    - texto livre (procura em name+email+phone+website)
    """
    import re
    base = select(Lead)
    free_text = q

    # score>X
    for op, sym in [(">=", "ge"), ("<=", "le"), (">", "gt"), ("<", "lt"), ("=", "eq")]:
        m = re.search(rf"score\s*{re.escape(op)}\s*(\d+)", q)
        if m:
            val = int(m.group(1))
            if sym == "gt": base = base.where(Lead.score > val)
            elif sym == "lt": base = base.where(Lead.score < val)
            elif sym == "ge": base = base.where(Lead.score >= val)
            elif sym == "le": base = base.where(Lead.score <= val)
            elif sym == "eq": base = base.where(Lead.score == val)
            free_text = free_text.replace(m.group(0), "").strip()
            break

    # field:value
    for field, col in [("city", Lead.city), ("niche", Lead.niche), ("source", Lead.source),
                       ("stage", Lead.stage), ("tag", Lead.tags)]:
        m = re.search(rf"{field}:(\S+)", free_text)
        if m:
            val = m.group(1)
            base = base.where(col.ilike(f"%{val}%"))
            free_text = free_text.replace(m.group(0), "").strip()

    # has:X
    for m in re.finditer(r"has:(\w+)", free_text):
        what = m.group(1).lower()
        if what == "phone": base = base.where(Lead.phone_e164.isnot(None))
        elif what == "email": base = base.where(Lead.email.isnot(None))
        elif what == "website": base = base.where(Lead.website.isnot(None))
    free_text = re.sub(r"has:\w+", "", free_text).strip()

    # Free text
    if free_text:
        from sqlalchemy import or_
        like = f"%{free_text}%"
        base = base.where(or_(
            Lead.name.ilike(like), Lead.email.ilike(like),
            Lead.phone_e164.ilike(like), Lead.website.ilike(like),
        ))

    rows = db.execute(base.order_by(Lead.score.desc().nulls_last()).limit(limit)).scalars().all()
    return [
        {"id": l.id, "name": l.name, "city": l.city, "niche": l.niche,
         "score": l.score, "stage": l.stage, "source": l.source,
         "phone_e164": l.phone_e164, "email": l.email}
        for l in rows
    ]


# ────────────────────── Audit log ──────────────────────

@router.get("/audit")
def audit_log(limit: int = 100, source: str | None = None, db: Session = Depends(get_db), user: str = Depends(require_user)):
    q = select(EventLog).order_by(desc(EventLog.created_at)).limit(limit)
    if source:
        q = select(EventLog).where(EventLog.source == source).order_by(desc(EventLog.created_at)).limit(limit)
    rows = db.execute(q).scalars().all()
    return [
        {"id": e.id, "created_at": e.created_at.isoformat(),
         "level": e.level, "source": e.source, "actor": e.actor,
         "message": e.message}
        for e in rows
    ]
