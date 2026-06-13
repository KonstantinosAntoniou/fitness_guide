import pytest
from app.integrations.nutrition import parse_off_product, NutritionResult

SAMPLE = {
    "code": "3017620422003",
    "product_name": "Nutella",
    "brands": "Ferrero",
    "nutriments": {
        "energy-kcal_100g": 539,
        "proteins_100g": 6.3,
        "carbohydrates_100g": 57.5,
        "fat_100g": 30.9,
        "saturated-fat_100g": 10.6,
        "fiber_100g": 0,
        "sodium_100g": 0.0428,
    },
}


def test_parse_off_product():
    r = parse_off_product(SAMPLE)
    assert isinstance(r, NutritionResult)
    assert r.name == "Nutella"
    assert r.brand == "Ferrero"
    assert r.source == "openfoodfacts"
    assert r.source_id == "3017620422003"
    assert r.serving_description == "100g"
    assert r.serving_grams == 100
    assert r.calories == 539
    assert r.fat_saturated == 10.6
    # unsaturated = total - saturated, clamped at >= 0
    assert r.fat_unsaturated == pytest.approx(20.3)
    assert r.sodium == pytest.approx(0.0428)


def test_parse_off_product_missing_fields_default_zero():
    r = parse_off_product({"product_name": "Mystery", "nutriments": {}})
    assert r.name == "Mystery"
    assert r.calories == 0
    assert r.fat_unsaturated == 0


def test_parse_off_product_clamps_negative_unsaturated():
    # saturated > total (dirty data) must not produce negative unsaturated
    r = parse_off_product({"product_name": "X", "nutriments": {"fat_100g": 1, "saturated-fat_100g": 5}})
    assert r.fat_unsaturated == 0
