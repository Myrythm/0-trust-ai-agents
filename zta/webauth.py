"""Stateless signed session cookies using only the standard library.

A cookie value is `base64url(json(payload)) + "." + hex(hmac_sha256)`.
`verify_session` recomputes the HMAC and compares in constant time; any
mismatch, malformed token, or bad JSON returns None. No server-side session
store — the signed payload is the session.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json


def _sign(body_b64: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_session(payload: dict[str, str], secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body_b64 = base64.urlsafe_b64encode(body).decode("utf-8")
    return f"{body_b64}.{_sign(body_b64, secret)}"


def verify_session(token: str, secret: str) -> dict[str, str] | None:
    if not token or token.count(".") != 1:
        return None
    body_b64, sig = token.split(".")
    expected = _sign(body_b64, secret)
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        raw = base64.urlsafe_b64decode(body_b64.encode("utf-8"))
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    return {str(k): str(v) for k, v in payload.items()}
