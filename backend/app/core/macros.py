"""Pure macro arithmetic. No DB, no frameworks."""
from dataclasses import dataclass, fields
from typing import Iterable, Optional, Protocol


@dataclass
class Macros:
    calories: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat_saturated: float = 0.0
    fat_unsaturated: float = 0.0
    fiber: float = 0.0
    sodium: float = 0.0

    @property
    def fat_total(self) -> float:
        return self.fat_saturated + self.fat_unsaturated

    def __add__(self, other: "Macros") -> "Macros":
        return Macros(**{f.name: getattr(self, f.name) + getattr(other, f.name)
                         for f in fields(self)})


class FoodLike(Protocol):
    calories: float
    protein: float
    carbs: float
    fat_saturated: float
    fat_unsaturated: float
    fiber: Optional[float]
    sodium: float


def scale_food(food: FoodLike, servings: float) -> Macros:
    return Macros(
        calories=(food.calories or 0) * servings,
        protein=(food.protein or 0) * servings,
        carbs=(food.carbs or 0) * servings,
        fat_saturated=(food.fat_saturated or 0) * servings,
        fat_unsaturated=(food.fat_unsaturated or 0) * servings,
        fiber=(food.fiber or 0) * servings,
        sodium=(food.sodium or 0) * servings,
    )


def sum_macros(items: Iterable[Macros]) -> Macros:
    total = Macros()
    for m in items:
        total = total + m
    return total
