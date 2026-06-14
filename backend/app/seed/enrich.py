"""Apply legacy_micros.json onto legacy foods — fills micros + serving_grams, keeps macros."""
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.repositories import FoodRepository

_FILE = Path(__file__).resolve().parent / "legacy_micros.json"
_FIELDS = ("serving_grams", "fiber", "sugar_g", "iron_mg", "calcium_mg",
           "potassium_mg", "vitamin_c_mg", "vitamin_d_ug")


def enrich_legacy(session: Session) -> int:
    """Backfill micros onto foods whose name matches the enrichment data. Idempotent
    (skips foods already enriched). Macros are never touched."""
    if not _FILE.exists():
        return 0
    data = json.loads(_FILE.read_text())
    n = 0
    for food in FoodRepository(session).list_all():
        rec = data.get(food.name.lower())
        if not rec or food.iron_mg is not None:  # no source, or already enriched
            continue
        for field in _FIELDS:
            if rec.get(field) is not None:
                setattr(food, field, rec[field])
        n += 1
    session.flush()
    return n
