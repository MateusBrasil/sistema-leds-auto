"""Live health checks de cada integração externa.

Cada check devolve {name, status: 'ok'|'fail'|'disabled', message, hint, latency_ms}.
A mensagem é técnica; a hint é accionável (o que fazer para arranjar).
"""

import asyncio
import time
from typing import TypedDict

import httpx

from ..config import settings


class CheckResult(TypedDict):
    name: str
    status: str
    message: str
    hint: str | None
    latency_ms: int | None


async def _measure(coro):
    t0 = time.perf_counter()
    try:
        ok, msg, hint = await coro
        return ok, msg, hint, int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"[:200], "Verifica conexão à internet ou logs em data/app.log", int((time.perf_counter() - t0) * 1000)


def _disabled(name: str, env_key: str) -> CheckResult:
    return {
        "name": name, "status": "disabled",
        "message": f"Sem chave configurada (.env {env_key})",
        "hint": None, "latency_ms": None,
    }


async def _google_places() -> CheckResult:
    if not settings.GOOGLE_PLACES_API_KEY:
        return _disabled("Google Places", "GOOGLE_PLACES_API_KEY")

    async def _do():
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={"query": "lisboa", "key": settings.GOOGLE_PLACES_API_KEY},
            )
            data = r.json()
            status = data.get("status", "?")
            if status in ("OK", "ZERO_RESULTS"):
                return True, f"Pronta · status {status}", None
            if status == "REQUEST_DENIED":
                return False, "REQUEST_DENIED — chave inválida ou Places API não activa", "console.cloud.google.com → APIs & Services → activar 'Places API' no projecto desta chave"
            if status == "OVER_QUERY_LIMIT":
                return False, "OVER_QUERY_LIMIT — passou o limite gratuito mensal", "Activar billing no Google Cloud (até 6600 buscas grátis depois 17€/1000)"
            return False, f"status={status} · {data.get('error_message', '')[:120]}", None

    ok, msg, hint, ms = await _measure(_do())
    return {"name": "Google Places", "status": "ok" if ok else "fail", "message": msg, "hint": hint, "latency_ms": ms}


async def _hunter() -> CheckResult:
    if not settings.HUNTER_API_KEY:
        return _disabled("Hunter.io", "HUNTER_API_KEY")

    async def _do():
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://api.hunter.io/v2/account",
                params={"api_key": settings.HUNTER_API_KEY},
            )
            if r.status_code == 200:
                d = r.json().get("data", {})
                used = d.get("calls", {}).get("used", 0)
                total = d.get("calls", {}).get("available", 0)
                plan = d.get("plan_name", "free")
                pct = (used / total * 100) if total else 0
                hint = None
                if pct > 90:
                    hint = "Quota quase esgotada — upgrade em hunter.io/api ou esperar reset mensal"
                return True, f"Plano {plan} · {used}/{total} buscas ({pct:.0f}%)", hint
            if r.status_code == 401:
                return False, "401 — API key inválida ou expirada", "Regenerar key em hunter.io → API → New API key"
            return False, f"HTTP {r.status_code}: {r.text[:140]}", None

    ok, msg, hint, ms = await _measure(_do())
    return {"name": "Hunter.io", "status": "ok" if ok else "fail", "message": msg, "hint": hint, "latency_ms": ms}


async def _brevo() -> CheckResult:
    if not settings.BREVO_API_KEY:
        return _disabled("Brevo (Email)", "BREVO_API_KEY")

    async def _do():
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://api.brevo.com/v3/account",
                headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
            )
            if r.status_code == 200:
                d = r.json()
                email = d.get("email", "?")
                plan = (d.get("plan") or [{}])[0].get("type", "free")
                return True, f"{email} · plano {plan}", None
            if r.status_code == 401:
                return False, "401 — API key inválida", "Regerar key em app.brevo.com → SMTP & API → API keys"
            return False, f"HTTP {r.status_code}: {r.text[:140]}", None

    ok, msg, hint, ms = await _measure(_do())
    return {"name": "Brevo (Email)", "status": "ok" if ok else "fail", "message": msg, "hint": hint, "latency_ms": ms}


async def _apify() -> CheckResult:
    if not settings.APIFY_API_TOKEN:
        return _disabled("Apify (LinkedIn/IG)", "APIFY_API_TOKEN")

    async def _do():
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://api.apify.com/v2/users/me",
                params={"token": settings.APIFY_API_TOKEN},
            )
            if r.status_code == 200:
                d = r.json().get("data", {})
                username = d.get("username", "?")
                plan = d.get("plan", "free")
                return True, f"@{username} · plano {plan}", None
            if r.status_code == 401:
                return False, "401 — Token inválido ou revogado", "Gerar novo token em console.apify.com → Settings → Integrations → API tokens. Captura LinkedIn/IG fica desactivada até corrigir (Google Maps continua a funcionar)."
            return False, f"HTTP {r.status_code}: {r.text[:140]}", None

    ok, msg, hint, ms = await _measure(_do())
    return {"name": "Apify (LinkedIn/IG)", "status": "ok" if ok else "fail", "message": msg, "hint": hint, "latency_ms": ms}


async def _gemini() -> CheckResult:
    if not settings.GEMINI_API_KEY:
        return {"name": "Gemini (IA)", "status": "disabled",
                "message": "Sem chave — IA usa fallback heurístico",
                "hint": "Cria key grátis em aistudio.google.com/app/apikey",
                "latency_ms": None}

    async def _do():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
        body = {"contents": [{"role": "user", "parts": [{"text": "ping"}]}], "generationConfig": {"maxOutputTokens": 5}}
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, params={"key": settings.GEMINI_API_KEY}, json=body)
            if r.status_code == 200:
                return True, f"Modelo {settings.GEMINI_MODEL} · operacional", None
            if r.status_code == 429:
                return False, f"429 — Quota grátis esgotada para {settings.GEMINI_MODEL}", "Sistema faz auto-fallback para outros modelos a cada chamada. Espera reset diário (00h UTC) ou activa billing em console.cloud.google.com/billing"
            if r.status_code == 400 and "API_KEY_INVALID" in r.text:
                return False, "Key inválida", "Regerar em aistudio.google.com/app/apikey"
            if r.status_code == 404:
                return False, f"Modelo {settings.GEMINI_MODEL} não disponível", "Mudar GEMINI_MODEL no .env para 'gemini-2.5-flash' ou 'gemini-2.5-flash-lite'"
            return False, f"HTTP {r.status_code}: {r.text[:160]}", None

    ok, msg, hint, ms = await _measure(_do())
    return {"name": "Gemini (IA)", "status": "ok" if ok else "fail", "message": msg, "hint": hint, "latency_ms": ms}


async def _whatsapp() -> CheckResult:
    provider = settings.WHATSAPP_PROVIDER

    if provider == "zapi":
        if not (settings.ZAPI_INSTANCE_ID and settings.ZAPI_TOKEN):
            return _disabled("WhatsApp (Z-API)", "ZAPI_*")

        async def _do():
            url = f"https://api.z-api.io/instances/{settings.ZAPI_INSTANCE_ID}/token/{settings.ZAPI_TOKEN}/status"
            headers = {}
            if settings.ZAPI_CLIENT_TOKEN:
                headers["client-token"] = settings.ZAPI_CLIENT_TOKEN
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(url, headers=headers)
                if r.status_code == 200:
                    d = r.json()
                    connected = d.get("connected", False)
                    if connected:
                        return True, "Conectado · WhatsApp activo", None
                    return False, "Desconectado", "Re-scan do QR Code em z-api.io → instância"
                if r.status_code == 400 and "subscribe" in r.text.lower():
                    return False, "Trial de 7 dias expirou", "Subscrever em z-api.io ($24/mês) OU migrar para Evolution self-hosted (FREE, ver PLANO-ESCALA-V2.md)"
                if r.status_code == 401:
                    return False, "401 — Token inválido", "Confirmar ZAPI_INSTANCE_ID, ZAPI_TOKEN e ZAPI_CLIENT_TOKEN em z-api.io"
                return False, f"HTTP {r.status_code}: {r.text[:140]}", None

        ok, msg, hint, ms = await _measure(_do())
        return {"name": "WhatsApp (Z-API)", "status": "ok" if ok else "fail", "message": msg, "hint": hint, "latency_ms": ms}

    # Evolution self-hosted
    if not (settings.EVOLUTION_BASE_URL and settings.EVOLUTION_API_KEY):
        return {"name": "WhatsApp (Evolution)", "status": "disabled",
                "message": "Evolution não configurado",
                "hint": "Deploy free em railway.app/template/evolution-api (5 min) e preencher EVOLUTION_* no .env",
                "latency_ms": None}

    async def _do():
        url = f"{settings.EVOLUTION_BASE_URL}/instance/connectionState/{settings.EVOLUTION_INSTANCE}"
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(url, headers={"apikey": settings.EVOLUTION_API_KEY})
            if r.status_code == 200:
                state = r.json().get("instance", {}).get("state", "?")
                if state == "open":
                    return True, "Conectado · WhatsApp activo", None
                return False, f"Estado: {state}", "Re-scan QR Code no painel Evolution"
            return False, f"HTTP {r.status_code}", "Verificar EVOLUTION_BASE_URL e EVOLUTION_API_KEY"

    ok, msg, hint, ms = await _measure(_do())
    return {"name": "WhatsApp (Evolution)", "status": "ok" if ok else "fail", "message": msg, "hint": hint, "latency_ms": ms}


async def _scheduler() -> CheckResult:
    from ..workers.scheduler import scheduler
    if scheduler and scheduler.running:
        jobs = len(scheduler.get_jobs())
        return {"name": "Scheduler", "status": "ok",
                "message": f"{jobs} job(s) · Europe/Lisbon",
                "hint": None, "latency_ms": 0}
    return {"name": "Scheduler", "status": "fail", "message": "Inactivo",
            "hint": "Reiniciar o servidor (start.bat)", "latency_ms": None}


async def _database() -> CheckResult:
    from ..database import engine
    from sqlalchemy import text
    t0 = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ms = int((time.perf_counter() - t0) * 1000)
        url_str = str(engine.url).replace("///./", "/")
        return {"name": "Database", "status": "ok", "message": url_str, "hint": None, "latency_ms": ms}
    except Exception as e:
        return {"name": "Database", "status": "fail", "message": str(e)[:200],
                "hint": "Verificar permissões da pasta data/", "latency_ms": None}


async def all_checks() -> list[CheckResult]:
    results = await asyncio.gather(
        _database(),
        _scheduler(),
        _google_places(),
        _apify(),
        _hunter(),
        _brevo(),
        _whatsapp(),
        _gemini(),
        return_exceptions=False,
    )
    return list(results)
