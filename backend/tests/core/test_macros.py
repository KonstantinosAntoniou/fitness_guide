import pytest
from app.core.macros import Macros, scale_food, sum_macros


class FakeFood:
    def __init__(self, **kw):
        self.calories = kw.get("calories", 0)
        self.protein = kw.get("protein", 0)
        self.carbs = kw.get("carbs", 0)
        self.fat_saturated = kw.get("fat_saturated", 0)
        self.fat_unsaturated = kw.get("fat_unsaturated", 0)
        self.fiber = kw.get("fiber")
        self.sodium = kw.get("sodium", 0)


def test_scale_food():
    f = FakeFood(calories=100, protein=10, carbs=20, fat_saturated=1, fat_unsaturated=2, sodium=0.5)
    m = scale_food(f, 2.5)
    assert m.calories == 250
    assert m.protein == 25
    assert m.fat_total == pytest.approx(7.5)


def test_scale_food_handles_none_fiber():
    m = scale_food(FakeFood(calories=50, fiber=None), 2)
    assert m.fiber == 0


def test_sum_macros():
    total = sum_macros([
        Macros(calories=100, protein=10),
        Macros(calories=200, protein=5),
    ])
    assert total.calories == 300
    assert total.protein == 15
