import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.nutrition import get_nutrition_provider
from app.integrations.nutrition import NutritionResult


class FakeProvider:
    def search(self, query: str, limit: int = 5):
        return [NutritionResult(name=f"{query}-result", calories=100, protein=5,
                                carbs=10, fat_saturated=1, fat_unsaturated=2, sodium=0.01)]


@pytest.fixture
def client():
    app.dependency_overrides[get_nutrition_provider] = lambda: FakeProvider()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_nutrition_search(client):
    r = client.get("/nutrition/search", params={"q": "apple"})
    assert r.status_code == 200
    body = r.json()
    assert body[0]["name"] == "apple-result"
    assert body[0]["calories"] == 100
