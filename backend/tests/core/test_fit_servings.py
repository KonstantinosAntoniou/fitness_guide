import pytest
from app.core.planner import ItemSpec, fit_servings, food_spec, meal_ingredient_specs


class F:
    def __init__(self, **k):
        self.id = k.get("id", 0)
        self.name = k.get("name", "x")
        self.protein = k.get("protein", 0.0)
        self.carbs = k.get("carbs", 0.0)
        self.fat_saturated = k.get("fat_saturated", 0.0)
        self.fat_unsaturated = k.get("fat_unsaturated", 0.0)
        self.calories = k.get("calories", 0.0)


def test_fit_hits_macros_within_bounds():
    chicken = F(name="chicken", protein=31, carbs=0, fat_unsaturated=3, calories=165)
    rice = F(name="rice", protein=2.7, carbs=28, fat_unsaturated=0.3, calories=130)
    oil = F(name="oil", protein=0, carbs=0, fat_unsaturated=14, calories=120)
    specs = [food_spec(chicken, max_servings=8), food_spec(rice, max_servings=8), food_spec(oil, max_servings=5)]
    servings = fit_servings(specs, protein_g=120, carb_g=140, fat_g=50)
    assert all(0 <= s <= spec.hi + 1e-6 for s, spec in zip(servings, specs))
    protein = sum(f.protein * s for f, s in zip([chicken, rice, oil], servings))
    assert protein == pytest.approx(120, abs=12)


def test_meal_ingredient_specs_flex():
    egg = F(name="egg")
    toast = F(name="toast")

    class Item:
        def __init__(self, food, servings):
            self.food, self.servings = food, servings

    class Meal:
        items = [Item(egg, 2.0), Item(toast, 1.0)]

    specs = meal_ingredient_specs(Meal(), flex=0.3)
    assert specs[0].lo == pytest.approx(1.4) and specs[0].hi == pytest.approx(2.6)


def test_fit_empty_returns_empty():
    assert fit_servings([], 100, 100, 30) == []
