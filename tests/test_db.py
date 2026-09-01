from db.database import to_major, to_minor


def test_seed_defaults_populates_categories(db):
    rows = db.query("SELECT * FROM categories")
    assert len(rows) >= 10
    names = {r["name"] for r in rows}
    assert "Stationery" in names and "Household Supplies" in names


def test_seed_is_idempotent(db):
    before = db.query_one("SELECT COUNT(*) AS n FROM categories")["n"]
    db.seed_defaults_if_empty()
    after = db.query_one("SELECT COUNT(*) AS n FROM categories")["n"]
    assert before == after


def test_minor_major_roundtrip():
    assert to_minor(149.50) == 14950
    assert to_major(14950) == 149.50
    assert to_minor(0) == 0


def test_insert_update_delete(db, category_id):
    txn_id = db.insert("transactions", {
        "txn_date": "2026-09-01", "amount_minor": to_minor(250),
        "txn_type": "expense", "category_id": category_id, "merchant": "Office Mart",
    })
    row = db.query_one("SELECT * FROM transactions WHERE id = ?", (txn_id,))
    assert row["merchant"] == "Office Mart"

    db.update("transactions", txn_id, {"merchant": "Office Mart Updated"})
    row = db.query_one("SELECT * FROM transactions WHERE id = ?", (txn_id,))
    assert row["merchant"] == "Office Mart Updated"

    db.delete("transactions", txn_id)
    row = db.query_one("SELECT * FROM transactions WHERE id = ?", (txn_id,))
    assert row is None
