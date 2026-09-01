"""
Offline, rule-based parser for Indian bank/UPI transaction SMS.

No network, no ML -- just regex over common templates banks and UPI apps use
(HDFC/SBI/ICICI/Axis/Kotak-style debit/credit alerts, GPay/PhonePe/Paytm-style
UPI confirmations). Bank SMS formats vary and change without notice and this
lexicon will need upkeep, but it's a reasonable, fully-offline starting point,
and every result is a *suggestion* -- nothing here ever writes to the real
transactions table directly (see core/sms_import.py for the staging/review
flow that owns that decision).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

# ---- classification keywords -------------------------------------------------

DEBIT_KEYWORDS = [
    "debited", "debited with", "spent", "spent on", "paid", "payment of",
    "sent", "withdrawn", "purchase of", "txn of", "deducted",
]
CREDIT_KEYWORDS = [
    "credited", "credited with", "received", "deposited", "refund of",
    "cashback of", "reversed",
]
# SMS that are very likely NOT a transaction alert (OTP, promo, reminders...) --
# checked first so we don't misparse "Rs.500 cashback offer!" as real income.
IGNORE_KEYWORDS = [
    "otp", "one time password", "do not share", "won't be liable",
    "will expire in", "verification code", "is your", "reminder:",
    "offer", "cashback upto", "win ", "lucky draw", "click here", "download",
    "minimum due", "bill generated", "statement is ready", "emi due on",
]

AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|₹)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE
)
ACCOUNT_RE = re.compile(r"a/?c\.?\s*(?:no\.?)?\s*[xX*]*\s*(\d{3,6})", re.IGNORECASE)
CARD_RE = re.compile(r"card\s*(?:no\.?)?\s*(?:ending|ending in|xx+)?\s*(\d{3,4})", re.IGNORECASE)
VPA_RE = re.compile(r"(?:vpa|to|from)\s+([a-zA-Z0-9.\-_]+@[a-zA-Z]+)", re.IGNORECASE)
# "at MERCHANT on" / "at MERCHANT," -- greedy-but-bounded merchant name capture
MERCHANT_AT_RE = re.compile(r"\bat\s+([A-Za-z0-9&'.\-\s]{2,40}?)(?:\s+on\b|\s+dated\b|,|\.|$)", re.IGNORECASE)

DATE_PATTERNS = [
    (re.compile(r"\b(\d{2})-(\d{2})-(\d{2,4})\b"), "%d-%m-%Y"),   # 01-09-2026 or 01-09-26
    (re.compile(r"\b(\d{2})/(\d{2})/(\d{2,4})\b"), "%d/%m/%Y"),
    (re.compile(r"\b(\d{2})-([A-Za-z]{3})-(\d{2,4})\b"), "%d-%b-%Y"),  # 01-Sep-2026
]


@dataclass
class ParsedSmsTransaction:
    amount_major: float
    txn_type: str                  # 'expense' or 'income'
    txn_date: str                  # 'YYYY-MM-DD' -- falls back to the SMS's received date
    merchant: str = ""
    account_hint: str = ""          # last 3-6 digits of account/card, for the user's reference only
    confidence: float = 0.0         # 0..1, rough heuristic -- higher = more fields matched
    raw_text: str = ""


def _normalize_year(y: str) -> int:
    if len(y) == 2:
        return 2000 + int(y)
    return int(y)


def _extract_date(text: str, received_date: date) -> str:
    for pattern, _fmt in DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            if _fmt == "%d-%b-%Y":
                day, mon_str, year = m.groups()
                dt = datetime.strptime(f"{day}-{mon_str}-{_normalize_year(year)}", "%d-%b-%Y")
            else:
                day, month, year = m.groups()
                dt = datetime(_normalize_year(year), int(month), int(day))
            return dt.date().isoformat()
        except ValueError:
            continue
    return received_date.isoformat()


def _extract_merchant(text: str) -> str:
    m = VPA_RE.search(text)
    if m:
        return m.group(1)
    m = MERCHANT_AT_RE.search(text)
    if m:
        return m.group(1).strip()
    return ""


def is_likely_transaction_sms(text: str) -> bool:
    low = text.lower()
    if any(kw in low for kw in IGNORE_KEYWORDS):
        return False
    if not AMOUNT_RE.search(text):
        return False
    return any(kw in low for kw in DEBIT_KEYWORDS + CREDIT_KEYWORDS)


def parse_sms(text: str, received_at: Optional[date] = None) -> Optional[ParsedSmsTransaction]:
    """
    Best-effort parse of one SMS body. Returns None when the message doesn't
    look like a transaction alert at all (OTPs, promos, bill reminders...).
    Every non-None result should still go through user review before it
    becomes a real transaction -- see core/sms_import.py.
    """
    received_at = received_at or date.today()
    if not text or not text.strip():
        return None
    low = text.lower()

    if any(kw in low for kw in IGNORE_KEYWORDS):
        return None

    amount_match = AMOUNT_RE.search(text)
    if not amount_match:
        return None
    try:
        amount = float(amount_match.group(1).replace(",", ""))
    except ValueError:
        return None
    if amount <= 0:
        return None

    is_debit = any(kw in low for kw in DEBIT_KEYWORDS)
    is_credit = any(kw in low for kw in CREDIT_KEYWORDS)
    if not is_debit and not is_credit:
        return None
    # If a message somehow matches both (rare), prefer debit -- safer default
    # for a budgeting app (won't inflate income and mask overspending).
    txn_type = "income" if (is_credit and not is_debit) else "expense"

    account_match = ACCOUNT_RE.search(text) or CARD_RE.search(text)
    merchant = _extract_merchant(text)
    txn_date = _extract_date(text, received_at)

    # Confidence: base for amount+direction match, plus bonuses for the extras
    # that make the parse more trustworthy / more useful to pre-fill.
    confidence = 0.5
    if account_match:
        confidence += 0.15
    if merchant:
        confidence += 0.2
    if txn_date != received_at.isoformat():
        confidence += 0.15
    confidence = min(1.0, confidence)

    return ParsedSmsTransaction(
        amount_major=amount,
        txn_type=txn_type,
        txn_date=txn_date,
        merchant=merchant,
        account_hint=account_match.group(1) if account_match else "",
        confidence=round(confidence, 2),
        raw_text=text,
    )
