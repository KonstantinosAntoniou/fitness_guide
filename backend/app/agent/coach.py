"""Assemble the coach agent: Gemini model + coach tools via create_agent."""
from langchain.agents import create_agent
from sqlalchemy.orm import Session
from app.agent.tools import build_tools
from app.agent.model import make_chat_model

SYSTEM_PROMPT = (
    "You are a concise, practical fitness and nutrition coach. "
    "Always ground advice in the user's real data: call get_profile for their macro + micro targets, "
    "search_my_foods / search_nutrition_database before inventing macros, and add_food_to_library for new foods. "
    "To make a day plan, choose balanced, varied, meal-appropriate foods (a protein + a carb + veg/fruit per meal) "
    "and call plan_day — it sizes the servings to hit the targets and returns a scorecard. "
    "You may refine and call plan_day at most ONCE more if a macro is well off, then PRESENT the plan and "
    "scorecard to the user. Do NOT keep re-planning to chase perfect micronutrients — some (e.g. vitamin D) are "
    "hard to hit from whole foods; just note which are low. "
    "Use log_food to record what they ate. Keep replies short; never fabricate calorie numbers — look them up."
)


def build_coach_agent(session: Session, user_id: int, model=None, nutrition_provider=None):
    tools = build_tools(session, user_id, nutrition_provider=nutrition_provider)
    return create_agent(
        model=model or make_chat_model(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
