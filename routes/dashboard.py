"""
ARGUS — Dashboard Route
Serves the command center at /dashboard
"""
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter()

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
    summary="ARGUS Command Center — web dashboard",
    tags=["Dashboard"],
)
async def dashboard():
    """Serves the ARGUS Command Center single-page application."""
    html_path = _STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse(
            content="<h1>Dashboard not found</h1>",
            status_code=404,
        )
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
