from core.categorizer import learn_from_correction, suggest_category_id


def test_keyword_lexicon_match(db):
    cat_id = suggest_category_id(db, "SWIGGY*ORDER1234")
    row = db.query_one("SELECT name FROM categories WHERE id = ?", (cat_id,))
    assert row["name"] == "Food & Dining"


def test_no_match_returns_none(db):
    cat_id = suggest_category_id(db, "XYZQWERTY123")
    assert cat_id is None


def test_learned_rule_overrides_future_lookups(db):
    stationery_id = db.query_one("SELECT id FROM categories WHERE name = 'Stationery'")["id"]
    learn_from_correction(db, "ACME General Store", stationery_id)
    cat_id = suggest_category_id(db, "ACME General Store", "monthly restock")
    assert cat_id == stationery_id


def test_learned_rule_beats_keyword_lexicon(db):
    # "ACME cafe" would keyword-match Food & Dining, but a learned rule should win.
    stationery_id = db.query_one("SELECT id FROM categories WHERE name = 'Stationery'")["id"]
    learn_from_correction(db, "acme cafe", stationery_id)
    cat_id = suggest_category_id(db, "ACME Cafe")
    assert cat_id == stationery_id
