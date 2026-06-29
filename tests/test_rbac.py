"""Tests for the RBAC permission matrix (Layer 1 of authorization)."""

from __future__ import annotations

from pathlib import Path

import pytest
from zta.errors import RbacError
from zta.rbac import KNOWN_PAGES, KNOWN_TOOLS, Permissions, Role


def write_roles(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "roles.yaml"
    p.write_text(body)
    return p


VALID = """
roles:
  admin:
    pages: [chat, audit, policy, users, roles]
    tools: [echo, db_query, db_write]
  analyst:
    pages: [chat, audit]
    tools: [echo, db_query]
  viewer:
    pages: [chat]
    tools: []
"""


def test_known_constants() -> None:
    assert set(KNOWN_PAGES) == {"chat", "audit", "policy", "users", "roles"}
    assert set(KNOWN_TOOLS) == {"echo", "db_query", "db_write"}
    assert Role.ADMIN.value == "admin"
    assert Role.ANALYST.value == "analyst"
    assert Role.VIEWER.value == "viewer"


def test_tool_allowed(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    assert perms.tool_allowed("admin", "db_write") is True
    assert perms.tool_allowed("analyst", "db_query") is True
    assert perms.tool_allowed("analyst", "db_write") is False
    assert perms.tool_allowed("viewer", "echo") is False


def test_page_allowed(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    assert perms.page_allowed("analyst", "audit") is True
    assert perms.page_allowed("analyst", "policy") is False
    assert perms.page_allowed("viewer", "chat") is True
    assert perms.page_allowed("viewer", "audit") is False


def test_unknown_role_rejected(tmp_path: Path) -> None:
    bad = "roles:\n  superuser:\n    pages: [chat]\n    tools: []\n"
    with pytest.raises(RbacError):
        Permissions.load(write_roles(tmp_path, bad))


def test_unknown_page_rejected(tmp_path: Path) -> None:
    bad = "roles:\n  admin:\n    pages: [dashboard]\n    tools: []\n"
    with pytest.raises(RbacError):
        Permissions.load(write_roles(tmp_path, bad))


def test_unknown_tool_rejected(tmp_path: Path) -> None:
    bad = "roles:\n  admin:\n    pages: [chat]\n    tools: [rm_rf]\n"
    with pytest.raises(RbacError):
        Permissions.load(write_roles(tmp_path, bad))


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(RbacError):
        Permissions.load(tmp_path / "nope.yaml")


def test_unknown_role_query_is_false(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    assert perms.tool_allowed("ghost", "echo") is False
    assert perms.page_allowed("ghost", "chat") is False


def test_roles_listing(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    assert perms.roles() == ["admin", "analyst", "viewer"]


def test_as_table(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    table = perms.as_table()
    by_role = {row["role"]: row for row in table}
    assert set(by_role) == {"admin", "analyst", "viewer"}
    assert by_role["viewer"]["tools"] == []
    assert "db_query" in by_role["analyst"]["tools"]
    assert "audit" in by_role["analyst"]["pages"]


def test_repo_roles_yaml_is_valid() -> None:
    """The committed roles.yaml at the repo root must load and validate."""
    perms = Permissions.load(Path("roles.yaml"))
    assert perms.roles() == ["admin", "analyst", "viewer"]
