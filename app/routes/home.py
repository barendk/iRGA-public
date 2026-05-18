"""Home page route — landing page at /."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    """Render the home page."""
    return templates.TemplateResponse(request, "home.html")
