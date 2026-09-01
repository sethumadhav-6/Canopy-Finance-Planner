"""
Rule-based, fully offline transaction categorizer.

Two layers, cheapest first:
  1. merchant_rules table -- exact substring matches the app has "learned" from
     the user's own past corrections (see learn_from_correction()).
  2. A built-in keyword lexicon covering common Indian retail/merchant naming
     patterns, used as a fallback for new/unseen merchants.

No network, no ML model -- keeps the app fully usable offline and keeps
behaviour predictable/explainable to the user ("why was this categorized here?").
"""
from __future__ import annotations

from typing import Optional

from db.database import Database

# group_name -> list of keywords/substrings looked for in merchant+description (lowercased)
KEYWORD_LEXICON: dict[str, list[str]] = {
    "Groceries": ["grocery", "supermarket", "bigbasket", "grofers", "blinkit", "zepto",
                  "dmart", "more retail", "reliance fresh", "kirana"],
    "Stationery": ["stationery", "stationary", "notebook", "pen ", "printer ink",
                   "office depot", "staples"],
    "Household Supplies": ["household", "cleaning", "detergent", "utensil", "homecentre",
                            "home centre", "hardware store"],
    "Rent": ["rent", "landlord", "lease payment"],
    "Utilities": ["electricity", "water bill", "power bill", "gas bill", "broadband",
                  "wifi bill", "dth recharge", "mobile recharge", "airtel", "jio", "vodafone", "bsnl"],
    "Subscriptions": ["netflix", "prime video", "spotify", "hotstar", "youtube premium",
                       "subscription", "icloud", "google one", "playstation plus", "xbox live"],
    "Transport": ["uber", "ola", "rapido", "petrol", "diesel", "fuel", "metro card",
                  "toll", "parking", "irctc", "railway", "flight", "indigo", "vistara"],
    "Food & Dining": ["restaurant", "swiggy", "zomato", "cafe", "food court", "dominos",
                       "mcdonald", "kfc", "starbucks", "dining"],
    "Health": ["pharmacy", "medplus", "apollo", "hospital", "clinic", "doctor",
               "diagnostic", "medical store", "gym", "fitness"],
    "Entertainment": ["bookmyshow", "cinema", "movie", "pvr", "inox", "concert", "gaming"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho", "mall", "shopping"],
    "Savings & Investments": ["mutual fund", "sip ", "zerodha", "groww", "nps ", "fixed deposit", "rd account"],
    "Income": ["salary", "credited", "refund", "cashback", "interest credit", "reimbursement"],
}


def suggest_category_id(db: Database, merchant: str, description: str = "") -> Optional[int]:
    """Best-effort category guess for a new transaction. Returns None if nothing matches."""
    text = f"{merchant} {description}".strip().lower()
    if not text:
        return None

    # Layer 1: learned merchant rules (most specific / user-confirmed first)
    rules = db.query(
        "SELECT merchant_pattern, category_id FROM merchant_rules ORDER BY hit_count DESC"
    )
    for r in rules:
        if r["merchant_pattern"] in text:
            return r["category_id"]

    # Layer 2: built-in keyword lexicon
    for cat_name, keywords in KEYWORD_LEXICON.items():
        if any(kw in text for kw in keywords):
            row = db.query_one("SELECT id FROM categories WHERE name = ?", (cat_name,))
            if row:
                return row["id"]
    return None


def learn_from_correction(db: Database, merchant: str, category_id: int) -> None:
    """
    Call this whenever a user manually assigns/changes a transaction's category.
    Builds up merchant_rules so future transactions from the same merchant
    auto-categorize correctly -- this is how the app "learns" offline.
    """
    pattern = merchant.strip().lower()
    if not pattern:
        return
    existing = db.query_one(
        "SELECT id, hit_count FROM merchant_rules WHERE merchant_pattern = ?", (pattern,)
    )
    if existing:
        db.update("merchant_rules", existing["id"], {
            "category_id": category_id,
            "hit_count": existing["hit_count"] + 1,
        })
    else:
        db.insert("merchant_rules", {
            "merchant_pattern": pattern,
            "category_id": category_id,
            "hit_count": 1,
        })
