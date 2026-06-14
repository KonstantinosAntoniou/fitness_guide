import pytest
import httpx
from app.integrations.usda import USDAProvider, parse_usda_food

# Trimmed real-shape FDC search hit for chicken breast (per 100 g)
FDC = {"foods": [{
    "fdcId": 171077, "description": "Chicken, broiler, breast, raw", "dataType": "SR Legacy",
    "foodNutrients": [
        {"nutrientNumber": "208", "value": 165}, {"nutrientNumber": "203", "value": 31},
        {"nutrientNumber": "205", "value": 0}, {"nutrientNumber": "204", "value": 3.6},
        {"nutrientNumber": "606", "value": 1.0}, {"nutrientNumber": "307", "value": 74},
        {"nutrientNumber": "303", "value": 0.7}, {"nutrientNumber": "306", "value": 256},
        {"nutrientNumber": "401", "value": 0}, {"nutrientNumber": "328", "value": 0.1},
    ],
}]}


def test_parse_usda_food():
    r = parse_usda_food(FDC["foods"][0])
    assert r.name.lower().startswith("chicken")
    assert r.source == "usda" and r.source_id == "171077"
    assert r.calories == 165 and r.protein == 31
    assert r.fat_saturated == 1.0 and r.fat_unsaturated == pytest.approx(2.6)
    assert r.sodium == 74 and r.iron_mg == 0.7 and r.potassium_mg == 256


def test_energy_fallback_for_foundation_foods():
    # Foundation foods store kcal under 2048, not 208 — must still resolve calories
    food = {"fdcId": 1, "description": "Lentils, Dry", "foodNutrients": [
        {"nutrientNumber": "203", "value": 25}, {"nutrientNumber": "205", "value": 60},
        {"nutrientNumber": "2048", "value": 352},
    ]}
    assert parse_usda_food(food).calories == 352


def test_search_hits_api_and_parses():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=FDC)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=USDAProvider.BASE)
    results = USDAProvider(api_key="k", client=client).search("chicken breast", limit=3)
    assert results[0].calories == 165
    assert "api_key=k" in captured["url"] and "chicken" in captured["url"]
