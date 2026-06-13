"""Pure energy-expenditure math. No I/O, no frameworks."""
from typing import Literal

Sex = Literal["male", "female"]


def _check_sex(sex: str) -> None:
    if sex not in ("male", "female"):
        raise ValueError(f"sex must be 'male' or 'female', got {sex!r}")


def mifflin_st_jeor(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    _check_sex(sex)
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + (5 if sex == "male" else -161)


def harris_benedict(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    _check_sex(sex)
    if sex == "male":
        return 88.362 + 13.397 * weight_kg + 4.799 * height_cm - 5.677 * age
    return 447.593 + 9.247 * weight_kg + 3.098 * height_cm - 4.330 * age


ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


def tdee(bmr: float, activity_level: str) -> float:
    if activity_level not in ACTIVITY_MULTIPLIERS:
        raise ValueError(f"unknown activity_level: {activity_level!r}")
    return bmr * ACTIVITY_MULTIPLIERS[activity_level]
