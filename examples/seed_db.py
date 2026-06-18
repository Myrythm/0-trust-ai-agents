"""Populate data.db with sample customers and orders for the demo."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data.db"
DB_PATH = Path(os.environ.get("ZTA_DB_PATH", str(_DEFAULT_DB)))

CUSTOMERS = [
    ("Alice", "alice@example.com"),
    ("Bob", "bob@example.com"),
    ("Carol", "carol@example.com"),
    ("Dave", "dave@example.com"),
    ("Eve", "eve@example.com"),
]

ORDERS = [
    (1, 19.99, "2024-01-15"),
    (1, 42.50, "2024-03-22"),
    (2, 8.75, "2024-02-10"),
    (2, 99.00, "2024-04-05"),
    (3, 15.00, "2023-12-01"),
    (3, 75.25, "2024-05-12"),
    (4, 200.00, "2024-06-30"),
    (4, 33.33, "2024-07-04"),
    (5, 5.99, "2023-08-19"),
    (5, 12.50, "2024-08-25"),
]


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE customers (
                id   INTEGER PRIMARY KEY,
                name  TEXT NOT NULL,
                email TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE orders (
                id          INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                amount      REAL NOT NULL,
                placed_on   TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
            """
        )
        cur.executemany("INSERT INTO customers (name, email) VALUES (?, ?)", CUSTOMERS)
        cur.executemany(
            "INSERT INTO orders (customer_id, amount, placed_on) VALUES (?, ?, ?)", ORDERS
        )
        conn.commit()
        print(f"Seeded {DB_PATH}: {len(CUSTOMERS)} customers, {len(ORDERS)} orders")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
