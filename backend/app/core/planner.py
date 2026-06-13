"""Deterministic day-plan math. The LLM picks foods; this portions them."""
from typing import Protocol


class FoodLike(Protocol):
    calories: float


def portion_to_calories(foods: list, target_calories: float) -> list[float]:
    """Servings per food so the group hits target_calories with an even calorie split."""
    if not foods:
        raise ValueError("no foods to portion")
    share = target_calories / len(foods)
    servings = []
    for f in foods:
        if not f.calories or f.calories <= 0:
            raise ValueError(f"food {getattr(f, 'id', '?')} has non-positive calories")
        servings.append(share / f.calories)
    return servings


def build_day_plan(target_calories: float, candidates: list, meals: int = 3,
                   foods_per_meal: int = 2) -> list[dict]:
    """Split target across `meals`; fill each meal by rotating through candidates.

    Returns a list of {"name": str, "items": [(food, servings), ...]}.
    """
    usable = [f for f in candidates if getattr(f, "calories", 0) and f.calories > 0]
    if not usable:
        raise ValueError("no usable candidate foods (need positive calories)")

    per_meal = target_calories / meals
    plan: list[dict] = []
    cursor = 0
    for i in range(meals):
        chosen = []
        for _ in range(foods_per_meal):
            chosen.append(usable[cursor % len(usable)])
            cursor += 1
        servings = portion_to_calories(chosen, per_meal)
        plan.append({
            "name": f"Meal {i + 1}",
            "items": list(zip(chosen, servings)),
        })
    return plan
