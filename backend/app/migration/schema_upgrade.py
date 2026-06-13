"""Idempotent additive schema upgrades for the existing SQLite dev DB."""
from sqlalchemy import text
from sqlalchemy.engine import Engine

_FOOD_MICRO_COLUMNS = {
    "sugar_g": "FLOAT", "iron_mg": "FLOAT", "calcium_mg": "FLOAT",
    "potassium_mg": "FLOAT", "vitamin_c_mg": "FLOAT", "vitamin_d_ug": "FLOAT",
}


def ensure_food_micro_columns(engine: Engine) -> None:
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(foods)"))}
        for name, sqltype in _FOOD_MICRO_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE foods ADD COLUMN {name} {sqltype}"))
