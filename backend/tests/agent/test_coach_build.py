import os
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User
from app.agent.coach import build_coach_agent, SYSTEM_PROMPT


def test_system_prompt_mentions_coaching():
    assert "coach" in SYSTEM_PROMPT.lower()


@pytest.mark.skipif(not os.getenv("RUN_LIVE_AGENT"),
                    reason="set RUN_LIVE_AGENT=1 (with GOOGLE_API_KEY in .env) to run the live Gemini test")
def test_live_agent_runs():
    from app.config import load_project_env
    load_project_env()
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
        s.commit()
        agent = build_coach_agent(s, user_id=1)
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "What's my calorie target?"}]},
            config={"recursion_limit": 8},
        )
        assert result["messages"][-1].content
