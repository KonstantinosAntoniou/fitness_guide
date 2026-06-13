import pytest
from app.migration.parsers import food_from_row, parse_meal_food_name


def test_food_from_row():
    row = {"Name": "Oats", "Label": "Brown", "Measurement": "100g",
           "Calories": 375, "Protein": 11, "Carbs": 69,
           "Fat_Saturated": 1, "Fat_Regular": 8, "Sodium": 0}
    f = food_from_row(row)
    assert f.name == "Oats"
    assert f.brand == "Brown"
    assert f.serving_description == "100g"
    assert f.fat_saturated == 1
    assert f.fat_unsaturated == 8
    assert f.calories == 375


@pytest.mark.parametrize("raw,mult,name", [
    ("2.1x Chichen", 2.1, "Chichen"),
    ("2.0x Pita Kalampokiou", 2.0, "Pita Kalampokiou"),
    ("1x Egg", 1.0, "Egg"),
])
def test_parse_meal_food_name(raw, mult, name):
    assert parse_meal_food_name(raw) == (mult, name)


def test_parse_meal_food_name_rejects_total():
    with pytest.raises(ValueError):
        parse_meal_food_name("Total")
