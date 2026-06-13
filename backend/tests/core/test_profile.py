import pytest
from app.core.profile import compute_metrics


def test_compute_metrics_male_moderate_lose():
    m = compute_metrics(
        sex="male", weight_kg=80, height_cm=180, age=30,
        activity_level="moderate",
        goal_type="lose", goal_period="week", amount_kg=0.5,
    )
    assert m["bmr_msj"] == pytest.approx(1780.0)
    assert m["bmr_hb"] == pytest.approx(1853.632)
    assert m["tdee_msj"] == pytest.approx(2759.0)
    assert m["bmi"] == pytest.approx(24.6914, abs=1e-3)
    assert m["bmi_category"] == "normal"
    # target uses Mifflin TDEE: 2759 - 550 = 2209
    assert m["target_calories"] == pytest.approx(2209.0)
