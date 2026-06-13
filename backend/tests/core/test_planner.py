import pytest
from app.core.planner import portion_to_calories, build_day_plan


class FakeFood:
    def __init__(self, id, calories):
        self.id = id
        self.calories = calories
        self.protein = self.carbs = self.fat_saturated = self.fat_unsaturated = self.sodium = 0
        self.fiber = 0


def test_portion_to_calories_even_split():
    foods = [FakeFood(1, 100), FakeFood(2, 200)]
    servings = portion_to_calories(foods, 1000)
    # even calorie split: 500 each -> 5.0 and 2.5 servings
    assert servings == pytest.approx([5.0, 2.5])
    total = sum(f.calories * s for f, s in zip(foods, servings))
    assert total == pytest.approx(1000)


def test_portion_rejects_zero_calorie_food():
    with pytest.raises(ValueError):
        portion_to_calories([FakeFood(1, 0)], 500)


def test_build_day_plan_hits_target_and_meal_count():
    candidates = [FakeFood(1, 100), FakeFood(2, 200), FakeFood(3, 50)]
    plan = build_day_plan(target_calories=2000, candidates=candidates, meals=2, foods_per_meal=2)
    assert len(plan) == 2
    total = sum(f.calories * s for entry in plan for f, s in entry["items"])
    assert total == pytest.approx(2000)
    assert plan[0]["name"] == "Meal 1"


def test_build_day_plan_requires_candidates():
    with pytest.raises(ValueError):
        build_day_plan(2000, candidates=[FakeFood(1, 0)], meals=1)
