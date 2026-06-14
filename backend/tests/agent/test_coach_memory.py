from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from app.db import Base, new_engine, new_session_factory
from app.models import User
from app.agent.coach import build_coach_agent


class FakeToolModel(BaseChatModel):
    """Minimal chat model that survives create_agent (bind_tools) and never calls tools."""

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])


def test_agent_remembers_within_thread():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
        s.commit()
        agent = build_coach_agent(s, user_id=1, model=FakeToolModel())
        cfg = {"configurable": {"thread_id": "t1"}}
        agent.invoke({"messages": [{"role": "user", "content": "My favorite color is blue."}]}, config=cfg)
        out = agent.invoke({"messages": [{"role": "user", "content": "What did I say?"}]}, config=cfg)
        # checkpointer persisted turn 1, so the history starts with the first user message
        assert out["messages"][0].content == "My favorite color is blue."
        assert len(out["messages"]) >= 3
