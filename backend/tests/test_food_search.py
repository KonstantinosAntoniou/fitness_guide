import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import Food
from app.repositories import FoodRepository


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_search_partial_case_insensitive(session):
    repo = FoodRepository(session)
    repo.add(Food(name="Greek Yogurt", calories=59))
    repo.add(Food(name="Brown Rice", calories=130))
    session.commit()
    names = [f.name for f in repo.search("rice")]
    assert names == ["Brown Rice"]
    assert len(repo.search("e")) == 2  # both contain 'e'


def test_search_matches_reordered_usda_names(session):
    repo = FoodRepository(session)
    repo.add(Food(name="Rice, Brown, Parboiled, Cooked", calories=120))
    repo.add(Food(name="Yogurt, Greek, Plain, Nonfat", calories=59))
    session.commit()
    # natural multi-word queries must match the reordered "Noun, modifier" names
    assert [f.name for f in repo.search("brown rice")] == ["Rice, Brown, Parboiled, Cooked"]
    assert [f.name for f in repo.search("greek yogurt")] == ["Yogurt, Greek, Plain, Nonfat"]
