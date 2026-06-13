import pytest
from app.integrations.nutrition import parse_off_product, NutritionResult

SAMPLE = {
    "code": "3017620422003", "product_name": "Nutella", "brands": "Ferrero",
    "nutriments": {
        "energy-kcal_100g": 539, "proteins_100g": 6.3, "carbohydrates_100g": 57.5,
        "sugars_100g": 56.3, "fat_100g": 30.9, "saturated-fat_100g": 10.6,
        "fiber_100g": 0, "sodium_100g": 0.0428,  # grams in OFF
    },
}


def test_parse_off_product_macros_and_sugar():
    r = parse_off_product(SAMPLE)
    assert isinstance(r, NutritionResult)
    assert r.calories == 539
    assert r.fat_unsaturated == pytest.approx(20.3)
    assert r.sugar_g == pytest.approx(56.3)
    assert r.sodium == pytest.approx(42.8)   # 0.0428 g -> 42.8 mg


def test_parse_off_product_micros_default_none_when_absent():
    r = parse_off_product({"product_name": "X", "nutriments": {}})
    assert r.iron_mg is None and r.calcium_mg is None and r.sugar_g is None


def test_parse_off_product_clamps_negative_unsaturated():
    r = parse_off_product({"product_name": "X", "nutriments": {"fat_100g": 1, "saturated-fat_100g": 5}})
    assert r.fat_unsaturated == 0
