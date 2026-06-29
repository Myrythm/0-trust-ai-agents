"""RBAC permission matrix: which role may use which pages, tools, and data tables.

This is Layer 1 of the two-layer authorization model. It is loaded from a
YAML file (`roles.yaml`) and answers `tool_allowed` / `page_allowed` /
`table_readable`. The policy engine (`zta.policy`) is Layer 2 and stays
role-agnostic; the two are composed with AND at the runtime surface.

Roles are domain-themed for the Chinook media-store dataset:
  - manager: everything (all pages, db_write, all tables incl. Employee).
  - sales:   read catalog + sales tables (Customer/Invoice/InvoiceLine); no Employee.
  - catalog: read catalog tables only (no Customer/Invoice/Employee).

Table scope is `"*"` (all tables) or an explicit list. It is enforced at
execution time by a SQLite authorizer in the db_query tool; this module is
the source of truth for *what* each role may read.

Validation happens at load time: every role must be a known `Role` and every
referenced page/tool/table must be known, so typos fail loudly instead of
silently denying. An unknown role queried at runtime returns False / no access
(deny-by-default).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

import yaml

from zta.errors import RbacError


class Role(StrEnum):
    MANAGER = "manager"
    SALES = "sales"
    CATALOG = "catalog"


KNOWN_PAGES: frozenset[str] = frozenset({"chat", "audit", "policy", "users", "roles"})
KNOWN_TOOLS: frozenset[str] = frozenset({"echo", "db_query", "db_write"})
KNOWN_TABLES: frozenset[str] = frozenset(
    {
        "Artist",
        "Album",
        "Track",
        "Genre",
        "MediaType",
        "Playlist",
        "PlaylistTrack",
        "Customer",
        "Invoice",
        "InvoiceLine",
        "Employee",
    }
)
KNOWN_ROLES: frozenset[str] = frozenset(r.value for r in Role)

_ALL_TABLES = "*"


class RoleRow(TypedDict):
    """One row of the rendered permission matrix (see `Permissions.as_table`)."""

    role: str
    pages: list[str]
    tools: list[str]
    tables: list[str]


@dataclass
class Permissions:
    """A loaded RBAC matrix: role -> allowed pages, tools, and readable tables.

    In `_tables`, a value of None means "all tables" (the `"*"` scope).
    """

    _pages: dict[str, set[str]]
    _tools: dict[str, set[str]]
    _tables: dict[str, set[str] | None]

    @classmethod
    def load(cls, path: Path) -> Permissions:
        if not path.exists():
            raise RbacError(f"roles file not found: {path}")
        try:
            raw = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            raise RbacError(f"invalid YAML in roles file {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise RbacError(f"roles file root must be a mapping: {path}")
        roles_raw = raw.get("roles", {})
        if not isinstance(roles_raw, dict):
            raise RbacError(f"'roles' must be a mapping: {path}")

        pages: dict[str, set[str]] = {}
        tools: dict[str, set[str]] = {}
        tables: dict[str, set[str] | None] = {}
        for role, spec in roles_raw.items():
            if role not in KNOWN_ROLES:
                raise RbacError(f"unknown role {role!r}; must be one of {sorted(KNOWN_ROLES)}")
            if not isinstance(spec, dict):
                raise RbacError(f"role {role!r} spec must be a mapping")
            pages[role] = cls._parse_set(role, "pages", spec.get("pages"), KNOWN_PAGES)
            tools[role] = cls._parse_set(role, "tools", spec.get("tools"), KNOWN_TOOLS)
            tables[role] = cls._parse_tables(role, spec.get("tables"))
        return cls(_pages=pages, _tools=tools, _tables=tables)

    @staticmethod
    def _parse_set(role: str, key: str, value: object, known: frozenset[str]) -> set[str]:
        if value is not None and not isinstance(value, list):
            raise RbacError(f"role {role!r} {key!r} must be a list")
        items = set(value or [])
        unknown = items - known
        if unknown:
            raise RbacError(f"role {role!r} references unknown {key}: {sorted(unknown)}")
        return items

    @staticmethod
    def _parse_tables(role: str, value: object) -> set[str] | None:
        if value == _ALL_TABLES:
            return None
        if value is None:
            return set()
        if not isinstance(value, list):
            raise RbacError(f"role {role!r} 'tables' must be '*' or a list")
        items = set(value)
        unknown = items - KNOWN_TABLES
        if unknown:
            raise RbacError(f"role {role!r} references unknown table(s): {sorted(unknown)}")
        return items

    def tool_allowed(self, role: str, tool: str) -> bool:
        return tool in self._tools.get(role, set())

    def page_allowed(self, role: str, page: str) -> bool:
        return page in self._pages.get(role, set())

    def table_readable(self, role: str, table: str) -> bool:
        scope = self._tables.get(role, set())
        return scope is None or table in scope

    def tables_allowed(self, role: str) -> set[str] | None:
        """Readable tables for a role; None means all tables."""
        return self._tables.get(role, set())

    def roles(self) -> list[str]:
        return sorted(self._pages)

    def as_table(self) -> list[RoleRow]:
        rows: list[RoleRow] = []
        for role in self.roles():
            scope = self._tables.get(role, set())
            table_display = [_ALL_TABLES] if scope is None else sorted(scope)
            rows.append(
                RoleRow(
                    role=role,
                    pages=sorted(self._pages.get(role, set())),
                    tools=sorted(self._tools.get(role, set())),
                    tables=table_display,
                )
            )
        return rows
