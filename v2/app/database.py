from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from .config import settings


class Base(DeclarativeBase):
    pass


if settings.DATABASE_URL.startswith("sqlite"):
    Path("data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  — register models
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def _migrate_sqlite() -> None:
    """Migração leve para SQLite: adiciona colunas novas que faltam.
    Idempotente — pode correr em todo o arranque."""
    from sqlalchemy import inspect, text

    if not str(engine.url).startswith("sqlite"):
        return

    insp = inspect(engine)
    if "campaigns" not in insp.get_table_names():
        return

    cols_campaigns = {c["name"] for c in insp.get_columns("campaigns")}
    cols_leads = {c["name"] for c in insp.get_columns("leads")} if "leads" in insp.get_table_names() else set()
    cols_eventlog = {c["name"] for c in insp.get_columns("event_log")} if "event_log" in insp.get_table_names() else set()

    migrations = [
        ("campaigns", "max_leads", "INTEGER DEFAULT 60", cols_campaigns),
        ("campaigns", "expand_variations", "BOOLEAN DEFAULT 1", cols_campaigns),
        ("campaigns", "dry_run", "BOOLEAN DEFAULT 0", cols_campaigns),
        ("leads", "captured_by_campaign_id", "INTEGER REFERENCES campaigns(id)", cols_leads),
        ("leads", "next_followup_at", "DATETIME", cols_leads),
        ("leads", "tags", "VARCHAR(500)", cols_leads),
        ("leads", "score_fit", "INTEGER", cols_leads),
        ("leads", "score_intent", "INTEGER", cols_leads),
        ("leads", "score_reachability", "INTEGER", cols_leads),
        ("event_log", "actor", "VARCHAR(120)", cols_eventlog),
    ]
    with engine.begin() as conn:
        for table, col, ddl, existing in migrations:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
