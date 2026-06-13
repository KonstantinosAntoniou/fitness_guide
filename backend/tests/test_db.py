from sqlalchemy import text
from app.db import Base, new_engine, new_session_factory


def test_create_all_and_session_roundtrip():
    engine = new_engine("sqlite://")  # in-memory
    Base.metadata.create_all(engine)
    Session = new_session_factory(engine)
    with Session() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1
