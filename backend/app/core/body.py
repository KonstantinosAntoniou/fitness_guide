"""Body-composition helpers."""


def bmi(weight_kg: float, height_cm: float) -> float:
    height_m = height_cm / 100
    return weight_kg / (height_m ** 2)


def bmi_category(value: float) -> str:
    if value < 18.5:
        return "underweight"
    if value < 25:
        return "normal"
    if value < 30:
        return "overweight"
    return "obese"
