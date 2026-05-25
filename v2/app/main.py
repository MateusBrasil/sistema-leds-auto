"""Entry point — FastAPI app + lifecycle (init DB, start scheduler)."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from loguru import logger

from .config import settings
from .database import init_db
from .utils import setup_logging
from .workers.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.LOG_LEVEL)
    init_db()
    logger.info("Sistema de Leds V2 — starting up...")

    # Backup automático da DB (se houver leads e o último backup foi há >20h)
    from .services.backup import auto_backup_on_startup
    try:
        backup_name = auto_backup_on_startup()
        if backup_name:
            logger.info("Backup ao arranque: {}", backup_name)
    except Exception as e:
        logger.warning("Backup ao arranque falhou: {}", e)

    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Shutdown complete.")


app = FastAPI(title="Sistema de Leads V2 — VV TRAFFIC DATA", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.APP_SECRET,
    same_site="lax",
    https_only=False,
    max_age=60 * 60 * 24 * 14,  # 14 dias
    session_cookie="vvtraffic_session",
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    # Redirect 303 to /login on auth failures for HTML pages.
    if exc.status_code == 303 and "Location" in (exc.headers or {}):
        url = exc.headers["Location"]
        if "next" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}next={request.url.path}"
        return RedirectResponse(url, status_code=303)
    if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers or {})


from .routes.auth import router as auth_router  # noqa: E402
from .routes.dashboard import router as dashboard_router  # noqa: E402
from .routes.api import router as api_router  # noqa: E402
from .routes.webhooks import router as webhooks_router  # noqa: E402
from .routes.stream import router as stream_router  # noqa: E402
from .routes.extras import router as extras_router  # noqa: E402

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(api_router)
app.include_router(webhooks_router)
app.include_router(stream_router)
app.include_router(extras_router)


@app.get("/healthz")
def healthz():
    return {"ok": True, "version": "2.0.0"}
