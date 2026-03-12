"""
OIDC Authorization Code flow med PKCE + client secret (server-side).

Mange moderne providers (Keycloak, Auth0 m.fl.) kræver PKCE selv for
fortrolige klienter. code_verifier genereres og gemmes i session på
serveren — browseren ser hverken verifier, tokens eller client secret.

GET /auth/login     → generer state + PKCE, gem i session, redirect til provider
GET /auth/callback  → valider state, byt code til token med verifier + secret
GET /auth/logout    → ryd session, RP-initiated logout hvis muligt
"""

import base64
import hashlib
import json
import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from auth import (
    OIDC_CLIENT_ID,
    OIDC_CLIENT_SECRET,
    OIDC_REDIRECT_URI,
    get_discovery,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"], include_in_schema=False)


# ── PKCE helpers ───────────────────────────────────────────────────────────────

def _generate_pkce() -> tuple[str, str]:
    """Returner (code_verifier, code_challenge)."""
    verifier  = secrets.token_urlsafe(64)
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _redirect_uri(request: Request) -> str:
    if OIDC_REDIRECT_URI:
        return OIDC_REDIRECT_URI
    return str(request.base_url).rstrip("/") + "/auth/callback"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/login")
def login(request: Request) -> RedirectResponse:
    state            = secrets.token_urlsafe(16)
    verifier, challenge = _generate_pkce()

    # Gem i session — backenden husker dem til callback
    request.session["oidc_state"]    = state
    request.session["pkce_verifier"] = verifier

    discovery = get_discovery()
    params = urlencode({
        "response_type":         "code",
        "client_id":             OIDC_CLIENT_ID,
        "redirect_uri":          _redirect_uri(request),
        "scope":                 "openid profile email",
        "state":                 state,
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
    })
    return RedirectResponse(f"{discovery['authorization_endpoint']}?{params}")


@router.get("/callback")
def callback(
    request: Request,
    code:  str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    if error:
        desc = request.query_params.get("error_description", error)
        logger.warning("OIDC callback fejl: %s", desc)
        return RedirectResponse(f"/auth/login?error={desc}")

    # Valider state (CSRF)
    saved_state = request.session.pop("oidc_state", None)
    if not saved_state or state != saved_state:
        logger.warning("OIDC state mismatch")
        return RedirectResponse("/auth/login?error=state_mismatch")

    # Hent verifier fra session
    verifier = request.session.pop("pkce_verifier", None)
    if not verifier:
        logger.warning("PKCE verifier mangler i session")
        return RedirectResponse("/auth/login?error=missing_verifier")

    discovery = get_discovery()

    # Token exchange — server-to-server med secret + verifier
    try:
        r = httpx.post(
            discovery["token_endpoint"],
            data={
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  _redirect_uri(request),
                "client_id":     OIDC_CLIENT_ID,
                "client_secret": OIDC_CLIENT_SECRET,
                "code_verifier": verifier,
            },
            timeout=15,
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = exc.response.json() if exc.response.content else {}
        desc = body.get("error_description") or body.get("error") or str(exc)
        logger.error("Token exchange fejlede: %s", body)
        return RedirectResponse(f"/auth/login?error={desc}")
    except Exception as exc:
        logger.error("Token exchange fejlede: %s", exc)
        return RedirectResponse("/auth/login?error=token_exchange_failed")

    tokens = r.json()

    # Udpak brugerinfo fra id_token claims
    user: dict = {}
    id_token = tokens.get("id_token", "")
    if id_token:
        try:
            padding = 4 - len(id_token.split(".")[1]) % 4
            payload = id_token.split(".")[1] + "=" * padding
            user = json.loads(base64.urlsafe_b64decode(payload))
        except Exception as exc:
            logger.warning("Kunne ikke dekode id_token: %s", exc)

    # Fallback: /userinfo endpoint
    if not user and "userinfo_endpoint" in discovery:
        try:
            ui = httpx.get(
                discovery["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=10,
            )
            ui.raise_for_status()
            user = ui.json()
        except Exception as exc:
            logger.warning("Userinfo hentning fejlede: %s", exc)

    request.session["user"] = {
        "sub":   user.get("sub", ""),
        "name":  user.get("name") or user.get("preferred_username") or user.get("email") or "Bruger",
        "email": user.get("email", ""),
    }

    logger.info("Login: %s (%s)", request.session["user"]["name"], request.session["user"]["sub"])
    return RedirectResponse("/admin")


@router.get("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    try:
        discovery = get_discovery()
        end_session = discovery.get("end_session_endpoint")
        if end_session:
            post_logout = _redirect_uri(request).replace("/callback", "/login")
            params = urlencode({"post_logout_redirect_uri": post_logout})
            return RedirectResponse(f"{end_session}?{params}")
    except Exception:
        pass
    return RedirectResponse("/auth/login")