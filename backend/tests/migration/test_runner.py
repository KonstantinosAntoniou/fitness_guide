from pathlib import Path
import pytest
from app.db import Base, new_engine, new_session_factory
from app.migration.runner import migrate

REPO_ROOT = Path(__file__).resolve().parents[3]
FOODS_XLSX = REPO_ROOT / "foods_log.xlsx"
MEALS_XLSX = REPO_ROOT / "meals_log.xlsx"


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


@pytest.mark.skipif(not FOODS_XLSX.exists(), reason="legacy Excel not present")
def test_migrate_loads_foods_and_is_idempotent(session):
    report = migrate(session, str(FOODS_XLSX), str(MEALS_XLSX))
    session.commit()
    assert report["foods_added"] >= 60
    from app.repositories import FoodRepository
    count = len(FoodRepository(session).list_all())
    # running again adds no duplicate foods
    migrate(session, str(FOODS_XLSX), str(MEALS_XLSX))
    session.commit()
    assert len(FoodRepository(session).list_all()) == count
