"""FastAPI application entry point.

Configures static files and includes all route modules.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import ORG_NAME
from app.csrf import CSRFTokenMiddleware
from app.templating import templates

BASE_DIR = Path(__file__).resolve().parent


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds 100 KB.

    Protects against trivially large form payloads.  Only checks the
    declared Content-Length header (clients that lie are still bounded by
    the underlying HTTP server / proxy layer).
    """

    MAX_BYTES = 100 * 1024  # 100 KB

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.MAX_BYTES:
                    return Response("Verzoek te groot (max 100 KB)", status_code=413)
            except ValueError:
                pass
        return await call_next(request)


app = FastAPI(title=f"{ORG_NAME} Goal Review", version="0.1.0")

# Middleware (outermost first)
app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(CSRFTokenMiddleware)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Static files (CSS, JS)
app.mount("/static", StaticFiles(directory=BASE_DIR.parent / "static"), name="static")

# Import routes after app is created to avoid circular imports
from app.routes import admin, goals, home, reviews, status  # noqa: E402

app.include_router(home.router)
app.include_router(goals.router)
app.include_router(reviews.router)
app.include_router(status.router)
app.include_router(admin.router)


@app.exception_handler(404)
async def not_found(request: Request, exc: Exception) -> HTMLResponse:
    """Custom 404 page using the base template."""
    return templates.TemplateResponse(request, "404.html", status_code=404)
