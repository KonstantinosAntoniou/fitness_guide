"""Translate a weight goal into a daily calorie target."""
from typing import Literal, Optional

KCAL_PER_KG = 7700
PERIOD_DAYS = {"week": 7, "month": 30, "year": 365}

GoalType = Literal["lose", "gain"]
GoalPeriod = Literal["week", "month", "year"]


def target_calories(
    tdee: float,
    goal_type: Optional[GoalType],
    goal_period: Optional[GoalPeriod],
    amount_kg: Optional[float],
) -> float:
    if not goal_type or amount_kg is None:
        return tdee
    if goal_period not in PERIOD_DAYS:
        raise ValueError(f"unknown goal_period: {goal_period!r}")
    delta_per_day = amount_kg * KCAL_PER_KG / PERIOD_DAYS[goal_period]
    if goal_type == "lose":
        return tdee - delta_per_day
    if goal_type == "gain":
        return tdee + delta_per_day
    raise ValueError(f"unknown goal_type: {goal_type!r}")
