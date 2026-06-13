import datetime
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import Food
from app.repositories import PlanRepository, LogRepository


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def _food(session, **kw):
    f = Food(name=kw.get("name", "X"), serving_description="100g",
             **{k: v for k, v in kw.items() if k != "name"})
    session.add(f)
    session.flush()
    return f


def test_save_and_get_plan(session):
    f = _food(session, name="Rice", calories=130)
    repo = PlanRepository(session)
    draft = [{"name": "Lunch", "items": [(f, 2.0)]}]
    plan = repo.save_draft(user_id=1, name="Day 1", draft=draft)
    session.commit()
    loaded = repo.get(plan.id)
    assert loaded.name == "Day 1"
    assert loaded.entries[0].items[0].servings == 2.0


def test_log_and_day_entries(session):
    f = _food(session, name="Egg", calories=78)
    repo = LogRepository(session)
    repo.add(user_id=1, food_id=f.id, servings=3.0)
    session.commit()
    today = datetime.date.today()
    entries = repo.for_day(user_id=1, day=today)
    assert len(entries) == 1
    assert entries[0].servings == 3.0
