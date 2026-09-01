from core import analytics
from core.envelope_manager import record_expense


def test_shift_month_wraps_year():
    assert analytics.shift_month("2026-01", -1) == "2025-12"
    assert analytics.shift_month("2026-12", 1) == "2027-01"


def test_last_n_months_order():
    months = analytics.last_n_months("2026-09", 3)
    assert months == ["2026-07", "2026-08", "2026-09"]


def test_monthly_total(db, category_id):
    record_expense(db, None, category_id, "2026-09-01", 100, merchant="A")
    record_expense(db, None, category_id, "2026-09-15", 50, merchant="B")
    record_expense(db, None, category_id, "2026-08-15", 999, merchant="C")  # different month
    assert analytics.monthly_total(db, "2026-09") == 15000


def test_spend_by_category_sorted_desc(db):
    stat = db.query_one("SELECT id FROM categories WHERE name = 'Stationery'")["id"]
    food = db.query_one("SELECT id FROM categories WHERE name = 'Food & Dining'")["id"]
    record_expense(db, None, stat, "2026-09-01", 50, merchant="A")
    record_expense(db, None, food, "2026-09-01", 500, merchant="B")
    rows = analytics.spend_by_category(db, "2026-09")
    assert rows[0]["name"] == "Food & Dining"
    assert rows[0]["total_minor"] == 50000


def test_top_overspend_alerts(db, category_id):
    db.insert("budgets", {"month": "2026-09", "category_id": category_id, "planned_minor": 10000})
    record_expense(db, None, category_id, "2026-09-01", 150, merchant="A")
    alerts = analytics.top_overspend_alerts(db, "2026-09", threshold_pct=100.0)
    assert len(alerts) == 1
    assert alerts[0]["pct"] == 150.0
