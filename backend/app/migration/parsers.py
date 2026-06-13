"""Pure parsing of legacy Excel rows. No DB, no I/O."""
import re
from app.models import Food

_MULT = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*x\s+(.*\S)\s*$", re.IGNORECASE)


def food_from_row(row: dict) -> Food:
    def num(key):
        v = row.get(key)
        return float(v) if v is not None else 0.0

    return Food(
        name=str(row["Name"]).strip(),
        brand=str(row.get("Label") or "").strip(),
        serving_description=str(row.get("Measurement") or "100g").strip(),
        calories=num("Calories"),
        protein=num("Protein"),
        carbs=num("Carbs"),
        fat_saturated=num("Fat_Saturated"),
        fat_unsaturated=num("Fat_Regular"),
        sodium=num("Sodium"),
        source="legacy",
    )


def parse_meal_food_name(raw: str) -> tuple[float, str]:
    """'2.1x Chichen' -> (2.1, 'Chichen'). Raises ValueError on non-item rows."""
    m = _MULT.match(raw or "")
    if not m:
        raise ValueError(f"not a meal item row: {raw!r}")
    return float(m.group(1)), m.group(2).strip()
