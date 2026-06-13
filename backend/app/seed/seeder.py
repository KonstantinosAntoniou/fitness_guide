"""Load the committed staples.json into the food library (idempotent on name+brand)."""
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Food
from app.repositories import FoodRepository

_SEED_FILE = Path(__file__).resolve().parent / "staples.json"
_FOOD_FIELDS = {
    "name", "brand", "serving_description", "serving_grams", "source", "source_id",
    "calories", "protein", "carbs", "fat_saturated", "fat_unsaturated", "fiber", "sodium",
    "sugar_g", "iron_mg", "calcium_mg", "potassium_mg", "vitamin_c_mg", "vitamin_d_ug",
}


def seed_staples(session: Session) -> int:
    if not _SEED_FILE.exists():
        return 0
    repo = FoodRepository(session)
    records = json.loads(_SEED_FILE.read_text())
    added = 0
    for rec in records:
        name, brand = rec.get("name", ""), rec.get("brand", "") or ""
        if not name or repo.find_by_name_brand(name, brand):
            continue
        repo.add(Food(**{k: v for k, v in rec.items() if k in _FOOD_FIELDS}))
        added += 1
    session.flush()
    return added
