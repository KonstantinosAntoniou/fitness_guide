"""Day-plan math. The LLM picks foods; the core sizes the servings."""
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy.optimize import lsq_linear

from app.core.macros import scale_food, sum_macros


class FoodLike(Protocol):
    calories: float


# --- legacy calorie-only builder (still used by the /plans/generate endpoint) ---


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


# --- macro-aware planner (Plan B): LLM selects foods, this fits the servings ---


@dataclass
class ItemSpec:
    food: object       # FoodLike: .protein/.carbs/.fat_saturated/.fat_unsaturated/.calories/.name/.id
    lo: float          # min servings
    hi: float          # max servings


def food_spec(food, max_servings: float = 4.0) -> ItemSpec:
    return ItemSpec(food=food, lo=0.0, hi=max_servings)


def meal_ingredient_specs(meal, flex: float = 0.3) -> list[ItemSpec]:
    """A saved meal's ingredients, each anchored to its recipe servings ±flex."""
    out = []
    for it in meal.items:
        r = it.servings
        out.append(ItemSpec(food=it.food, lo=r * (1 - flex), hi=r * (1 + flex)))
    return out


def fit_servings(specs: list[ItemSpec], protein_g: float, carb_g: float, fat_g: float,
                 protein_weight: float = 1.5) -> list[float]:
    """Servings per item that best hit the macro targets within each item's bounds."""
    if not specs:
        return []
    P = np.array([s.food.protein or 0 for s in specs], dtype=float)
    C = np.array([s.food.carbs or 0 for s in specs], dtype=float)
    Ft = np.array([(s.food.fat_saturated or 0) + (s.food.fat_unsaturated or 0) for s in specs], dtype=float)
    A = np.vstack([protein_weight * P, C, Ft])
    b = np.array([protein_weight * protein_g, carb_g, fat_g], dtype=float)
    lb = np.array([s.lo for s in specs], dtype=float)
    ub = np.array([max(s.hi, s.lo) for s in specs], dtype=float)
    res = lsq_linear(A, b, bounds=(lb, ub))
    return [float(x) for x in res.x]


_MICROS = ("iron_mg", "calcium_mg", "potassium_mg", "vitamin_c_mg", "vitamin_d_ug")


@dataclass
class PlanScore:
    calories: float
    protein_g: float
    carb_g: float
    fat_g: float
    fiber_g: float
    sodium_mg: float
    micros: dict          # name -> (got, target)
    _targets: object

    def macro_pct(self) -> dict:
        t = self._targets

        def pct(got, target):
            return round(100 * got / target, 0) if target else 0.0

        return {
            "protein": pct(self.protein_g, t.protein_g),
            "carbs": pct(self.carb_g, t.carb_g),
            "fat": pct(self.fat_g, t.fat_g),
            "calories": pct(self.calories, t.calories),
        }


def score_plan(specs: list[ItemSpec], servings: list[float], targets) -> PlanScore:
    macros = sum_macros([scale_food(s.food, q) for s, q in zip(specs, servings)])
    micros = {}
    for m in _MICROS:
        got = sum((getattr(s.food, m, None) or 0) * q for s, q in zip(specs, servings))
        micros[m] = (round(got, 1), getattr(targets, m))
    return PlanScore(
        calories=round(macros.calories, 0), protein_g=round(macros.protein, 1),
        carb_g=round(macros.carbs, 1), fat_g=round(macros.fat_total, 1),
        fiber_g=round(macros.fiber, 1), sodium_mg=round(macros.sodium, 1),
        micros=micros, _targets=targets,
    )
