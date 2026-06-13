from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_profile_metrics():
    r = client.post("/profile/metrics", json={
        "sex": "male", "weight_kg": 80, "height_cm": 180, "age": 30,
        "activity_level": "moderate",
        "goal_type": "lose", "goal_period": "week", "amount_kg": 0.5,
    })
    assert r.status_code == 200
    body = r.json()
    assert round(body["target_calories"]) == 2209
    assert body["bmi_category"] == "normal"


def test_profile_metrics_validation_error():
    r = client.post("/profile/metrics", json={"sex": "male"})
    assert r.status_code == 422
