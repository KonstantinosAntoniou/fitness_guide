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
