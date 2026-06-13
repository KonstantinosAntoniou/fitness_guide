import pytest
from app.db import Base, new_engine, new_session_factory
from app.repositories import FoodRepository
from app.seed.seeder import seed_staples


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_seed_is_idempotent_and_has_micros(session):
    added = seed_staples(session)
    session.commit()
    assert added >= 30
    foods = FoodRepository(session).list_all()
    assert any(f.iron_mg is not None for f in foods)  # micros present
    before = len(foods)
    seed_staples(session)            # second run adds nothing
    session.commit()
    assert len(FoodRepository(session).list_all()) == before
