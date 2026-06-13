import pytest
from fastapi.testclient import TestClient
from app.db import Base, new_engine, new_session_factory, get_session
from app.main import app


@pytest.fixture
def client():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestingSession = new_session_factory(engine)

    def override():
        with TestingSession() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_food_and_list(client):
    payload = {"name": "Banana", "brand": "", "serving_description": "1 medium",
               "calories": 105, "protein": 1.3, "carbs": 27,
               "fat_saturated": 0.1, "fat_unsaturated": 0.2, "sodium": 0.001}
    r = client.post("/foods", json=payload)
    assert r.status_code == 201
    assert r.json()["name"] == "Banana"
    listed = client.get("/foods").json()
    assert any(f["name"] == "Banana" for f in listed)


def test_create_food_duplicate_rejected(client):
    payload = {"name": "Banana", "brand": "Dole", "calories": 105}
    assert client.post("/foods", json=payload).status_code == 201
    assert client.post("/foods", json=payload).status_code == 409
