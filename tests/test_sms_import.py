from datetime import date

from core.sms_import import (approve_sms, bulk_stage_from_messages, pending_sms_staging,
                              reject_sms, stage_sms)


def test_stage_valid_sms(db):
    sid = stage_sms(db, "Rs.450.00 debited from A/c XX1234 on 01-09-26 to VPA officemart@ybl.",
                      sender="HDFCBK")
    assert sid is not None
    row = db.query_one("SELECT * FROM sms_staging WHERE id = ?", (sid,))
    assert row["status"] == "pending"
    assert row["parsed_amount_minor"] == 45000
    assert row["parsed_txn_type"] == "expense"


def test_stage_non_transaction_sms_returns_none(db):
    sid = stage_sms(db, "Your OTP is 384921. Do not share.")
    assert sid is None
    assert db.query_one("SELECT COUNT(*) AS n FROM sms_staging")["n"] == 0


def test_pending_list_sorted_by_confidence(db):
    stage_sms(db, "Rs.99 debited from A/c XX0001 to VPA lowconf@upi.")  # no date -> lower confidence
    stage_sms(db, "Rs.450.00 debited from A/c XX1234 on 01-09-26 to VPA officemart@ybl.")
    pending = pending_sms_staging(db)
    assert len(pending) == 2
    assert pending[0]["confidence"] >= pending[1]["confidence"]


def test_approve_creates_real_transaction(db, category_id):
    sid = stage_sms(db, "Rs.450.00 debited from A/c XX1234 on 01-09-26 to VPA officemart@ybl.")
    txn_id = approve_sms(db, sid, category_id=category_id)
    assert txn_id is not None

    txn = db.query_one("SELECT * FROM transactions WHERE id = ?", (txn_id,))
    assert txn["amount_minor"] == 45000
    assert txn["source"] == "sms"
    assert txn["category_id"] == category_id

    staging = db.query_one("SELECT * FROM sms_staging WHERE id = ?", (sid,))
    assert staging["status"] == "approved"
    assert staging["resulting_txn_id"] == txn_id


def test_approve_falls_back_to_auto_category(db):
    sid = stage_sms(db, "Rs.300.00 spent at SWIGGY on 01-09-26 using your card.")
    txn_id = approve_sms(db, sid)
    txn = db.query_one("SELECT * FROM transactions WHERE id = ?", (txn_id,))
    cat = db.query_one("SELECT name FROM categories WHERE id = ?", (txn["category_id"],))
    assert cat["name"] == "Food & Dining"


def test_approve_income_sms(db):
    sid = stage_sms(db, "Your A/c XX9988 is credited with Rs.50000.00 on 01-09-2026 by NEFT from EMPLOYER LTD.")
    txn_id = approve_sms(db, sid)
    txn = db.query_one("SELECT * FROM transactions WHERE id = ?", (txn_id,))
    assert txn["txn_type"] == "income"
    assert txn["amount_minor"] == 5000000


def test_reject_sms(db):
    sid = stage_sms(db, "Rs.450.00 debited from A/c XX1234 on 01-09-26 to VPA officemart@ybl.")
    reject_sms(db, sid)
    row = db.query_one("SELECT status FROM sms_staging WHERE id = ?", (sid,))
    assert row["status"] == "rejected"
    assert pending_sms_staging(db) == []


def test_cannot_double_approve(db):
    sid = stage_sms(db, "Rs.450.00 debited from A/c XX1234 on 01-09-26 to VPA officemart@ybl.")
    first = approve_sms(db, sid)
    second = approve_sms(db, sid)
    assert first is not None
    assert second is None  # already approved, no-op


def test_bulk_stage_dedupes_and_skips_non_transactions(db):
    messages = [
        {"text": "Rs.450.00 debited from A/c XX1234 on 01-09-26 to VPA officemart@ybl.",
         "sender": "HDFCBK", "received_at": date(2026, 9, 1)},
        {"text": "Rs.450.00 debited from A/c XX1234 on 01-09-26 to VPA officemart@ybl.",
         "sender": "HDFCBK", "received_at": date(2026, 9, 1)},  # exact duplicate SMS
        {"text": "Your OTP is 123456.", "sender": "VM-OTP", "received_at": date(2026, 9, 1)},
    ]
    result = bulk_stage_from_messages(db, messages)
    assert result.scanned == 3
    assert result.staged == 1
    assert len(pending_sms_staging(db)) == 1


def test_approve_duplicate_subscription_sms_gets_flagged(db, category_id):
    # Simulates the classic "same subscription charged twice" case surfacing via SMS.
    sid1 = stage_sms(db, "Rs.199.00 debited from A/c XX1234 on 01-09-26 to VPA netflix@upi.")
    sid2 = stage_sms(db, "Rs.199.00 debited from A/c XX1234 on 02-09-26 to VPA netflix@upi.")
    first_txn = approve_sms(db, sid1, category_id=category_id)
    second_txn = approve_sms(db, sid2, category_id=category_id)
    row = db.query_one("SELECT * FROM transactions WHERE id = ?", (second_txn,))
    assert row["duplicate_of"] == first_txn
