import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.db import Base, new_engine, new_session_factory, get_session
from app.main import app
from app.api.coach import get_coach_agent_builder


class FakeAgent:
    def invoke(self, payload, config=None):
        user_msg = payload["messages"][-1]["content"]
        return {"messages": [SimpleNamespace(content=f"echo: {user_msg}")]}


@pytest.fixture
def client():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestingSession = new_session_factory(engine)

    def override_session():
        with TestingSession() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_coach_agent_builder] = lambda: (lambda db, uid: FakeAgent())
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_coach_chat(client):
    r = client.post("/users/1/coach", json={"message": "make me a plan"})
    assert r.status_code == 200
    assert r.json()["reply"] == "echo: make me a plan"


def test_coach_chat_extracts_gemini_text_blocks(client):
    class FakeListAgent:
        def invoke(self, payload, config=None):
            return {"messages": [SimpleNamespace(content=[
                {"type": "text", "text": "Here is"}, {"type": "text", "text": "your plan."}])]}

    app.dependency_overrides[get_coach_agent_builder] = lambda: (lambda db, uid: FakeListAgent())
    r = client.post("/users/1/coach", json={"message": "plan"})
    assert r.status_code == 200
    assert r.json()["reply"] == "Here is\nyour plan."
