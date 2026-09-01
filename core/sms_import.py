"""
SMS staging/review workflow -- the layer between core.sms_parser (pure text ->
parsed fields) and the real transactions table. Nothing here ever auto-commits
a transaction: every parsed SMS sits in sms_staging with status='pending'
until a user explicitly approves or rejects it (see ui/screens/settings_screen.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from core.categorizer import learn_from_correction, suggest_category_id
from core.duplicate_detector import check_and_flag
from core.envelope_manager import record_expense
from core.sms_parser import parse_sms
from db.database import Database, to_major, to_minor

# Parses below this confidence still get staged (so nothing is silently
# dropped) but are visually deprioritized/flagged as "low confidence" in the
# review UI -- see ui/screens/settings_screen.py.
LOW_CONFIDENCE_THRESHOLD = 0.55


def stage_sms(db: Database, raw_text: str, sender: str = "", received_at: Optional[date] = None) -> Optional[int]:
    """
    Parse one SMS and add it to the review queue if it looks like a transaction.
    Returns the new sms_staging row id, or None if the message was ignored
    (OTP/promo/no amount/etc -- see core.sms_parser.parse_sms).
    Safe to call repeatedly on the same inbox scan; callers should dedupe by
    raw_text+received_at themselves if re-scanning (see android/sms_reader.py).
    """
    received_at = received_at or date.today()
    parsed = parse_sms(raw_text, received_at)
    if parsed is None:
        return None
    return db.insert("sms_staging", {
        "received_at": received_at.isoformat(),
        "sender": sender,
        "raw_text": raw_text,
        "parsed_amount_minor": to_minor(parsed.amount_major),
        "parsed_txn_type": parsed.txn_type,
        "parsed_txn_date": parsed.txn_date,
        "parsed_merchant": parsed.merchant,
        "parsed_account_hint": parsed.account_hint,
        "confidence": parsed.confidence,
        "status": "pending",
    })


@dataclass
class BulkImportResult:
    scanned: int
    staged: int
    ignored: int


def bulk_stage_from_messages(db: Database, messages: list[dict]) -> BulkImportResult:
    """
    messages: list of {"text": str, "sender": str, "received_at": date} dicts,
    as produced by android/sms_reader.py's inbox scan. Skips SMS whose raw_text
    is already staged (by exact match) so re-scans don't create duplicates.
    """
    staged = 0
    for m in messages:
        existing = db.query_one(
            "SELECT id FROM sms_staging WHERE raw_text = ?", (m["text"],)
        )
        if existing:
            continue
        result = stage_sms(db, m["text"], m.get("sender", ""), m.get("received_at"))
        if result is not None:
            staged += 1
    return BulkImportResult(scanned=len(messages), staged=staged, ignored=len(messages) - staged)


def pending_sms_staging(db: Database) -> list[dict]:
    rows = db.query(
        "SELECT * FROM sms_staging WHERE status = 'pending' ORDER BY confidence DESC, received_at DESC"
    )
    return [dict(r) for r in rows]


def approve_sms(db: Database, staging_id: int, category_id: Optional[int] = None,
                 envelope_id: Optional[int] = None) -> Optional[int]:
    """
    Turn a staged SMS into a real transaction. If no category is given, falls
    back to the offline categorizer's best guess from the merchant text.
    Runs duplicate detection on the resulting transaction just like a manual
    entry would (repeated subscription SMS are a classic case this catches).
    Returns the new transaction id.
    """
    staging = db.query_one("SELECT * FROM sms_staging WHERE id = ?", (staging_id,))
    if not staging or staging["status"] != "pending":
        return None

    resolved_category_id = category_id or suggest_category_id(db, staging["parsed_merchant"] or "")

    if staging["parsed_txn_type"] == "income":
        txn_id = db.insert("transactions", {
            "txn_date": staging["parsed_txn_date"],
            "amount_minor": staging["parsed_amount_minor"],
            "txn_type": "income",
            "category_id": resolved_category_id,
            "envelope_id": envelope_id,
            "merchant": staging["parsed_merchant"] or "",
            "source": "sms",
            "raw_text": staging["raw_text"],
        })
    else:
        txn_id = record_expense(
            db, envelope_id, resolved_category_id, staging["parsed_txn_date"],
            to_major(staging["parsed_amount_minor"]), merchant=staging["parsed_merchant"] or "",
            source="sms", raw_text=staging["raw_text"],
        )
        check_and_flag(db, txn_id)

    if resolved_category_id and staging["parsed_merchant"]:
        learn_from_correction(db, staging["parsed_merchant"], resolved_category_id)

    db.update("sms_staging", staging_id, {"status": "approved", "resulting_txn_id": txn_id})
    return txn_id


def reject_sms(db: Database, staging_id: int) -> None:
    db.update("sms_staging", staging_id, {"status": "rejected"})
