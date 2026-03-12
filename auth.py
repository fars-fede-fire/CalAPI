"""
Server-side OIDC Authorization Code flow med client secret + PKCE.

Miljøvariabler (alle påkrævet):
  OIDC_ISSUER         f.eks. https://id.kajo.fun/realms/myrealm
  OIDC_CLIENT_ID      App-registreringens client_id
  OIDC_CLIENT_SECRET  Client secret
  SECRET_KEY          Tilfældig streng til at signere session-cookien

Valgfri:
  OIDC_REDIRECT_URI   Fuldt URL til /auth/callback (auto-detekteres hvis tom)
"""

import os
import logging
import time
from typing import Any

import httpx
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

# ── Konfiguration ──────────────────────────────────────────────────────────────
OIDC_ISSUER        = os.getenv("OIDC_ISSUER", "").rstrip("/")
OIDC_CLIENT_ID     = os.getenv("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI  = os.getenv("OIDC_REDIRECT_URI", "")

# Valider at alle påkrævede variabler er sat ved opstart
_missing = [k for k, v in {
    "OIDC_ISSUER":        OIDC_ISSUER,
    "OIDC_CLIENT_ID":     OIDC_CLIENT_ID,
    "OIDC_CLIENT_SECRET": OIDC_CLIENT_SECRET,
}.items() if not v]

if _missing:
    raise RuntimeError(
        f"Manglende miljøvariabler: {', '.join(_missing)}\n"
        "Udfyld .env — se .env.example for vejledning."
    )

# ── OIDC Discovery cache ───────────────────────────────────────────────────────
_discovery_cache: dict[str, Any] = {}
_discovery_fetched_at: float = 0.0
_DISCOVERY_TTL = 3600


def get_discovery() -> dict[str, Any]:
    global _discovery_cache, _discovery_fetched_at
    if time.time() - _discovery_fetched_at < _DISCOVERY_TTL and _discovery_cache:
        return _discovery_cache
    url = f"{OIDC_ISSUER}/.well-known/openid-configuration"
    try:
        r = httpx.get(url, timeout=10)
        r.raise_for_status()
        _discovery_cache = r.json()
        _discovery_fetched_at = time.time()
        logger.info("OIDC discovery hentet fra %s", url)
        return _discovery_cache
    except Exception as exc:
        if _discovery_cache:
            logger.warning("OIDC discovery fejlede, bruger cached: %s", exc)
            return _discovery_cache
        raise RuntimeError(f"Kunne ikke hente OIDC discovery fra {url}: {exc}") from exc


# ── Session dependency ─────────────────────────────────────────────────────────

def require_session(request: Request) -> dict[str, Any]:
    """
    FastAPI dependency der kræver en gyldig session.
    Returnerer session['user'] dict med claims.
    """
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ikke logget ind.",
        )
    return user