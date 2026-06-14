import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import Food
from app.seed.enrich import enrich_legacy


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_enrich_fills_micros_keeps_macros(session):
    f = Food(name="Spinach", serving_description="100g", calories=23, protein=2.9, source="legacy")
    session.add(f)
    session.commit()
    n = enrich_legacy(session)
    session.commit()
    session.refresh(f)
    assert f.calories == 23 and f.protein == 2.9          # macros preserved
    assert (f.iron_mg or 0) > 0 or (f.potassium_mg or 0) > 0  # micros added
    assert n >= 1


def test_enrich_idempotent(session):
    f = Food(name="Spinach", serving_description="100g", calories=23, source="legacy")
    session.add(f)
    session.commit()
    enrich_legacy(session)
    session.commit()
    assert enrich_legacy(session) == 0   # second pass enriches nothing new
