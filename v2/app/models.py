from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """Timezone-aware UTC now (substitui datetime.utcnow deprecated em Py3.12+)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Stage(str, Enum):
    NOVO = "novo"
    CONTACTADO = "contactado"
    FOLLOWUP = "followup"
    REUNIAO = "reuniao"
    PROPOSTA = "proposta"
    CLIENTE = "cliente"
    ARQUIVO = "arquivo"
    BLACKLIST = "blacklist"


class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class MessageStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    REPLIED = "replied"


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("dedup_hash", name="uq_leads_dedup"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    source: Mapped[str] = mapped_column(String(50), index=True)  # google_maps, linkedin, paginas_amarelas, ...
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedup_hash: Mapped[str] = mapped_column(String(64), index=True)
    captured_by_campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_valid: Mapped[bool] = mapped_column(Boolean, default=False)

    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    niche: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviews_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    stage: Mapped[str] = mapped_column(String(20), default=Stage.NOVO.value, index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 0-100
    score_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    personalization: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    touches: Mapped[int] = mapped_column(Integer, default=0)
    last_reply_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)  # csv: "vip,interessado"

    # Scoring multi-dimensional
    score_fit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_intent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_reachability: Mapped[int | None] = mapped_column(Integer, nullable=True)

    messages: Mapped[list["Message"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    notes_history: Mapped[list["LeadNote"]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    name: Mapped[str] = mapped_column(String(255))
    niche: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(120))

    template_whatsapp: Mapped[str] = mapped_column(Text)
    template_email_subject: Mapped[str] = mapped_column(String(255))
    template_email_body: Mapped[str] = mapped_column(Text)

    use_ai_personalization: Mapped[bool] = mapped_column(Boolean, default=True)
    expand_variations: Mapped[bool] = mapped_column(Boolean, default=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    min_score: Mapped[int] = mapped_column(Integer, default=0)
    max_leads: Mapped[int] = mapped_column(Integer, default=60)

    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft, capturing, sending, done
    leads_captured: Mapped[int] = mapped_column(Integer, default=0)
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)

    channel: Mapped[str] = mapped_column(String(20), index=True)  # whatsapp / email
    direction: Mapped[str] = mapped_column(String(10), default="out")  # out / in
    touch_number: Mapped[int] = mapped_column(Integer, default=1)  # 1, 2, 3...

    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(20), default=MessageStatus.PENDING.value, index=True)
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    lead: Mapped[Lead] = relationship(back_populates="messages")


class EventLog(Base):
    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    source: Mapped[str] = mapped_column(String(60), index=True)
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)


# ───────────────────────── Sequência de follow-up ─────────────────────────

class CampaignTouch(Base):
    """Template de mensagem para um toque específico de uma campanha (touch 1..5)."""
    __tablename__ = "campaign_touches"
    __table_args__ = (UniqueConstraint("campaign_id", "touch_number", name="uq_touch"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    touch_number: Mapped[int] = mapped_column(Integer)  # 1..5
    delay_days: Mapped[int] = mapped_column(Integer, default=0)  # dias após touch anterior
    channel: Mapped[str] = mapped_column(String(20), default="both")
    template_whatsapp: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_email_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_email_body: Mapped[str | None] = mapped_column(Text, nullable=True)


# ───────────────────────── Notas (histórico append-only) ─────────────────────────

class LeadNote(Base):
    __tablename__ = "lead_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    author: Mapped[str] = mapped_column(String(120), default="admin")
    body: Mapped[str] = mapped_column(Text)

    lead: Mapped[Lead] = relationship(back_populates="notes_history")


# ───────────────────────── Templates reutilizáveis ─────────────────────────

class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    name: Mapped[str] = mapped_column(String(120))
    niche: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20))  # whatsapp / email
    touch_number: Mapped[int] = mapped_column(Integer, default=1)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text)


# ───────────────────────── Filtros guardados ─────────────────────────

class SavedFilter(Base):
    __tablename__ = "saved_filters"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    name: Mapped[str] = mapped_column(String(120))
    params: Mapped[str] = mapped_column(Text)  # JSON-encoded query params


# Índices em campos de pesquisa frequente
Index("ix_messages_provider", Message.provider_id)
