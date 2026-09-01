"""Lightweight dataclasses used to pass rows around the app without exposing sqlite3.Row."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Category:
    id: int
    name: str
    group_name: str = "other"
    icon: str = "shape-outline"
    color_hex: str = "#7C83FD"
    is_recurring: bool = False
    is_system: bool = False

    @classmethod
    def from_row(cls, row) -> "Category":
        return cls(
            id=row["id"], name=row["name"], group_name=row["group_name"],
            icon=row["icon"], color_hex=row["color_hex"],
            is_recurring=bool(row["is_recurring"]), is_system=bool(row["is_system"]),
        )


@dataclass
class Transaction:
    id: int
    txn_date: str
    amount_minor: int
    txn_type: str = "expense"
    category_id: Optional[int] = None
    envelope_id: Optional[int] = None
    merchant: str = ""
    description: str = ""
    payment_method: str = "other"
    source: str = "manual"
    raw_text: str = ""
    duplicate_of: Optional[int] = None
    duplicate_score: Optional[float] = None
    is_reviewed: bool = False

    @classmethod
    def from_row(cls, row) -> "Transaction":
        return cls(
            id=row["id"], txn_date=row["txn_date"], amount_minor=row["amount_minor"],
            txn_type=row["txn_type"], category_id=row["category_id"], envelope_id=row["envelope_id"],
            merchant=row["merchant"] or "", description=row["description"] or "",
            payment_method=row["payment_method"] or "other", source=row["source"] or "manual",
            raw_text=row["raw_text"] or "", duplicate_of=row["duplicate_of"],
            duplicate_score=row["duplicate_score"], is_reviewed=bool(row["is_reviewed"]),
        )


@dataclass
class Envelope:
    id: int
    name: str
    category_id: Optional[int]
    envelope_type: str = "discretionary"      # discretionary, recurring_vault, savings_goal
    monthly_allocation_minor: int = 0
    rollover_enabled: bool = True
    expected_due_day: Optional[int] = None
    is_active: bool = True

    @classmethod
    def from_row(cls, row) -> "Envelope":
        return cls(
            id=row["id"], name=row["name"], category_id=row["category_id"],
            envelope_type=row["envelope_type"],
            monthly_allocation_minor=row["monthly_allocation_minor"],
            rollover_enabled=bool(row["rollover_enabled"]),
            expected_due_day=row["expected_due_day"], is_active=bool(row["is_active"]),
        )


@dataclass
class EnvelopeStatus:
    """Computed view of one envelope for one month -- what the UI actually renders."""
    envelope: Envelope
    month: str
    allocated_minor: int
    spent_minor: int
    rollover_in_minor: int = 0

    @property
    def remaining_minor(self) -> int:
        return self.allocated_minor + self.rollover_in_minor - self.spent_minor

    @property
    def pct_used(self) -> float:
        total = self.allocated_minor + self.rollover_in_minor
        if total <= 0:
            return 0.0
        return max(0.0, min(999.0, (self.spent_minor / total) * 100))

    @property
    def is_over(self) -> bool:
        return self.remaining_minor < 0
