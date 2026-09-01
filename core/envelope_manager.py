"""
Envelope budgeting engine -- the "custom offline envelope" system from the spec.

Each envelope is a virtual bucket (e.g. "Groceries", "Netflix vault", "New laptop
fund"). Every month gets its own envelope_balances row so allocation/spend/rollover
history is fully auditable month to month, and recurring vaults (subscriptions,
rent, EMIs) can be watched for cost creep over time.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.analytics import shift_month
from core.models import Envelope, EnvelopeStatus
from db.database import Database, to_minor


def create_envelope(
    db: Database, name: str, envelope_type: str = "discretionary",
    category_id: int | None = None, monthly_allocation_major: float = 0,
    rollover_enabled: bool = True, expected_due_day: int | None = None,
) -> int:
    return db.insert("envelopes", {
        "name": name,
        "category_id": category_id,
        "envelope_type": envelope_type,
        "monthly_allocation_minor": to_minor(monthly_allocation_major),
        "rollover_enabled": int(rollover_enabled),
        "expected_due_day": expected_due_day,
        "is_active": 1,
    })


def _get_or_create_balance_row(db: Database, envelope: Envelope, month: str) -> dict:
    row = db.query_one(
        "SELECT * FROM envelope_balances WHERE envelope_id = ? AND month = ?",
        (envelope.id, month),
    )
    if row:
        return dict(row)

    rollover_in = 0
    if envelope.rollover_enabled:
        prev_month = shift_month(month, -1)
        prev = db.query_one(
            "SELECT * FROM envelope_balances WHERE envelope_id = ? AND month = ?",
            (envelope.id, prev_month),
        )
        if prev:
            prev_remaining = prev["allocated_minor"] + prev["rollover_in_minor"] - prev["spent_minor"]
            rollover_in = max(0, prev_remaining)  # never roll over a negative balance

    new_id = db.insert("envelope_balances", {
        "envelope_id": envelope.id,
        "month": month,
        "allocated_minor": envelope.monthly_allocation_minor,
        "spent_minor": 0,
        "rollover_in_minor": rollover_in,
    })
    return dict(db.query_one("SELECT * FROM envelope_balances WHERE id = ?", (new_id,)))


def recompute_spent(db: Database, envelope_id: int, month: str) -> int:
    """Recalculate spent_minor for one envelope/month from actual transactions and cache it."""
    row = db.query_one(
        "SELECT COALESCE(SUM(amount_minor),0) AS total FROM transactions "
        "WHERE envelope_id = ? AND txn_type = 'expense' AND strftime('%Y-%m', txn_date) = ?",
        (envelope_id, month),
    )
    spent = row["total"] if row else 0
    bal = db.query_one(
        "SELECT id FROM envelope_balances WHERE envelope_id = ? AND month = ?",
        (envelope_id, month),
    )
    if bal:
        db.update("envelope_balances", bal["id"], {"spent_minor": spent})
    return spent


def get_envelope_status(db: Database, envelope_id: int, month: str) -> EnvelopeStatus:
    row = db.query_one("SELECT * FROM envelopes WHERE id = ?", (envelope_id,))
    envelope = Envelope.from_row(row)
    bal = _get_or_create_balance_row(db, envelope, month)
    spent = recompute_spent(db, envelope_id, month)
    return EnvelopeStatus(
        envelope=envelope, month=month,
        allocated_minor=bal["allocated_minor"], spent_minor=spent,
        rollover_in_minor=bal["rollover_in_minor"],
    )


def all_envelope_statuses(db: Database, month: str) -> list[EnvelopeStatus]:
    rows = db.query("SELECT id FROM envelopes WHERE is_active = 1 ORDER BY envelope_type, name")
    return [get_envelope_status(db, r["id"], month) for r in rows]


def record_expense(
    db: Database, envelope_id: int | None, category_id: int | None, txn_date: str,
    amount_major: float, merchant: str = "", description: str = "",
    payment_method: str = "other", source: str = "manual", raw_text: str = "",
) -> int:
    """
    Add a transaction and keep its envelope's cached balance in sync.
    This is the single write path the UI (and, later, SMS import) should use
    so envelope math never drifts out of sync with the transactions table.
    """
    txn_id = db.insert("transactions", {
        "txn_date": txn_date,
        "amount_minor": to_minor(amount_major),
        "txn_type": "expense",
        "category_id": category_id,
        "envelope_id": envelope_id,
        "merchant": merchant,
        "description": description,
        "payment_method": payment_method,
        "source": source,
        "raw_text": raw_text,
    })
    if envelope_id:
        month = txn_date[:7]
        env_row = db.query_one("SELECT * FROM envelopes WHERE id = ?", (envelope_id,))
        if env_row:
            _get_or_create_balance_row(db, Envelope.from_row(env_row), month)
        recompute_spent(db, envelope_id, month)
    return txn_id
