"""Assemble the coach agent: Gemini model + coach tools via create_agent."""
from langchain.agents import create_agent
from sqlalchemy.orm import Session
from app.agent.tools import build_tools
from app.agent.model import make_chat_model

SYSTEM_PROMPT = (
    "You are a concise, practical fitness and nutrition coach. "
    "Always ground advice in the user's real data: call get_profile for their targets, "
    "search_my_foods / search_nutrition_database before inventing macros, and use "
    "generate_plan and log_food to take action. When you log or plan, confirm what you did. "
    "Keep replies short and specific. Never fabricate calorie numbers — look them up."
)


def build_coach_agent(session: Session, user_id: int, model=None, nutrition_provider=None):
    tools = build_tools(session, user_id, nutrition_provider=nutrition_provider)
    return create_agent(
        model=model or make_chat_model(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
