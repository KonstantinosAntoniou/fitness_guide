import pytest
from app.core.energy import (
    mifflin_st_jeor,
    harris_benedict,
    tdee,
    ACTIVITY_MULTIPLIERS,
)


def test_mifflin_male():
    # 10*80 + 6.25*180 - 5*30 + 5 = 1780.0
    assert mifflin_st_jeor("male", 80, 180, 30) == pytest.approx(1780.0)


def test_mifflin_female():
    # 10*65 + 6.25*165 - 5*28 - 161 = 1380.25
    assert mifflin_st_jeor("female", 65, 165, 28) == pytest.approx(1380.25)


def test_harris_benedict_male():
    assert harris_benedict("male", 80, 180, 30) == pytest.approx(1853.632)


def test_harris_benedict_female():
    assert harris_benedict("female", 65, 165, 28) == pytest.approx(1438.578)


def test_invalid_sex_raises():
    with pytest.raises(ValueError):
        mifflin_st_jeor("other", 80, 180, 30)


def test_tdee_moderate():
    # 1780.0 * 1.55 = 2759.0
    assert tdee(1780.0, "moderate") == pytest.approx(2759.0)


def test_activity_levels_present():
    assert set(ACTIVITY_MULTIPLIERS) == {
        "sedentary", "light", "moderate", "active", "very_active"
    }


def test_tdee_invalid_level_raises():
    with pytest.raises(ValueError):
        tdee(1780.0, "couch")
