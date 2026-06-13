import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import Food
from app.repositories import FoodRepository, MealRepository, UserRepository


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_food_upsert_is_idempotent(session):
    repo = FoodRepository(session)
    repo.add(Food(name="Apple", brand="Green", serving_description="1 medium", calories=97))
    session.commit()
    existing = repo.find_by_name_brand("apple", "green")
    assert existing is not None
    assert len(repo.list_all()) == 1


def test_user_create_and_get(session):
    repo = UserRepository(session)
    u = repo.create(name="Kostas", age=30, sex="male", height_cm=180,
                    weight_kg=80, activity_level="moderate")
    session.commit()
    assert repo.get(u.id).name == "Kostas"


def test_meal_get_by_name(session):
    repo = MealRepository(session)
    repo.create(name="Lunch")
    session.commit()
    assert repo.find_by_name("lunch").name == "Lunch"
