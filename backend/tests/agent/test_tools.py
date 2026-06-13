import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food
from app.repositories import PlanRepository, LogRepository
from app.agent.tools import build_tools
from app.integrations.nutrition import NutritionResult


class FakeProvider:
    def search(self, query, limit=5):
        return [NutritionResult(name="Tofu", calories=144, protein=15, carbs=3,
                                fat_saturated=1, fat_unsaturated=8, sodium=0.01)]


@pytest.fixture
def ctx():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = new_session_factory(engine)()
    s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
    s.add(Food(name="Rice", serving_description="100g", calories=130, protein=2.7))
    s.add(Food(name="Chicken", serving_description="100g", calories=165, protein=31))
    s.commit()
    tools = {t.name: t for t in build_tools(s, user_id=1, nutrition_provider=FakeProvider())}
    yield s, tools
    s.close()


def test_get_profile_tool(ctx):
    _, tools = ctx
    out = tools["get_profile"].invoke({})
    assert "kcal" in out and "K" in out


def test_search_nutrition_tool(ctx):
    _, tools = ctx
    assert "Tofu" in tools["search_nutrition_database"].invoke({"query": "tofu"})


def test_plan_day_tool_persists(ctx):
    session, tools = ctx
    out = tools["plan_day"].invoke({"meals": [{"name": "Lunch", "foods": ["Rice", "Chicken"]}]})
    assert "plan" in out.lower()
    assert len(PlanRepository(session).list_for_user(1)) == 1


def test_log_food_tool_persists(ctx):
    import datetime
    session, tools = ctx
    out = tools["log_food"].invoke({"name": "rice", "servings": 2})
    assert "Logged" in out
    assert len(LogRepository(session).for_day(1, datetime.date.today())) == 1
