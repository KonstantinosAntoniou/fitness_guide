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


def test_create_and_list_user(client):
    r = client.post("/users", json={
        "name": "Kostas", "age": 30, "sex": "male", "height_cm": 180,
        "weight_kg": 80, "activity_level": "moderate",
        "goal_type": "lose", "goal_period": "week", "amount_kg": 0.5,
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Kostas"
    assert round(body["metrics"]["target_calories"]) == 2209

    r2 = client.get("/users")
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_duplicate_name_rejected(client):
    payload = {"name": "Kostas", "age": 30, "sex": "male", "height_cm": 180,
               "weight_kg": 80, "activity_level": "moderate"}
    assert client.post("/users", json=payload).status_code == 201
    assert client.post("/users", json=payload).status_code == 409


def test_user_output_includes_targets(client):
    r = client.post("/users", json={
        "name": "T", "age": 30, "sex": "male", "height_cm": 181, "weight_kg": 85,
        "activity_level": "moderate", "goal_type": "lose", "goal_period": "week", "amount_kg": 0.5,
    })
    assert r.status_code == 201
    targets = r.json()["targets"]
    assert round(targets["protein_g"]) == 170
    assert round(targets["calories"]) == 2296
