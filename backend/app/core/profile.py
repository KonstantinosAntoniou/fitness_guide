"""Compose energy/body math into a single profile metrics result."""
from typing import Optional

from app.core.energy import mifflin_st_jeor, harris_benedict, tdee
from app.core.goals import target_calories
from app.core.body import bmi, bmi_category


def compute_metrics(
    *, sex: str, weight_kg: float, height_cm: float, age: int,
    activity_level: str,
    goal_type: Optional[str] = None,
    goal_period: Optional[str] = None,
    amount_kg: Optional[float] = None,
) -> dict:
    bmr_msj = mifflin_st_jeor(sex, weight_kg, height_cm, age)
    bmr_hb = harris_benedict(sex, weight_kg, height_cm, age)
    tdee_msj = tdee(bmr_msj, activity_level)
    tdee_hb = tdee(bmr_hb, activity_level)
    body_bmi = bmi(weight_kg, height_cm)
    return {
        "bmr_msj": bmr_msj,
        "bmr_hb": bmr_hb,
        "tdee_msj": tdee_msj,
        "tdee_hb": tdee_hb,
        "bmi": body_bmi,
        "bmi_category": bmi_category(body_bmi),
        "target_calories": target_calories(tdee_msj, goal_type, goal_period, amount_kg),
    }
