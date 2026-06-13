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
        s.add(Food(name="Rice", serving_description="100g", calories=130, protein=2.7))
        s.add(Food(name="Chicken", serving_description="100g", calories=165, protein=31))
        s.commit()

    def override():
        with TestingSession() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_generate_plan_hits_target(client):
    r = client.post("/users/1/plans/generate", json={"target_calories": 2000, "meals": 2, "foods_per_meal": 2})
    assert r.status_code == 201
    body = r.json()
    assert body["name"]
    assert body["totals"]["calories"] == pytest.approx(2000, abs=1)
    assert len(body["entries"]) == 2

    plan_id = body["id"]
    r2 = client.get(f"/plans/{plan_id}")
    assert r2.status_code == 200
    assert r2.json()["totals"]["calories"] == pytest.approx(2000, abs=1)
