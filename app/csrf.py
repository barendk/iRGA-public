"""CSRF protection helpers.

Double-submit cookie pattern:
  - CSRFTokenMiddleware sets a `csrftoken` cookie on every response and
    makes the current token value available as `request.state.csrftoken`
    so Jinja2 templates can embed it in forms.
  - `verify_csrf` is a FastAPI dependency added to every unsafe (POST/PUT/…)
    route.  It compares the `csrftoken` form field against the cookie.

No third-party package is required — the pattern relies only on the fact
that a cross-site attacker cannot read the SameSite cookie value and
therefore cannot reproduce the matching form field.
"""

import hmac
import secrets

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import APP_SECRET_KEY

CSRF_COOKIE = "csrftoken"
CSRF_FIELD = "csrftoken"

# In production (real secret key) cookies are Secure + HttpOnly.
# In local dev (default key) we allow plain HTTP.
_PRODUCTION = APP_SECRET_KEY != "dev-secret-key"


# ── Middleware ──────────────────────────────────────────────────────────────


class CSRFTokenMiddleware(BaseHTTPMiddleware):
    """Set a CSRF cookie on every response and expose its value on the request.

    Only responsible for token *generation* and cookie housekeeping.
    Token *validation* on POST requests is handled by the `verify_csrf`
    FastAPI dependency so that it runs after FastAPI has parsed the form body.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        token = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
        request.state.csrftoken = token
        response = await call_next(request)
        # Set cookie if absent, or rotate after a successful POST.
        is_post_ok = request.method == "POST" and 200 <= response.status_code < 400
        if CSRF_COOKIE not in request.cookies or is_post_ok:
            new_token = secrets.token_urlsafe(32) if is_post_ok else token
            response.set_cookie(
                CSRF_COOKIE,
                new_token,
                samesite="lax",
                httponly=True,
                secure=_PRODUCTION,
                max_age=86400,
            )
        return response


# ── Dependency ──────────────────────────────────────────────────────────────


async def verify_csrf(request: Request) -> None:
    """FastAPI dependency that validates the CSRF token on unsafe requests.

    Raises HTTP 403 if the `csrftoken` form field is absent or does not match
    the `csrftoken` cookie value.

    Usage::

        @router.post("")
        async def my_post(request: Request, _csrf: None = Depends(verify_csrf)):
            ...
    """
    form = await request.form()
    form_token = str(form.get(CSRF_FIELD, "")).strip()
    cookie_token = request.cookies.get(CSRF_COOKIE, "")

    if not form_token or not cookie_token or not hmac.compare_digest(form_token, cookie_token):
        raise HTTPException(status_code=403, detail="Ongeldig CSRF token")
