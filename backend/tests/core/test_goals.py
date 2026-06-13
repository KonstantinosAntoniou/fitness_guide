import pytest
from app.core.goals import target_calories, PERIOD_DAYS, KCAL_PER_KG


def test_constants():
    assert KCAL_PER_KG == 7700
    assert PERIOD_DAYS == {"week": 7, "month": 30, "year": 365}


def test_lose_half_kg_per_week():
    # delta/day = 0.5 * 7700 / 7 = 550 ; 2759 - 550 = 2209
    assert target_calories(2759.0, "lose", "week", 0.5) == pytest.approx(2209.0)


def test_gain_per_month():
    # delta/day = 2 * 7700 / 30 = 513.333... ; 2759 + 513.333 = 3272.333
    assert target_calories(2759.0, "gain", "month", 2.0) == pytest.approx(3272.3333, abs=1e-3)


def test_no_goal_is_maintenance():
    assert target_calories(2759.0, None, None, None) == pytest.approx(2759.0)


def test_invalid_period_raises():
    with pytest.raises(ValueError):
        target_calories(2759.0, "lose", "fortnight", 0.5)
