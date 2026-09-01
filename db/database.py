"""
Offline SQLite access layer for Canopy Finance Planner.

Design goals:
- Zero network calls, ever. All data lives in a local .db file under app data dir.
- Amounts are stored as integer minor units (paise) to avoid float rounding bugs;
  convert with to_minor()/to_major() at the UI boundary only.
- A single Database object wraps one sqlite3.Connection with row_factory=Row so
  callers can use dict-like access (row["amount_minor"]) instead of tuple indices.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def to_minor(amount: float) -> int:
    """Convert a user-facing decimal amount (e.g. 149.50) to integer minor units (14950)."""
    return int(round(float(amount) * 100))


def to_major(amount_minor: int) -> float:
    """Convert integer minor units back to a decimal amount for display."""
    return round(amount_minor / 100, 2)


def default_db_path() -> Path:
    """
    Resolve where the sqlite file should live.
    On Android (python-for-android), the app's private storage dir is used so the
    file is sandboxed to this app only. On desktop, we fall back to ./data/.
    """
    try:
        from android.storage import app_storage_path  # type: ignore

        base = Path(app_storage_path())
    except Exception:
        base = Path(__file__).resolve().parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "canopy_finance.db"


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            self.conn.executescript(f.read())
        self.conn.commit()

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        cur = self.conn.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        cur = self.conn.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row

    def insert(self, table: str, values: dict) -> int:
        cols = ", ".join(values.keys())
        placeholders = ", ".join(["?"] * len(values))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        with self.cursor() as cur:
            cur.execute(sql, list(values.values()))
            return cur.lastrowid

    def update(self, table: str, row_id: int, values: dict, id_col: str = "id") -> None:
        set_clause = ", ".join(f"{k} = ?" for k in values.keys())
        sql = f"UPDATE {table} SET {set_clause} WHERE {id_col} = ?"
        with self.cursor() as cur:
            cur.execute(sql, [*values.values(), row_id])

    def delete(self, table: str, row_id: int, id_col: str = "id") -> None:
        with self.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE {id_col} = ?", (row_id,))

    def close(self) -> None:
        self.conn.close()

    # ---- first-run defaults -------------------------------------------------
    def seed_defaults_if_empty(self) -> None:
        """Populate a sensible default category set on first launch only."""
        existing = self.query_one("SELECT COUNT(*) AS n FROM categories")
        if existing and existing["n"] > 0:
            return
        defaults = [
            ("Groceries", "household", "cart-outline", "#4CAF50", 0),
            ("Stationery", "stationery", "pencil-outline", "#FF9800", 0),
            ("Household Supplies", "household", "home-outline", "#8BC34A", 0),
            ("Rent", "recurring", "home-city-outline", "#3F51B5", 1),
            ("Utilities", "recurring", "flash-outline", "#00BCD4", 1),
            ("Subscriptions", "recurring", "repeat", "#9C27B0", 1),
            ("Transport", "transport", "car-outline", "#607D8B", 0),
            ("Food & Dining", "food", "silverware-fork-knife", "#F44336", 0),
            ("Health", "health", "heart-pulse", "#E91E63", 0),
            ("Entertainment", "entertainment", "movie-open-outline", "#FFC107", 0),
            ("Shopping", "other", "bag-personal-outline", "#795548", 0),
            ("Savings & Investments", "savings", "piggy-bank-outline", "#009688", 0),
            ("Income", "income", "cash-plus", "#2E7D32", 0),
            ("Other", "other", "shape-outline", "#9E9E9E", 0),
        ]
        for name, group_name, icon, color_hex, is_recurring in defaults:
            self.insert(
                "categories",
                {
                    "name": name,
                    "group_name": group_name,
                    "icon": icon,
                    "color_hex": color_hex,
                    "is_recurring": is_recurring,
                    "is_system": 1,
                },
            )


_singleton: Optional[Database] = None


def get_db(db_path: Optional[str] = None) -> Database:
    """App-wide singleton accessor so every screen shares one connection."""
    global _singleton
    if _singleton is None:
        _singleton = Database(db_path)
        _singleton.seed_defaults_if_empty()
    return _singleton
