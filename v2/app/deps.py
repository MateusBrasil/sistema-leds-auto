"""Auth via cookie session — substitui o antigo HTTP Basic.

Login bonito em /login. Cookies seguros (HttpOnly, SameSite=lax).
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse


SESSION_KEY = "user"


def get_current_user(request: Request) -> str | None:
    return request.session.get(SESSION_KEY)


def require_user(request: Request) -> str:
    user = get_current_user(request)
    if not user:
        # Browser visit → redirect; API call → 401
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                detail="not-auth",
                headers={"Location": "/login"},
            )
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
