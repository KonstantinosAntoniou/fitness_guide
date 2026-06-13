import pytest
from sqlalchemy import text
from app.db import Base, new_engine, new_session_factory
from app.models import Food
from app.migration.schema_upgrade import ensure_food_micro_columns


def test_food_has_micro_fields():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        f = Food(name="Spinach", calories=23, iron_mg=2.7, calcium_mg=99,
                 potassium_mg=558, vitamin_c_mg=28, vitamin_d_ug=0, sugar_g=0.4)
        s.add(f)
        s.commit()
        assert f.iron_mg == 2.7 and f.potassium_mg == 558


def test_ensure_columns_idempotent_on_old_table():
    engine = new_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE foods (id INTEGER PRIMARY KEY, name VARCHAR, calories FLOAT)"))
    ensure_food_micro_columns(engine)
    ensure_food_micro_columns(engine)  # second run must not error
    with engine.begin() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(foods)"))}
    assert {"iron_mg", "calcium_mg", "potassium_mg", "vitamin_c_mg", "vitamin_d_ug", "sugar_g"} <= cols
