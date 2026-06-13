from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.agent.coach import build_coach_agent

router = APIRouter(tags=["coach"])


class CoachRequest(BaseModel):
    message: str


def get_coach_agent_builder():
    """Dependency returning the agent builder (overridable in tests)."""
    return build_coach_agent


@router.post("/users/{user_id}/coach")
def coach(user_id: int, req: CoachRequest, db: Session = Depends(get_session),
          builder=Depends(get_coach_agent_builder)) -> dict:
    agent = builder(db, user_id)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": req.message}]},
        config={"recursion_limit": 12},
    )
    return {"reply": result["messages"][-1].content}
