import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food
from app.repositories import MealRepository
from app.agent.tools import build_tools


@pytest.fixture
def ctx():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = new_session_factory(engine)()
    s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
    s.add(Food(name="Oats", serving_description="100g", calories=375, protein=11, carbs=69))
    s.add(Food(name="Banana", serving_description="1", calories=105, protein=1, carbs=27))
    s.commit()
    tools = {t.name: t for t in build_tools(s, user_id=1)}
    yield s, tools
    s.close()


def test_save_meal_creates_meal_with_items(ctx):
    session, tools = ctx
    out = tools["save_meal"].invoke({"name": "Breakfast Bowl",
                                     "items": [{"food": "Oats", "servings": 1}, {"food": "Banana", "servings": 1}]})
    assert "saved" in out.lower()
    meal = MealRepository(session).find_by_name("Breakfast Bowl")
    assert meal is not None and len(meal.items) == 2


def test_list_my_plans_empty(ctx):
    _, tools = ctx
    assert "no" in tools["list_my_plans"].invoke({}).lower()
