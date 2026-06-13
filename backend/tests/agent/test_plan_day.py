import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food
from app.repositories import PlanRepository
from app.agent.tools import build_tools


@pytest.fixture
def ctx():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = new_session_factory(engine)()
    s.add(User(name="K", age=30, sex="male", height_cm=181, weight_kg=85,
               activity_level="moderate", goal_type="lose", goal_period="week", amount_kg=0.5))
    s.add(Food(name="Chicken Breast", serving_description="100g", calories=165, protein=31,
               carbs=0, fat_unsaturated=3, iron_mg=0.7, potassium_mg=256))
    s.add(Food(name="White Rice", serving_description="100g", calories=130, protein=2.7,
               carbs=28, fat_unsaturated=0.3))
    s.add(Food(name="Olive Oil", serving_description="100g", calories=884, protein=0,
               carbs=0, fat_unsaturated=100))
    s.add(Food(name="Broccoli", serving_description="100g", calories=34, protein=2.8,
               carbs=7, vitamin_c_mg=89, potassium_mg=316))
    s.commit()
    tools = {t.name: t for t in build_tools(s, user_id=1)}
    yield s, tools
    s.close()


def test_plan_day_persists_and_scores(ctx):
    session, tools = ctx
    out = tools["plan_day"].invoke({"meals": [
        {"name": "Lunch", "foods": ["Chicken Breast", "White Rice", "Olive Oil"]},
        {"name": "Dinner", "foods": ["Chicken Breast", "Broccoli", "White Rice"]},
    ]})
    assert "kcal" in out.lower()
    assert "protein" in out.lower()
    plans = PlanRepository(session).list_for_user(1)
    assert len(plans) == 1


def test_plan_day_unknown_foods(ctx):
    _, tools = ctx
    out = tools["plan_day"].invoke({"meals": [{"name": "X", "foods": ["nonexistent food"]}]})
    assert "no" in out.lower() or "couldn" in out.lower()
