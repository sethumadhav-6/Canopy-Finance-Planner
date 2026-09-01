from core.duplicate_detector import check_and_flag, find_duplicates_for_transaction, resolve_duplicate
from core.envelope_manager import record_expense


def test_no_duplicate_for_first_purchase(db, category_id):
    txn_id = record_expense(db, None, category_id, "2026-09-01", 250, merchant="Office Mart")
    matches = find_duplicates_for_transaction(db, txn_id)
    assert matches == []


def test_flags_similar_repeat_purchase(db, category_id):
    first_id = record_expense(db, None, category_id, "2026-09-01", 250, merchant="Office Mart",
                               description="A4 paper + pens")
    second_id = record_expense(db, None, category_id, "2026-09-10", 260, merchant="Office Mart",
                                description="A4 paper + pens")
    match = check_and_flag(db, second_id)
    assert match is not None
    assert match.matched_txn_id == first_id
    assert 0 < match.score <= 1

    row = db.query_one("SELECT * FROM transactions WHERE id = ?", (second_id,))
    assert row["duplicate_of"] == first_id


def test_does_not_flag_different_category(db):
    food = db.query_one("SELECT id FROM categories WHERE name = 'Food & Dining'")["id"]
    stat = db.query_one("SELECT id FROM categories WHERE name = 'Stationery'")["id"]
    record_expense(db, None, food, "2026-09-01", 250, merchant="Notebook Cafe", description="lunch")
    second_id = record_expense(db, None, stat, "2026-09-02", 250, merchant="Notebook Cafe",
                                description="lunch")
    matches = find_duplicates_for_transaction(db, second_id)
    assert matches == []


def test_amount_too_different_not_flagged(db, category_id):
    record_expense(db, None, category_id, "2026-09-01", 250, merchant="Office Mart", description="pens")
    second_id = record_expense(db, None, category_id, "2026-09-03", 1000, merchant="Office Mart",
                                description="pens")
    matches = find_duplicates_for_transaction(db, second_id)
    assert matches == []


def test_resolve_duplicate_keep(db, category_id):
    first_id = record_expense(db, None, category_id, "2026-09-01", 250, merchant="Office Mart",
                               description="pens")
    second_id = record_expense(db, None, category_id, "2026-09-05", 255, merchant="Office Mart",
                                description="pens")
    check_and_flag(db, second_id)
    resolve_duplicate(db, second_id, keep=True)
    row = db.query_one("SELECT * FROM transactions WHERE id = ?", (second_id,))
    assert row["is_reviewed"] == 1
    assert row is not None  # not deleted


def test_resolve_duplicate_remove(db, category_id):
    first_id = record_expense(db, None, category_id, "2026-09-01", 250, merchant="Office Mart",
                               description="pens")
    second_id = record_expense(db, None, category_id, "2026-09-05", 255, merchant="Office Mart",
                                description="pens")
    check_and_flag(db, second_id)
    resolve_duplicate(db, second_id, keep=False)
    row = db.query_one("SELECT * FROM transactions WHERE id = ?", (second_id,))
    assert row is None
