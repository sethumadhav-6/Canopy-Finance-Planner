import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from db.database import Database


@pytest.fixture
def db(tmp_path):
    """Fresh, seeded, on-disk-but-temporary sqlite DB for each test."""
    d = Database(str(tmp_path / "test.db"))
    d.seed_defaults_if_empty()
    yield d
    d.close()


@pytest.fixture
def category_id(db):
    row = db.query_one("SELECT id FROM categories WHERE name = 'Stationery'")
    return row["id"]
