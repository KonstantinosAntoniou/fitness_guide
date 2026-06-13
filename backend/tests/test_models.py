import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food, Meal, MealItem


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_food_fat_total_is_computed(session):
    f = Food(name="Oats", brand="Brown", serving_description="100g",
             calories=375, protein=11, carbs=69, fat_saturated=1, fat_unsaturated=8, sodium=0)
    session.add(f)
    session.commit()
    assert f.fat_total == 9


def test_meal_with_items(session):
    chicken = Food(name="Chicken", brand="Breast", serving_description="100g", calories=165, protein=31)
    session.add(chicken)
    session.flush()
    meal = Meal(name="Lunch", items=[MealItem(food_id=chicken.id, servings=2.0)])
    session.add(meal)
    session.commit()
    assert meal.items[0].food.name == "Chicken"
    assert meal.items[0].servings == 2.0


def test_user_optional_goal(session):
    u = User(name="Kostas", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate")
    session.add(u)
    session.commit()
    assert u.goal_type is None
