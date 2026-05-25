# Sistema de Leads V2 — VV TRAFFIC DATA

Sistema de prospecção automática + CRM, **versão definitiva** em Python.
Substitui o Google Apps Script (`../Codigo.gs`) por um backend robusto, dashboard web próprio, IA grátis para qualificação/personalização, deduplicação automática, follow-up multi-toque e webhooks para detectar respostas.

> Stack: **FastAPI · SQLite · APScheduler · Jinja2 · Gemini 2.0 Flash · Hunter.io · Brevo · Evolution/Z-API · Apify**

---

## ⚡ Quick start (Windows, 1 minuto)

1. Instalar [Python 3.11+](https://www.python.org/downloads/) (na instalação marcar "Add Python to PATH").
2. Duplo clique em **`start.bat`**.
3. Na primeira execução abre o `.env` no Notepad — preencher as chaves API que já tens da Sheet antiga.
4. Voltar a correr `start.bat` → abre o servidor.
5. Browser → http://127.0.0.1:8000 → user/pass de `.env` (`admin` / `change-me` por defeito).

---

## 🧭 Como usar (3 cliques)

1. Painel → **Nova campanha**.
2. Indicar `nicho` (ex: clínica dentária) + `cidade` (ex: Lisboa) + escolher templates ou aceitar os default.
3. Botão **Lançar** → o sistema:
   - busca em paralelo no Google Maps + LinkedIn + Instagram
   - faz dedup (não repete leads que já estão na BD)
   - enriquece email com Hunter.io
   - valida sintaxe + MX record do email (free)
   - qualifica com IA Gemini (score 0-100) + razão
   - gera 1 frase de abertura específica para cada lead
   - envia WhatsApp + email (respeitando limites diários anti-bloqueio)
   - regista tudo

4. Painel mostra: leads novos, enviados hoje, respostas, funil por etapa.

---

## 📦 Estrutura

```
v2/
├── app/
│   ├── main.py                 # FastAPI app + lifecycle
│   ├── config.py               # Pydantic settings (.env)
│   ├── database.py             # SQLAlchemy engine
│   ├── models.py               # Lead, Campaign, Message, EventLog
│   ├── utils.py                # phone, dedup hash, logger
│   ├── deps.py                 # auth basic
│   ├── routes/
│   │   ├── dashboard.py        # HTML: /, /leads, /campaigns/new
│   │   ├── api.py              # JSON: /api/* (integrar com n8n/Apps Script)
│   │   └── webhooks.py         # /webhooks/brevo, /webhooks/whatsapp
│   ├── services/
│   │   ├── scrapers/           # google_maps, apify_linkedin, apify_instagram
│   │   ├── enrichment/         # hunter, email_validator
│   │   ├── ai/                 # gemini, qualifier, personalizer, classifier
│   │   ├── messaging/          # brevo, whatsapp, templating
│   │   └── pipeline.py         # orquestração: capture + send
│   ├── workers/scheduler.py    # APScheduler (follow-ups diários)
│   ├── templates/              # base, dashboard, leads, lead_detail, campaign_*
│   └── static/css/app.css
├── scripts/
│   └── import_sheets_csv.py    # importa CSV do Sheets antigo
├── data/                       # SQLite + logs (não commitar)
├── tests/
├── requirements.txt
├── .env.example
├── start.bat                   # launcher Windows
└── README.md
```

---

## 🔑 Variáveis de ambiente importantes

Edita `.env` (criado automaticamente a partir de `.env.example` na primeira execução).

### Obrigatórias para capturar leads
- `GOOGLE_PLACES_API_KEY` — copia da Sheet antiga
- `APIFY_API_TOKEN` — copia da Sheet antiga
- `HUNTER_API_KEY` — copia da Sheet antiga

### Obrigatórias para disparar
- `BREVO_API_KEY` — copia da Sheet antiga
- Para WhatsApp escolhe **um** provider em `WHATSAPP_PROVIDER`:
  - `evolution` (recomendado, self-hosted, free) → preencher `EVOLUTION_BASE_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`
  - `zapi` (cloud trial) → preencher `ZAPI_INSTANCE_ID`, `ZAPI_TOKEN`, `ZAPI_CLIENT_TOKEN`

### Recomendado (IA grátis)
- `GEMINI_API_KEY` — cria conta em https://aistudio.google.com → 1M tokens/dia free, ideal para personalização + qualificação

### Anti-bloqueio (defaults sensatos)
- `WHATSAPP_MAX_PER_DAY=50` — começa em 30, sobe gradualmente
- `EMAIL_MAX_PER_DAY=100` — warm-up de domínio
- `SEND_DELAY_MS=1500` — pausa entre mensagens

---

## 🔄 Migrar leads do sistema antigo

```powershell
# 1. Na Google Sheet antiga: Ficheiro → Descarregar → CSV (aba Leads)
# 2. Guardar como data\import.csv
# 3. Correr:
.\.venv\Scripts\activate.bat
python -m scripts.import_sheets_csv data\import.csv
```

Os duplicados são detectados pelo hash (nome+telefone+website+email) e ignorados.

---

## 🌐 Expor webhooks com ngrok (para detectar respostas)

Para Brevo e Evolution/Z-API conseguirem mandar notificações ao teu PC local:

```powershell
# Instalar ngrok: https://ngrok.com/download
ngrok http 8000
```

Copiar o URL `https://abc123.ngrok-free.app` e configurar:
- Brevo → Settings → Webhooks → URL: `https://abc123.ngrok-free.app/webhooks/brevo`
- Evolution/Z-API → Webhook URL: `https://abc123.ngrok-free.app/webhooks/whatsapp`

Quando alguém responde, o sistema:
1. Marca a mensagem como `replied`
2. Classifica com IA (interessado / pedir_remover / objeção / irrelevante)
3. Move o lead para a etapa correcta automaticamente (`Reunião`, `Blacklist`, `Follow-up`)

---

## 🤖 Cron automático

O scheduler corre dentro do próprio servidor — basta `start.bat` estar aberto.
- **09:00 (Lisboa)** — verifica follow-ups pendentes (D2/D4/D7/D10 desde último contacto)

Para escalar a 500 leads/dia depois, migrar para cloud (Railway/Render/VPS) — o código já está pronto, é só copiar os ficheiros e correr `uvicorn app.main:app` lá.

---

## 🛣 Roadmap dentro deste repo

- [x] Captação multi-fonte (Maps + LinkedIn + Instagram)
- [x] Dedup cross-source
- [x] Hunter.io + validação email
- [x] IA Gemini para qualificação + personalização + classificação de respostas
- [x] Disparo Brevo + Evolution/Z-API com limites diários
- [x] Dashboard HTML (painel, leads, lead detail, campanhas)
- [x] Webhooks de respostas
- [x] Scheduler de follow-ups
- [x] CLI para importar Sheets antigo
- [ ] Páginas Amarelas PT scraper (próxima feature)
- [ ] Racius.com / einforma.pt scraper
- [ ] Multi-number WhatsApp rotation
- [ ] A/B testing automático de copy
- [ ] Integração Calendly (agendamento auto na resposta "sim")

---

## 🧪 Testar localmente sem chaves

Sem chaves preenchidas, o sistema ainda inicia e o dashboard funciona — só não consegue capturar/enviar. O CLI de import permite ver o frontend com dados reais antes de configurar as APIs.

---

## ❓ Troubleshooting

- **"Python não encontrado"** — instalar Python 3.11+ e na instalação marcar "Add Python to PATH"
- **WhatsApp 401 Unauthorized** — `EVOLUTION_API_KEY` errado, ou Z-API desconectado (re-scan QR code no painel Z-API)
- **Brevo 401** — chave API expirou, gerar nova em brevo.com → SMTP & API
- **Sem leads no Google Maps** — verificar que `GOOGLE_PLACES_API_KEY` tem `Places API` activa no Google Cloud Console
- **Emails vão para spam** — falta SPF/DKIM/DMARC no domínio remetente. Ver `../PLANO-ESCALA-V2.md` secção 8.

---

*VV TRAFFIC DATA · Sistema de Leads V2 · v2.0.0*
