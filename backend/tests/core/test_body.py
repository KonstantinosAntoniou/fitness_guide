import pytest
from app.core.body import bmi, bmi_category


def test_bmi():
    # 80 / (1.8^2) = 24.6914...
    assert bmi(80, 180) == pytest.approx(24.6914, abs=1e-3)


@pytest.mark.parametrize("value,expected", [
    (17.0, "underweight"),
    (22.0, "normal"),
    (27.0, "overweight"),
    (32.0, "obese"),
])
def test_bmi_category(value, expected):
    assert bmi_category(value) == expected
