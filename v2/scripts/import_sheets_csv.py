"""Importa leads do Sheets antigo via CSV.

USO:
  1. Na Google Sheet antiga: Ficheiro → Descarregar → CSV (aba Leads)
  2. Coloca o ficheiro em data/import.csv (ou passa o caminho como argumento)
  3. python -m scripts.import_sheets_csv data/import.csv

O CSV esperado tem o cabeçalho do Codigo.gs:
  Data Adição, Fonte, Nome/Empresa, Website, Telefone/WhatsApp,
  E-mail, Endereço/Localização, Avaliação, Nº Avaliações, Status,
  Email Enviado, WhatsApp Enviado, ID/URL Fonte
"""

import csv
import sys
from pathlib import Path

# Permitir execução directa: `python scripts/import_sheets_csv.py ...`
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal, init_db
from app.models import Lead, Stage
from app.utils import dedup_hash, normalize_phone, normalize_website
from app.config import settings


def import_csv(path: str) -> int:
    init_db()
    db = SessionLocal()
    added = skipped = 0
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                if len(row) < 13:
                    continue
                source = (row[1] or "import").lower().replace(" ", "_")
                name = row[2]
                website = normalize_website(row[3])
                phone = row[4]
                email = (row[5] or "").strip().lower() or None
                address = row[6]
                rating = float(row[7]) if row[7] else None
                reviews_count = int(row[8]) if row[8] else None
                source_id = row[12] or None

                phone_e164 = normalize_phone(phone, settings.SENDER_COUNTRY_CODE)
                h = dedup_hash(name, phone, website, email)

                existing = db.query(Lead).filter(Lead.dedup_hash == h).first()
                if existing:
                    skipped += 1
                    continue

                lead = Lead(
                    source=source,
                    source_id=source_id,
                    dedup_hash=h,
                    name=name,
                    website=website,
                    phone=phone,
                    phone_e164=phone_e164,
                    email=email,
                    email_valid=bool(email),
                    address=address,
                    rating=rating,
                    reviews_count=reviews_count,
                    stage=Stage.NOVO.value,
                )
                db.add(lead)
                added += 1

        db.commit()
    finally:
        db.close()
    return added, skipped


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "data/import.csv"
    if not Path(src).exists():
        print(f"Ficheiro não encontrado: {src}")
        sys.exit(1)
    added, skipped = import_csv(src)
    print(f"Importados: {added}  ·  Ignorados (duplicados): {skipped}")
