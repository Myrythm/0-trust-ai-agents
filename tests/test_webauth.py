"""Tests for stateless HMAC-signed session cookies."""

from __future__ import annotations

import base64
import json

from zta.webauth import sign_session, verify_session

SECRET = "test-secret-key"


def test_roundtrip() -> None:
    token = sign_session({"username": "alice", "role": "manager"}, SECRET)
    payload = verify_session(token, SECRET)
    assert payload == {"username": "alice", "role": "manager"}


def test_tampered_payload_rejected() -> None:
    token = sign_session({"username": "alice", "role": "catalog"}, SECRET)
    _, sig = token.split(".")
    forged_body = base64.urlsafe_b64encode(
        json.dumps({"username": "alice", "role": "manager"}).encode()
    ).decode()
    forged = f"{forged_body}.{sig}"
    assert verify_session(forged, SECRET) is None


def test_wrong_secret_rejected() -> None:
    token = sign_session({"username": "a", "role": "manager"}, SECRET)
    assert verify_session(token, "other-secret") is None


def test_garbage_rejected() -> None:
    assert verify_session("not-a-token", SECRET) is None
    assert verify_session("", SECRET) is None
    assert verify_session("a.b.c", SECRET) is None
