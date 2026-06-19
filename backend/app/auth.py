"""Minimal admin auth for the /mock/* control surface.

A signed, expiring bearer token is issued on login and verified on each request.
Uses only the stdlib (hmac/hashlib/base64) so there is no extra dependency. The
TrustSignal-facing /api/v1/whatsapp/* endpoints are intentionally NOT guarded here
(they have their own api_key mechanism); this only protects the dashboard surface.
"""

import base64
import hashlib
import hmac
import secrets
import time

from app.config import get_settings

TOKEN_TTL_SECONDS = 12 * 60 * 60

# Stable for the life of the process; used only when AUTH_SECRET is not configured.
# Tokens then survive until the next restart, which is acceptable for this tool.
_RUNTIME_SECRET = secrets.token_hex(32)


def _signing_key() -> bytes:
    return (get_settings().auth_secret or _RUNTIME_SECRET).encode()


def _sign(payload: str) -> str:
    return hmac.new(_signing_key(), payload.encode(), hashlib.sha256).hexdigest()


def create_token(username: str) -> str:
    expiry = int(time.time()) + TOKEN_TTL_SECONDS
    body = base64.urlsafe_b64encode(f"{username}|{expiry}".encode()).decode()
    return f"{body}.{_sign(body)}"


def verify_token(token: str | None) -> str | None:
    """Return the username if the token is valid and unexpired, else None."""
    if not token:
        return None
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(body)):
        return None
    try:
        payload = base64.urlsafe_b64decode(body.encode()).decode()
        username, expiry = payload.split("|", 1)
    except Exception:
        return None
    if int(expiry) < int(time.time()):
        return None
    return username


def check_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    if not settings.admin_password:
        # Fail closed: admin auth is unusable until ADMIN_PASSWORD is configured.
        return False
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(
        password, settings.admin_password
    )


def bearer_token(authorization: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""
