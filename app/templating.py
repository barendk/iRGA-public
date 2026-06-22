"""Shared Jinja2 template configuration.

Separated from main.py to avoid circular imports with route modules.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import ORG_HEADER, ORG_NAME, ORG_TAGLINE

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Make org branding available in all templates without per-route context.
# Values are read from env vars once at import time; restart to pick up changes.
templates.env.globals["org_name"] = ORG_NAME
templates.env.globals["org_tagline"] = ORG_TAGLINE
templates.env.globals["org_header"] = ORG_HEADER
