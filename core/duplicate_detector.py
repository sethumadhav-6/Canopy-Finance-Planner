"""
Offline duplicate / near-duplicate purchase detector.

Purpose (per spec): catch accidental repeat purchases -- classic cases are
stationery and household restocking where the user forgets they already
bought pens/detergent/etc. two weeks ago. Runs entirely on-device, no network,
no ML -- just date proximity + amount tolerance + fuzzy text match.

A transaction is flagged as a *possible* duplicate, never auto-merged or
auto-deleted -- the user always makes the final call (is_reviewed flag).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional

from db.database import Database

# Only worth flagging within these categories by default -- restockable
# consumables are where accidental repeat buys actually happen. Configurable
# by the caller if the user wants a wider net.
DEFAULT_WATCH_GROUPS = {"stationery", "household"}

DATE_WINDOW_DAYS = 21          # look back/forward this many days for a possible dup
AMOUNT_TOLERANCE_PCT = 0.15    # amounts within +/-15% count as "similar"
TEXT_SIMILARITY_THRESHOLD = 0.55  # difflib ratio 0..1 on merchant+description


@dataclass
class DuplicateCandidate:
    new_txn_id: int
    matched_txn_id: int
    score: float          # 0..1 combined confidence
    reason: str            # human-readable explanation for the UI


def _text_similarity(a: str, b: str) -> float:
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _amount_close(a_minor: int, b_minor: int, tolerance_pct: float) -> bool:
    if a_minor == 0 or b_minor == 0:
        return a_minor == b_minor
    diff = abs(a_minor - b_minor) / max(a_minor, b_minor)
    return diff <= tolerance_pct


def find_duplicates_for_transaction(
    db: Database,
    txn_id: int,
    watch_groups: set[str] = DEFAULT_WATCH_GROUPS,
    date_window_days: int = DATE_WINDOW_DAYS,
    amount_tolerance_pct: float = AMOUNT_TOLERANCE_PCT,
    text_threshold: float = TEXT_SIMILARITY_THRESHOLD,
) -> list[DuplicateCandidate]:
    """Check one newly-added/edited transaction against nearby history for possible dupes."""
    txn = db.query_one("SELECT * FROM transactions WHERE id = ?", (txn_id,))
    if not txn:
        return []

    cat = db.query_one("SELECT group_name FROM categories WHERE id = ?", (txn["category_id"],)) \
        if txn["category_id"] else None
    if cat is None or cat["group_name"] not in watch_groups:
        return []

    txn_date = datetime.strptime(txn["txn_date"], "%Y-%m-%d").date()
    lo = (txn_date - timedelta(days=date_window_days)).isoformat()
    hi = (txn_date + timedelta(days=date_window_days)).isoformat()

    candidates = db.query(
        """
        SELECT * FROM transactions
        WHERE id != ? AND category_id = ? AND txn_date BETWEEN ? AND ?
          AND txn_type = 'expense'
        """,
        (txn_id, txn["category_id"], lo, hi),
    )

    results: list[DuplicateCandidate] = []
    for c in candidates:
        if not _amount_close(txn["amount_minor"], c["amount_minor"], amount_tolerance_pct):
            continue
        sim = _text_similarity(
            f"{txn['merchant']} {txn['description']}",
            f"{c['merchant']} {c['description']}",
        )
        if sim < text_threshold:
            continue
        days_apart = abs((txn_date - datetime.strptime(c["txn_date"], "%Y-%m-%d").date()).days)
        # Weighted score: text similarity matters most, closeness in time and amount boost confidence.
        score = round(0.55 * sim + 0.30 * (1 - days_apart / max(date_window_days, 1)) + 0.15, 3)
        score = max(0.0, min(1.0, score))
        results.append(DuplicateCandidate(
            new_txn_id=txn_id,
            matched_txn_id=c["id"],
            score=score,
            reason=(f"Similar {c['merchant'] or 'purchase'} for a close amount "
                    f"{days_apart} day(s) apart"),
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results


def flag_transaction(db: Database, candidate: DuplicateCandidate) -> None:
    """Persist the strongest duplicate match on the transaction row for the UI to surface."""
    db.update("transactions", candidate.new_txn_id, {
        "duplicate_of": candidate.matched_txn_id,
        "duplicate_score": candidate.score,
        "is_reviewed": 0,
    })


def check_and_flag(db: Database, txn_id: int) -> Optional[DuplicateCandidate]:
    """Convenience wrapper: find + persist the top duplicate candidate, if any."""
    matches = find_duplicates_for_transaction(db, txn_id)
    if not matches:
        return None
    top = matches[0]
    flag_transaction(db, top)
    return top


def unresolved_duplicates(db: Database) -> list[dict]:
    """All transactions still awaiting a user decision on a flagged duplicate."""
    rows = db.query(
        """
        SELECT t.*, m.merchant AS matched_merchant, m.txn_date AS matched_date,
               m.amount_minor AS matched_amount_minor
        FROM transactions t
        JOIN transactions m ON m.id = t.duplicate_of
        WHERE t.duplicate_of IS NOT NULL AND t.is_reviewed = 0
        ORDER BY t.txn_date DESC
        """
    )
    return [dict(r) for r in rows]


def resolve_duplicate(db: Database, txn_id: int, keep: bool) -> None:
    """
    User decision on a flagged duplicate.
    keep=True  -> it's a legitimate separate purchase, clear the flag.
    keep=False -> it really was a duplicate entry, delete this transaction row.
    """
    if keep:
        db.update("transactions", txn_id, {"is_reviewed": 1})
    else:
        db.delete("transactions", txn_id)
