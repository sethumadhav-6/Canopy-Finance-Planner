-- Canopy Finance Planner -- offline SQLite schema
-- All amounts stored as INTEGER paise/cents (amount_minor) to avoid float rounding errors.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    group_name      TEXT NOT NULL DEFAULT 'other',   -- stationery, household, food, transport, utilities, entertainment, health, recurring, other
    icon            TEXT DEFAULT 'shape-outline',      -- KivyMD icon name
    color_hex       TEXT DEFAULT '#7C83FD',
    is_recurring    INTEGER NOT NULL DEFAULT 0,        -- 1 = typically a recurring/subscription category
    is_system       INTEGER NOT NULL DEFAULT 0,        -- 1 = seeded default, protected from deletion
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS envelopes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    category_id         INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    envelope_type       TEXT NOT NULL DEFAULT 'discretionary', -- discretionary, recurring_vault, savings_goal
    monthly_allocation_minor INTEGER NOT NULL DEFAULT 0,
    rollover_enabled    INTEGER NOT NULL DEFAULT 1,
    expected_due_day    INTEGER,                       -- for recurring_vault: day of month bill is expected (1-28)
    notes               TEXT,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One balance row per envelope per month, so history/rollover is auditable.
CREATE TABLE IF NOT EXISTS envelope_balances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    envelope_id     INTEGER NOT NULL REFERENCES envelopes(id) ON DELETE CASCADE,
    month           TEXT NOT NULL,                      -- 'YYYY-MM'
    allocated_minor INTEGER NOT NULL DEFAULT 0,          -- allocation for this month (incl. rollover in)
    spent_minor     INTEGER NOT NULL DEFAULT 0,          -- computed from transactions, cached
    rollover_in_minor INTEGER NOT NULL DEFAULT 0,
    UNIQUE(envelope_id, month)
);

CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_date        TEXT NOT NULL,                      -- 'YYYY-MM-DD'
    amount_minor    INTEGER NOT NULL,                    -- always positive; direction via txn_type
    txn_type        TEXT NOT NULL DEFAULT 'expense',      -- expense, income, transfer
    category_id     INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    envelope_id     INTEGER REFERENCES envelopes(id) ON DELETE SET NULL,
    merchant        TEXT,
    description     TEXT,
    payment_method  TEXT DEFAULT 'other',                 -- cash, card, upi, netbanking, other
    source          TEXT NOT NULL DEFAULT 'manual',        -- manual, csv, sms
    raw_text        TEXT,                                 -- original SMS/CSV line, for audit + re-parsing
    duplicate_of    INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
    duplicate_score REAL,                                  -- 0..1 similarity confidence when flagged
    is_reviewed     INTEGER NOT NULL DEFAULT 0,            -- user has confirmed/dismissed duplicate flag
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_txn_envelope ON transactions(envelope_id);
CREATE INDEX IF NOT EXISTS idx_txn_merchant ON transactions(merchant);

CREATE TABLE IF NOT EXISTS budgets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    month           TEXT NOT NULL,                       -- 'YYYY-MM' the budget applies to
    category_id     INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    planned_minor   INTEGER NOT NULL DEFAULT 0,
    basis           TEXT NOT NULL DEFAULT 'auto',          -- auto (engine-suggested) or manual (user override)
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(month, category_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

-- Merchant -> category learning table, built up as the user categorizes transactions.
CREATE TABLE IF NOT EXISTS merchant_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_pattern TEXT NOT NULL UNIQUE,                 -- lowercase substring match
    category_id     INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    hit_count       INTEGER NOT NULL DEFAULT 0
);

-- Phase 2: SMS-derived transactions land here first and never touch the real
-- transactions table until a user explicitly approves them (see core/sms_import.py).
CREATE TABLE IF NOT EXISTS sms_staging (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at         TEXT NOT NULL,                        -- 'YYYY-MM-DD', when the SMS arrived
    sender              TEXT,                                  -- SMS sender ID, e.g. 'HDFCBK'
    raw_text            TEXT NOT NULL,
    parsed_amount_minor INTEGER,
    parsed_txn_type     TEXT,                                   -- expense, income
    parsed_txn_date     TEXT,
    parsed_merchant     TEXT,
    parsed_account_hint TEXT,
    confidence          REAL,
    status              TEXT NOT NULL DEFAULT 'pending',          -- pending, approved, rejected
    resulting_txn_id    INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sms_staging_status ON sms_staging(status);
