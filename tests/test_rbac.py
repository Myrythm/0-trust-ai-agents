"""Tests for the RBAC permission matrix (Layer 1 of authorization)."""

from __future__ import annotations

from pathlib import Path

import pytest
from zta.errors import RbacError
from zta.rbac import KNOWN_PAGES, KNOWN_TABLES, KNOWN_TOOLS, Permissions, Role


def write_roles(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "roles.yaml"
    p.write_text(body)
    return p


VALID = """
roles:
  manager:
    pages: [chat, audit, policy, users, roles]
    tools: [echo, db_query, db_write]
    tables: "*"
  sales:
    pages: [chat, audit]
    tools: [echo, db_query]
    tables: [Artist, Album, Track, Customer, Invoice, InvoiceLine]
  catalog:
    pages: [chat]
    tools: [echo, db_query]
    tables: [Artist, Album, Track, Genre]
"""


def test_known_constants() -> None:
    assert set(KNOWN_PAGES) == {"chat", "audit", "policy", "users", "roles"}
    assert set(KNOWN_TOOLS) == {"echo", "db_query", "db_write"}
    assert {"Artist", "Customer", "Employee", "Invoice", "Track"} <= set(KNOWN_TABLES)
    assert Role.MANAGER.value == "manager"
    assert Role.SALES.value == "sales"
    assert Role.CATALOG.value == "catalog"


def test_tool_allowed(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    assert perms.tool_allowed("manager", "db_write") is True
    assert perms.tool_allowed("sales", "db_query") is True
    assert perms.tool_allowed("sales", "db_write") is False
    assert perms.tool_allowed("catalog", "db_query") is True
    assert perms.tool_allowed("catalog", "db_write") is False


def test_page_allowed(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    assert perms.page_allowed("sales", "audit") is True
    assert perms.page_allowed("sales", "policy") is False
    assert perms.page_allowed("catalog", "chat") is True
    assert perms.page_allowed("catalog", "audit") is False
    assert perms.page_allowed("manager", "users") is True


def test_table_readable(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    # manager: all tables ("*")
    assert perms.table_readable("manager", "Employee") is True
    # sales: sales + catalog, but NOT Employee
    assert perms.table_readable("sales", "Customer") is True
    assert perms.table_readable("sales", "Employee") is False
    # catalog: catalog only, NOT Customer/Invoice/Employee
    assert perms.table_readable("catalog", "Artist") is True
    assert perms.table_readable("catalog", "Customer") is False
    assert perms.table_readable("catalog", "Employee") is False


def test_tables_allowed(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    assert perms.tables_allowed("manager") is None  # all
    sales = perms.tables_allowed("sales")
    assert sales is not None
    assert "Customer" in sales
    assert "Employee" not in sales


def test_unknown_role_rejected(tmp_path: Path) -> None:
    bad = "roles:\n  superuser:\n    pages: [chat]\n    tools: []\n"
    with pytest.raises(RbacError):
        Permissions.load(write_roles(tmp_path, bad))


def test_unknown_page_rejected(tmp_path: Path) -> None:
    bad = "roles:\n  manager:\n    pages: [dashboard]\n    tools: []\n"
    with pytest.raises(RbacError):
        Permissions.load(write_roles(tmp_path, bad))


def test_unknown_tool_rejected(tmp_path: Path) -> None:
    bad = "roles:\n  manager:\n    pages: [chat]\n    tools: [rm_rf]\n"
    with pytest.raises(RbacError):
        Permissions.load(write_roles(tmp_path, bad))


def test_unknown_table_rejected(tmp_path: Path) -> None:
    bad = "roles:\n  catalog:\n    pages: [chat]\n    tools: [db_query]\n    tables: [Sproket]\n"
    with pytest.raises(RbacError):
        Permissions.load(write_roles(tmp_path, bad))


def test_bad_tables_type_rejected(tmp_path: Path) -> None:
    bad = "roles:\n  catalog:\n    pages: [chat]\n    tools: [db_query]\n    tables: 5\n"
    with pytest.raises(RbacError):
        Permissions.load(write_roles(tmp_path, bad))


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(RbacError):
        Permissions.load(tmp_path / "nope.yaml")


def test_unknown_role_query_is_false(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    assert perms.tool_allowed("ghost", "echo") is False
    assert perms.page_allowed("ghost", "chat") is False
    assert perms.table_readable("ghost", "Artist") is False


def test_roles_listing(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    assert perms.roles() == ["catalog", "manager", "sales"]


def test_as_table(tmp_path: Path) -> None:
    perms = Permissions.load(write_roles(tmp_path, VALID))
    by_role = {row["role"]: row for row in perms.as_table()}
    assert set(by_role) == {"manager", "sales", "catalog"}
    assert by_role["manager"]["tables"] == ["*"]
    assert "Customer" in by_role["sales"]["tables"]
    assert "Customer" not in by_role["catalog"]["tables"]
    assert "db_query" in by_role["catalog"]["tools"]


def test_repo_roles_yaml_is_valid() -> None:
    """The committed roles.yaml at the repo root must load and validate."""
    perms = Permissions.load(Path("roles.yaml"))
    assert perms.roles() == ["catalog", "manager", "sales"]
    assert perms.table_readable("catalog", "Employee") is False
    assert perms.tables_allowed("manager") is None
