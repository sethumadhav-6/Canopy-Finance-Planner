from core import budget_engine
from core.envelope_manager import record_expense


def _add_month(db, category_id, month, amount):
    record_expense(db, None, category_id, f"{month}-15", amount, merchant="Test", description="x")


def test_suggest_budget_uses_trailing_average(db, category_id):
    _add_month(db, category_id, "2026-06", 400)
    _add_month(db, category_id, "2026-07", 420)
    _add_month(db, category_id, "2026-08", 440)
    suggestion = budget_engine.suggest_budget_for_category(db, category_id, "2026-09")
    # weighted average of 400/420/440 (recent-weighted) should land near 425-440
    assert 400 <= suggestion.trailing_avg_minor / 100 <= 445
    assert suggestion.suggested_minor > 0


def test_suggest_budget_detects_upward_trend(db, category_id):
    _add_month(db, category_id, "2026-06", 200)
    _add_month(db, category_id, "2026-07", 200)
    _add_month(db, category_id, "2026-08", 500)
    suggestion = budget_engine.suggest_budget_for_category(db, category_id, "2026-09")
    assert suggestion.trend_pct > 0


def test_apply_and_manual_override(db, category_id):
    _add_month(db, category_id, "2026-08", 300)
    suggestions = budget_engine.suggest_all_budgets(db, "2026-09")
    budget_engine.apply_budget_suggestions(db, suggestions, "2026-09")

    row = db.query_one("SELECT * FROM budgets WHERE month = '2026-09' AND category_id = ?",
                        (category_id,))
    assert row is not None
    assert row["basis"] == "auto"

    budget_engine.set_manual_budget(db, "2026-09", category_id, 999)
    row = db.query_one("SELECT * FROM budgets WHERE month = '2026-09' AND category_id = ?",
                        (category_id,))
    assert row["basis"] == "manual"
    assert row["planned_minor"] == 99900

    # Re-applying auto suggestions should not clobber the manual override
    budget_engine.apply_budget_suggestions(db, suggestions, "2026-09", overwrite_manual=False)
    row = db.query_one("SELECT * FROM budgets WHERE month = '2026-09' AND category_id = ?",
                        (category_id,))
    assert row["basis"] == "manual"


def test_budget_vs_actual(db, category_id):
    budget_engine.set_manual_budget(db, "2026-09", category_id, 500)
    _add_month(db, category_id, "2026-09", 300)
    rows = budget_engine.budget_vs_actual(db, "2026-09")
    assert len(rows) == 1
    assert rows[0]["actual_minor"] == 30000
    assert rows[0]["remaining_minor"] == 20000
    assert rows[0]["pct_used"] == 60.0
