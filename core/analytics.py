"""
Trend/analytics computations that back the charts and the dashboard.
Everything here is pure SQL + Python aggregation over the local sqlite file --
no external services.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from db.database import Database, to_major


def month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def shift_month(month: str, delta: int) -> str:
    """'2026-09' shifted by -1 -> '2026-08', by +1 -> '2026-10'."""
    y, m = (int(x) for x in month.split("-"))
    total = y * 12 + (m - 1) + delta
    y2, m2 = divmod(total, 12)
    return f"{y2:04d}-{m2 + 1:02d}"

def last_n_months(month: str, n: int) -> list[str]:
    return [shift_month(month, -i) for i in range(n - 1, -1, -1)]


def monthly_total(db: Database, month: str, txn_type: str = "expense") -> int:
    row = db.query_one(
        "SELECT COALESCE(SUM(amount_minor),0) AS total FROM transactions "
        "WHERE strftime('%Y-%m', txn_date) = ? AND txn_type = ?",
        (month, txn_type),
    )
    return row["total"] if row else 0


def spend_by_category(db: Database, month: str) -> list[dict]:
    """Category breakdown for one month, sorted highest spend first -- feeds the trends screen."""
    rows = db.query(
        """
        SELECT c.id AS category_id, c.name, c.color_hex, c.icon,
               COALESCE(SUM(t.amount_minor), 0) AS total_minor,
               COUNT(t.id) AS txn_count
        FROM categories c
        LEFT JOIN transactions t
          ON t.category_id = c.id AND t.txn_type = 'expense'
         AND strftime('%Y-%m', t.txn_date) = ?
        GROUP BY c.id
        HAVING total_minor > 0
        ORDER BY total_minor DESC
        """,
        (month,),
    )
    return [dict(r) for r in rows]


def monthly_trend(db: Database, end_month: str, n_months: int = 6) -> list[dict]:
    """Total expense per month for the last n_months, oldest first -- the trend line chart."""
    months = last_n_months(end_month, n_months)
    out = []
    for m in months:
        total = monthly_total(db, m, "expense")
        out.append({"month": m, "total_minor": total, "total_major": to_major(total)})
    return out


def category_trend(db: Database, category_id: int, end_month: str, n_months: int = 6) -> list[dict]:
    """Same as monthly_trend but scoped to one category -- 'am I improving on dining out?'."""
    months = last_n_months(end_month, n_months)
    out = []
    for m in months:
        row = db.query_one(
            "SELECT COALESCE(SUM(amount_minor),0) AS total FROM transactions "
            "WHERE category_id = ? AND txn_type = 'expense' AND strftime('%Y-%m', txn_date) = ?",
            (category_id, m),
        )
        total = row["total"] if row else 0
        out.append({"month": m, "total_minor": total, "total_major": to_major(total)})
    return out


def top_overspend_alerts(db: Database, month: str, threshold_pct: float = 100.0) -> list[dict]:
    """
    Categories where actual spend has already met/exceeded the planned budget for
    the month -- this is the 'where am I spending too much' surfacing logic.
    """
    rows = db.query(
        """
        SELECT b.category_id, c.name, c.color_hex, b.planned_minor,
               COALESCE(SUM(t.amount_minor), 0) AS spent_minor
        FROM budgets b
        JOIN categories c ON c.id = b.category_id
        LEFT JOIN transactions t
          ON t.category_id = b.category_id AND t.txn_type = 'expense'
         AND strftime('%Y-%m', t.txn_date) = b.month
        WHERE b.month = ?
        GROUP BY b.category_id
        """,
        (month,),
    )
    alerts = []
    for r in rows:
        planned = r["planned_minor"] or 0
        spent = r["spent_minor"] or 0
        if planned <= 0:
            continue
        pct = (spent / planned) * 100
        if pct >= threshold_pct:
            alerts.append({
                "category_id": r["category_id"], "name": r["name"], "color_hex": r["color_hex"],
                "planned_minor": planned, "spent_minor": spent, "pct": round(pct, 1),
            })
    alerts.sort(key=lambda a: a["pct"], reverse=True)
    return alerts


def recurring_vault_drift(db: Database, month: str) -> list[dict]:
    """
    For envelopes of type 'recurring_vault' (rent, subscriptions, EMIs...), compare
    actual spend this month against the envelope's steady monthly_allocation_minor --
    flags creeping subscription costs ("this vault crept up 18% vs its usual cost").
    """
    rows = db.query(
        """
        SELECT e.id AS envelope_id, e.name, e.monthly_allocation_minor,
               COALESCE(SUM(t.amount_minor), 0) AS spent_minor
        FROM envelopes e
        LEFT JOIN transactions t
          ON t.envelope_id = e.id AND t.txn_type = 'expense'
         AND strftime('%Y-%m', t.txn_date) = ?
        WHERE e.envelope_type = 'recurring_vault' AND e.is_active = 1
        GROUP BY e.id
        """,
        (month,),
    )
    out = []
    for r in rows:
        baseline = r["monthly_allocation_minor"] or 0
        spent = r["spent_minor"] or 0
        drift_pct = ((spent - baseline) / baseline * 100) if baseline > 0 else 0.0
        out.append({
            "envelope_id": r["envelope_id"], "name": r["name"],
            "baseline_minor": baseline, "spent_minor": spent,
            "drift_pct": round(drift_pct, 1),
        })
    out.sort(key=lambda a: a["drift_pct"], reverse=True)
    return out
