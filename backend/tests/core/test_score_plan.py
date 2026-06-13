import pytest
from app.core.planner import ItemSpec, score_plan
from app.core.targets import compute_targets


class F:
    def __init__(self, **k):
        for key in ("protein", "carbs", "fat_saturated", "fat_unsaturated", "calories",
                    "fiber", "sodium", "iron_mg", "calcium_mg", "potassium_mg",
                    "vitamin_c_mg", "vitamin_d_ug"):
            setattr(self, key, k.get(key, 0.0))
        self.name = k.get("name", "x")


def test_score_totals_and_micros():
    targets = compute_targets(sex="male", weight_kg=80, height_cm=180, age=30, activity_level="moderate")
    food = F(name="beef", protein=26, carbs=0, fat_saturated=6, fat_unsaturated=8,
             calories=250, iron_mg=2.6, potassium_mg=300, sodium=70)
    specs = [ItemSpec(food=food, lo=0, hi=5)]
    score = score_plan(specs, [2.0], targets)
    assert score.calories == pytest.approx(500)        # 250 * 2
    assert score.protein_g == pytest.approx(52)        # 26 * 2
    assert score.micros["iron_mg"][0] == pytest.approx(5.2)   # got
    assert score.micros["iron_mg"][1] == 8                    # target (male)
    assert 0 <= score.macro_pct()["protein"] <= 200
