"""Seed default ZTA users (idempotent). Run after seed_db.py.

Usage: ZTA_DB_PATH=./data.db python examples/seed_users.py

Default accounts (CHANGE these in any real deployment):
  manager / manager123   (role: manager — full access, incl. db_write + Employee data)
  sales   / sales123      (role: sales   — read catalog + Customer/Invoice; no Employee)
  catalog / catalog123    (role: catalog — read catalog tables only)
"""

from __future__ import annotations

import os
from pathlib import Path

from zta.users import UserStore

DEFAULTS = [
    ("manager", "manager123", "manager"),
    ("sales", "sales123", "sales"),
    ("catalog", "catalog123", "catalog"),
]


def main() -> None:
    db_path = Path(os.environ.get("ZTA_DB_PATH", "./data.db"))
    store = UserStore(db_path)
    for username, password, role in DEFAULTS:
        if store.get_user(username) is None:
            store.create_user(username, password, role)
            print(f"created {username} ({role})")
        else:
            print(f"skip {username} (exists)")


if __name__ == "__main__":
    main()
