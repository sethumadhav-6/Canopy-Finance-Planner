"""
Budget projection engine.

Approach: weighted trailing average with a mild trend adjustment, entirely
local/offline (no ML service). This mirrors how a careful person would set
next month's budget by hand: look at the last few months, weight recent
months more heavily, and nudge for a clear upward/downward trend, then round
to a "clean" number so the budget is easy to track against.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.analytics import category_trend, last_n_months, shift_month
from db.database import Database, to_major, to_minor


@dataclass
class BudgetSuggestion:
    category_id: int
    category_name: str
    suggested_minor: int
    trailing_avg_minor: int
    trend_pct: float          # positive = rising spend, negative = falling
    basis_months: int


def _weighted_average(values: list[int]) -> float:
    """More recent months count more: weights 1, 2, 3, ... n (last month weighted highest)."""
    if not values:
        return 0.0
    weights = list(range(1, len(values) + 1))
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def _round_clean(amount_minor: float, step_minor: int = 5000) -> int:
    """Round to the nearest clean step (default: nearest 50 rupees) so budgets are memorable."""
    if amount_minor <= 0:
        return 0
    return int(round(amount_minor / step_minor) * step_minor)


def suggest_budget_for_category(
    db: Database, category_id: int, target_month: str, lookback_months: int = 4
) -> BudgetSuggestion:
    """
    Suggest next month's budget for one category from the last `lookback_months`
    of actual spend (not including target_month itself).
    """
    prior_month = shift_month(target_month, -1)
    history = category_trend(db, category_id, prior_month, n_months=lookback_months)
    values = [h["total_minor"] for h in history if h["total_minor"] > 0] or [h["total_minor"] for h in history]

    trailing_avg = _weighted_average(values)

    trend_pct = 0.0
    if len(values) >= 2 and values[0] > 0:
        # simple first-half vs second-half comparison to gauge direction
        mid = len(values) // 2 or 1
        first_half_avg = sum(values[:mid]) / mid
        second_half_avg = sum(values[mid:]) / max(len(values) - mid, 1)
        if first_half_avg > 0:
            trend_pct = round((second_half_avg - first_half_avg) / first_half_avg * 100, 1)

    # Nudge the average by half the observed trend -- follows the trend without overreacting
    # to one unusual month.
    adjustment = trailing_avg * (trend_pct / 100) * 0.5
    suggested = _round_clean(trailing_avg + adjustment)

    cat = db.query_one("SELECT name FROM categories WHERE id = ?", (category_id,))
    return BudgetSuggestion(
        category_id=category_id,
        category_name=cat["name"] if cat else "Unknown",
        suggested_minor=suggested,
        trailing_avg_minor=int(trailing_avg),
        trend_pct=trend_pct,
        basis_months=len(values),
    )


def suggest_all_budgets(db: Database, target_month: str, lookback_months: int = 4) -> list[BudgetSuggestion]:
    """Run suggest_budget_for_category for every category that has any spending history."""
    cats = db.query(
        """
        SELECT DISTINCT c.id, c.name FROM categories c
        JOIN transactions t ON t.category_id = c.id
        WHERE t.txn_type = 'expense'
        """
    )
    return [suggest_budget_for_category(db, c["id"], target_month, lookback_months) for c in cats]


def apply_budget_suggestions(db: Database, suggestions: list[BudgetSuggestion], target_month: str,
                              overwrite_manual: bool = False) -> int:
    """
    Persist suggestions into the budgets table for target_month. Existing manual
    overrides are preserved unless overwrite_manual=True. Returns rows written.
    """
    written = 0
    for s in suggestions:
        existing = db.query_one(
            "SELECT id, basis FROM budgets WHERE month = ? AND category_id = ?",
            (target_month, s.category_id),
        )
        if existing:
            if existing["basis"] == "manual" and not overwrite_manual:
                continue
            db.update("budgets", existing["id"], {"planned_minor": s.suggested_minor, "basis": "auto"})
        else:
            db.insert("budgets", {
                "month": target_month, "category_id": s.category_id,
                "planned_minor": s.suggested_minor, "basis": "auto",
            })
        written += 1
    return written


def set_manual_budget(db: Database, target_month: str, category_id: int, amount_major: float) -> None:
    """User explicitly overrides a category's budget for a month."""
    amount_minor = to_minor(amount_major)
    existing = db.query_one(
        "SELECT id FROM budgets WHERE month = ? AND category_id = ?", (target_month, category_id)
    )
    if existing:
        db.update("budgets", existing["id"], {"planned_minor": amount_minor, "basis": "manual"})
    else:
        db.insert("budgets", {
            "month": target_month, "category_id": category_id,
            "planned_minor": amount_minor, "basis": "manual",
        })


def budget_vs_actual(db: Database, month: str) -> list[dict]:
    """Full budget-vs-actual table for a month -- what the Budget screen renders."""
    rows = db.query(
        """
        SELECT b.category_id, c.name, c.color_hex, c.icon, b.planned_minor, b.basis,
               COALESCE(SUM(t.amount_minor), 0) AS actual_minor
        FROM budgets b
        JOIN categories c ON c.id = b.category_id
        LEFT JOIN transactions t
          ON t.category_id = b.category_id AND t.txn_type = 'expense'
         AND strftime('%Y-%m', t.txn_date) = b.month
        WHERE b.month = ?
        GROUP BY b.category_id
        ORDER BY actual_minor DESC
        """,
        (month,),
    )
    out = []
    for r in rows:
        planned, actual = r["planned_minor"], r["actual_minor"]
        out.append({
            "category_id": r["category_id"], "name": r["name"], "color_hex": r["color_hex"],
            "icon": r["icon"], "planned_minor": planned, "actual_minor": actual,
            "basis": r["basis"],
            "remaining_minor": planned - actual,
            "pct_used": round((actual / planned * 100), 1) if planned > 0 else 0.0,
        })
    return out
