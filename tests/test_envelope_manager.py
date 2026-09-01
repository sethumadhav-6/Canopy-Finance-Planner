from core.envelope_manager import (all_envelope_statuses, create_envelope,
                                    get_envelope_status, record_expense)


def test_create_and_status(db, category_id):
    env_id = create_envelope(db, "Groceries", "discretionary", category_id, 500)
    status = get_envelope_status(db, env_id, "2026-09")
    assert status.allocated_minor == 50000
    assert status.spent_minor == 0
    assert status.remaining_minor == 50000
    assert status.pct_used == 0


def test_spend_updates_status(db, category_id):
    env_id = create_envelope(db, "Groceries", "discretionary", category_id, 500)
    record_expense(db, env_id, category_id, "2026-09-05", 120, merchant="DMart")
    status = get_envelope_status(db, env_id, "2026-09")
    assert status.spent_minor == 12000
    assert status.remaining_minor == 38000
    assert 20 < status.pct_used < 30


def test_over_budget_flag(db, category_id):
    env_id = create_envelope(db, "Groceries", "discretionary", category_id, 100)
    record_expense(db, env_id, category_id, "2026-09-05", 150, merchant="DMart")
    status = get_envelope_status(db, env_id, "2026-09")
    assert status.is_over is True
    assert status.remaining_minor == -5000


def test_rollover_carries_unspent_balance(db, category_id):
    env_id = create_envelope(db, "Groceries", "discretionary", category_id, 500,
                              rollover_enabled=True)
    record_expense(db, env_id, category_id, "2026-08-05", 200, merchant="DMart")
    aug_status = get_envelope_status(db, env_id, "2026-08")
    assert aug_status.remaining_minor == 30000  # 500 - 200 = 300 rupees unspent

    sep_status = get_envelope_status(db, env_id, "2026-09")
    assert sep_status.rollover_in_minor == 30000
    assert sep_status.allocated_minor + sep_status.rollover_in_minor == 80000


def test_rollover_never_carries_negative(db, category_id):
    env_id = create_envelope(db, "Groceries", "discretionary", category_id, 100,
                              rollover_enabled=True)
    record_expense(db, env_id, category_id, "2026-08-05", 300, merchant="DMart")  # overspent
    sep_status = get_envelope_status(db, env_id, "2026-09")
    assert sep_status.rollover_in_minor == 0


def test_all_envelope_statuses_lists_active_only(db, category_id):
    create_envelope(db, "Groceries", "discretionary", category_id, 500)
    inactive_id = create_envelope(db, "Old", "discretionary", category_id, 100)
    db.update("envelopes", inactive_id, {"is_active": 0})
    statuses = all_envelope_statuses(db, "2026-09")
    names = {s.envelope.name for s in statuses}
    assert "Groceries" in names
    assert "Old" not in names
