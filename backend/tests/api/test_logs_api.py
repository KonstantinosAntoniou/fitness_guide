import pytest
from fastapi.testclient import TestClient
from app.db import Base, new_engine, new_session_factory, get_session
from app.main import app
from app.models import User, Food


@pytest.fixture
def client():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestingSession = new_session_factory(engine)
    with TestingSession() as s:
        s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
        s.add(Food(name="Egg", serving_description="1", calories=78, protein=6))
        s.commit()

    def override():
        with TestingSession() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_log_food_and_day_summary(client):
    r = client.post("/users/1/log", json={"food_id": 1, "servings": 2})
    assert r.status_code == 201

    s = client.get("/users/1/log/today")
    assert s.status_code == 200
    body = s.json()
    assert body["totals"]["calories"] == pytest.approx(156)  # 78 * 2
    assert len(body["entries"]) == 1
