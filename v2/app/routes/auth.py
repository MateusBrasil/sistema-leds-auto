"""Login / logout endpoints com rate-limit e password hash flexível."""

from pathlib import Path

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from loguru import logger

from ..config import settings
from ..database import get_db
from ..deps import SESSION_KEY
from ..models import EventLog
from ..security import verify_password, login_limiter, client_ip


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _audit_login(db: Session, ip: str, username: str, success: bool, reason: str = ""):
    db.add(EventLog(
        level="INFO" if success else "WARNING",
        source="auth",
        actor=username,
        message=f"Login {'OK' if success else 'FALHA'} de {ip}" + (f" — {reason}" if reason else ""),
        payload=None,
    ))
    db.commit()


@router.get("/login")
def login_form(request: Request, next: str = "/", error: str | None = None):
    if request.session.get(SESSION_KEY):
        return RedirectResponse(next or "/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"next": next, "error": error})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    ip = client_ip(request)

    # Rate-limit antes de processar
    allowed, wait = login_limiter.check(ip)
    if not allowed:
        _audit_login(db, ip, username, False, f"rate-limited (wait {wait}s)")
        logger.warning("Login rate-limited: ip={} wait={}s", ip, wait)
        return templates.TemplateResponse(
            request, "login.html",
            {"next": next, "error": f"Demasiadas tentativas. Tenta de novo em {wait // 60 + 1} minutos."},
            status_code=429,
        )

    # Verifica username + password (constante de tempo)
    import secrets
    correct_user = secrets.compare_digest(username, settings.APP_USERNAME)
    correct_pass = verify_password(password, settings.APP_PASSWORD)

    if not (correct_user and correct_pass):
        _audit_login(db, ip, username, False, "credenciais inválidas")
        return templates.TemplateResponse(
            request, "login.html",
            {"next": next, "error": "Credenciais inválidas. Confirma user e password no .env."},
            status_code=401,
        )

    # Sucesso — limpa tentativas, regista sessão
    login_limiter.reset(ip)
    request.session[SESSION_KEY] = username
    _audit_login(db, ip, username, True)
    return RedirectResponse(next or "/", status_code=303)


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    user = request.session.get(SESSION_KEY)
    if user:
        db.add(EventLog(level="INFO", source="auth", actor=user,
                        message=f"Logout de {client_ip(request)}"))
        db.commit()
    request.session.pop(SESSION_KEY, None)
    return RedirectResponse("/login", status_code=303)
