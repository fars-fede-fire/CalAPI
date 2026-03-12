"""
Shift Calendar API
==================
Converts monthly Excel shift schedules into subscribable ICS calendar feeds.

Auth:   Server-side OIDC Authorization Code flow.
        Session cookie (signed, httponly) — ingen tokens i browseren.
Public: GET /  og  /calendar/* (statiske ICS-filer)
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import models  # noqa: F401

from auth import require_session
from routers import (
    upload_router,
    categories_router,
    shift_types_router,
    raw_shifts_router,
    employees_router,
    calendar_router,
    config_io_router,
    auth_router,
)

from dotenv import load_dotenv
load_dotenv()

BASE_DIR  = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

SECRET_KEY = os.getenv("SECRET_KEY", "")


# ── Lifespan ───────────────────────────────────────────────────────────────────


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Shift Calendar API",
    version="1.0.0",
)

# Session middleware — skal registreres FØR andre middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="vagtkalender_session",
    max_age=8 * 3600,   # 8 timer
    https_only=os.getenv("HTTPS_ONLY", "false").lower() == "true",
    same_site="lax",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files — PUBLIC ──────────────────────────────────────────────────────
CALENDAR_DIR = BASE_DIR / "static" / "calendars"
CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/calendar", StaticFiles(directory=str(CALENDAR_DIR)), name="calendars")

# ── Auth routes — PUBLIC (håndterer login/callback/logout) ────────────────────
app.include_router(auth_router)

# ── Protected API routers ──────────────────────────────────────────────────────
_auth = [Depends(require_session)]

app.include_router(upload_router,      dependencies=_auth)
app.include_router(categories_router,  dependencies=_auth)
app.include_router(shift_types_router, dependencies=_auth)
app.include_router(raw_shifts_router,  dependencies=_auth)
app.include_router(employees_router,   dependencies=_auth)
app.include_router(calendar_router,    dependencies=_auth)
app.include_router(config_io_router,   dependencies=_auth)


# ── Admin UI ───────────────────────────────────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
@app.get("/admin/", response_class=HTMLResponse, include_in_schema=False)
def admin_ui(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/auth/login")

    user = request.session.get("user")
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user":    user,
    })


# ── Health — PUBLIC ────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "admin": "/admin"}