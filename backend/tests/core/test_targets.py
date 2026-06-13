import pytest
from app.core.targets import compute_targets, NutritionTargets


def test_targets_male_lose():
    t = compute_targets(sex="male", weight_kg=85, height_cm=181, age=30,
                        activity_level="moderate", goal_type="lose",
                        goal_period="week", amount_kg=0.5)
    assert isinstance(t, NutritionTargets)
    assert t.calories == pytest.approx(2296.19, abs=0.5)
    assert t.protein_g == pytest.approx(170.0)          # 2.0 g/kg
    assert t.fat_g == pytest.approx(68.0)               # max(25% kcal/9, 0.8 g/kg) -> 68
    assert t.carb_g == pytest.approx(251.05, abs=0.5)   # remainder
    assert t.fiber_g == pytest.approx(32.15, abs=0.1)   # 14 g / 1000 kcal
    assert t.sodium_mg_max == 2300
    assert (t.iron_mg, t.calcium_mg, t.potassium_mg, t.vitamin_c_mg, t.vitamin_d_ug) == (8, 1000, 3400, 90, 15)


def test_targets_female_maintain_micros():
    t = compute_targets(sex="female", weight_kg=60, height_cm=165, age=30,
                        activity_level="light")
    assert t.protein_g == pytest.approx(96.0)           # 1.6 g/kg, no goal -> maintain
    assert (t.iron_mg, t.potassium_mg, t.vitamin_c_mg) == (18, 2600, 75)
