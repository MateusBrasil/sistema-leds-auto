"""Backup automático da SQLite DB.

- Faz cópia no arranque se a DB tem leads e o último backup foi há >24h.
- Mantém últimos N backups, apaga os mais antigos.
- Inclui endpoint para descarregar a DB actual via API.
"""

import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger
from ..models import utcnow

from ..config import settings


BACKUP_DIR = Path("data/backups")
MAX_BACKUPS = 7
MIN_INTERVAL_HOURS = 20  # não faz backup se já houve um nas últimas 20h


def _db_path() -> Path | None:
    """Devolve o Path da DB SQLite ou None se não for SQLite."""
    url = settings.DATABASE_URL
    if not url.startswith("sqlite"):
        return None
    # sqlite:///./data/leads.db  →  ./data/leads.db
    rel = url.replace("sqlite:///", "")
    return Path(rel)


def _count_leads(db_path: Path) -> int:
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM leads")
            return cur.fetchone()[0]
    except Exception:
        return 0


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    files = sorted(BACKUP_DIR.glob("leads_*.db"), reverse=True)
    return [
        {
            "name": f.name,
            "path": str(f),
            "size_bytes": f.stat().st_size,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime),
        }
        for f in files
    ]


def auto_backup_on_startup() -> str | None:
    """Cria backup se condições cumpridas. Devolve nome do backup criado ou None."""
    db_path = _db_path()
    if not db_path or not db_path.exists():
        return None

    leads_count = _count_leads(db_path)
    if leads_count == 0:
        logger.info("Backup skipped: DB has no leads yet")
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Skip se backup recente
    existing = list_backups()
    if existing:
        last_age = utcnow() - existing[0]["created_at"]
        if last_age < timedelta(hours=MIN_INTERVAL_HOURS):
            logger.info("Backup skipped: last backup was {:.1f}h ago", last_age.total_seconds() / 3600)
            return None

    # Cria backup usando o SQLite backup API (consistente mesmo se a DB estiver em uso)
    ts = utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"leads_{ts}.db"
    try:
        with sqlite3.connect(str(db_path)) as src:
            with sqlite3.connect(str(backup_file)) as dst:
                src.backup(dst)
        size_kb = backup_file.stat().st_size / 1024
        logger.info("Backup criado: {} ({:.0f} KB, {} leads)", backup_file.name, size_kb, leads_count)
    except Exception as e:
        logger.error("Backup falhou: {}", e)
        return None

    # Rotação: apaga mais antigos que MAX_BACKUPS
    backups_after = list_backups()
    if len(backups_after) > MAX_BACKUPS:
        for old in backups_after[MAX_BACKUPS:]:
            try:
                Path(old["path"]).unlink()
                logger.info("Backup antigo removido: {}", old["name"])
            except Exception as e:
                logger.warning("Falha ao remover {}: {}", old["name"], e)

    return backup_file.name


def db_stats() -> dict:
    """Estatísticas para a UI."""
    db_path = _db_path()
    if not db_path or not db_path.exists():
        return {"exists": False, "size_bytes": 0, "leads_count": 0, "path": str(db_path) if db_path else None}
    return {
        "exists": True,
        "path": str(db_path.absolute()),
        "size_bytes": db_path.stat().st_size,
        "leads_count": _count_leads(db_path),
        "modified_at": datetime.fromtimestamp(db_path.stat().st_mtime),
    }
