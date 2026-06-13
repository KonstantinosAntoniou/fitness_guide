"""Turn a profile into concrete daily macro + soft micro targets. Pure."""
from dataclasses import dataclass
from typing import Optional
from app.core.energy import mifflin_st_jeor, tdee
from app.core.goals import target_calories

PROTEIN_G_PER_KG = {"lose": 2.0, "maintain": 1.6, "gain": 1.8}
_RDA = {
    "male": dict(iron_mg=8, calcium_mg=1000, potassium_mg=3400, vitamin_c_mg=90, vitamin_d_ug=15),
    "female": dict(iron_mg=18, calcium_mg=1000, potassium_mg=2600, vitamin_c_mg=75, vitamin_d_ug=15),
}


@dataclass
class NutritionTargets:
    calories: float
    protein_g: float
    carb_g: float
    fat_g: float
    fiber_g: float
    sodium_mg_max: float
    sat_fat_g_max: float
    sugar_g_max: float
    iron_mg: float
    calcium_mg: float
    potassium_mg: float
    vitamin_c_mg: float
    vitamin_d_ug: float


def compute_targets(*, sex: str, weight_kg: float, height_cm: float, age: int,
                    activity_level: str, goal_type: Optional[str] = None,
                    goal_period: Optional[str] = None,
                    amount_kg: Optional[float] = None) -> NutritionTargets:
    cals = target_calories(
        tdee(mifflin_st_jeor(sex, weight_kg, height_cm, age), activity_level),
        goal_type, goal_period, amount_kg,
    )
    goal_key = goal_type if goal_type in PROTEIN_G_PER_KG else "maintain"
    protein_g = PROTEIN_G_PER_KG[goal_key] * weight_kg
    fat_g = max(0.25 * cals / 9, 0.8 * weight_kg)
    carb_g = max(0.0, (cals - protein_g * 4 - fat_g * 9) / 4)
    rda = _RDA["male" if sex == "male" else "female"]
    return NutritionTargets(
        calories=cals, protein_g=protein_g, carb_g=carb_g, fat_g=fat_g,
        fiber_g=14 * cals / 1000, sodium_mg_max=2300,
        sat_fat_g_max=0.10 * cals / 9, sugar_g_max=0.10 * cals / 4, **rda,
    )
