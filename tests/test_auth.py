"""Tests for authentication and per-role route guards."""

from __future__ import annotations

from pathlib import Path

from app import AppConfig, create_app
from fastapi.testclient import TestClient
from zta.users import UserStore


def cfg_for(tmp_path: Path) -> AppConfig:
    return AppConfig(
        agent_id="bot",
        policy_path=Path("policy.yaml"),
        audit_path=tmp_path / "a.jsonl",
        key_dir=tmp_path / "keys",
        roles_path=Path("roles.yaml"),
        users_db_path=tmp_path / "users.db",
        secret_key="test-secret",
    )


def login(client: TestClient, username: str, password: str) -> None:
    resp = client.post(
        "/login", data={"username": username, "password": password}, follow_redirects=False
    )
    assert resp.status_code == 303


def test_unauthenticated_html_redirects(tmp_path: Path) -> None:
    client = TestClient(create_app(cfg_for(tmp_path)))
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_unauthenticated_api_returns_401(tmp_path: Path) -> None:
    client = TestClient(create_app(cfg_for(tmp_path)))
    assert client.get("/api/audit").status_code == 401


def test_bad_credentials_401(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    UserStore(cfg.users_db_path).create_user("manager", "pw", "manager")
    client = TestClient(create_app(cfg))
    resp = client.post(
        "/login", data={"username": "manager", "password": "wrong"}, follow_redirects=False
    )
    assert resp.status_code == 401


def test_login_then_logout(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    UserStore(cfg.users_db_path).create_user("manager", "pw", "manager")
    client = TestClient(create_app(cfg))
    login(client, "manager", "pw")
    assert client.get("/", follow_redirects=False).status_code == 200
    client.get("/logout", follow_redirects=False)
    assert client.get("/", follow_redirects=False).status_code == 303


def test_catalog_forbidden_from_audit(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    UserStore(cfg.users_db_path).create_user("catalog", "pw", "catalog")
    client = TestClient(create_app(cfg))
    login(client, "catalog", "pw")
    assert client.get("/audit", follow_redirects=False).status_code == 403
    assert client.get("/api/audit").status_code == 403


def test_sales_can_audit_but_not_policy(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    UserStore(cfg.users_db_path).create_user("sales", "pw", "sales")
    client = TestClient(create_app(cfg))
    login(client, "sales", "pw")
    assert client.get("/audit", follow_redirects=False).status_code == 200
    assert client.get("/policy", follow_redirects=False).status_code == 403


def test_forged_cookie_rejected(tmp_path: Path) -> None:
    client = TestClient(create_app(cfg_for(tmp_path)))
    client.cookies.set("zta_session", "forged.deadbeef")
    assert client.get("/", follow_redirects=False).status_code == 303
