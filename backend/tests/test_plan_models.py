import datetime
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food, Plan, PlanEntry, PlanItem, LogEntry


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_plan_tree(session):
    food = Food(name="Rice", serving_description="100g", calories=130)
    session.add(food)
    session.flush()
    plan = Plan(name="Day 1", entries=[
        PlanEntry(name="Lunch", position=0, items=[PlanItem(food_id=food.id, servings=2.0)])
    ])
    session.add(plan)
    session.commit()
    assert plan.entries[0].items[0].food.name == "Rice"
    assert plan.entries[0].items[0].servings == 2.0


def test_log_entry_defaults_today(session):
    food = Food(name="Egg", serving_description="1", calories=78)
    session.add(food)
    session.flush()
    log = LogEntry(user_id=1, food_id=food.id, servings=2.0)
    session.add(log)
    session.commit()
    assert log.eaten_on == datetime.date.today()
    assert log.source == "manual"
