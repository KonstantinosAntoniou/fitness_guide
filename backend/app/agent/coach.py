"""Assemble the coach agent: Gemini model + coach tools via create_agent."""
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session
from app.agent.tools import build_tools
from app.agent.model import make_chat_model

# Shared in-process checkpointer so a per-user thread keeps conversation history
# across requests (resets on server restart — a persistent store is a later upgrade).
_CHECKPOINTER = InMemorySaver()

SYSTEM_PROMPT = (
    "You are a concise, practical fitness and nutrition coach. Ground every answer in the user's real "
    "data: call get_profile for their macro + micro targets and check todays_intake when relevant. "
    "Look foods up (search_my_foods, then search_nutrition_database) instead of inventing macros; "
    "add_food_to_library for new ones. "
    "When building a day plan, pick balanced, varied, meal-appropriate foods and ALWAYS cover every "
    "macro — include a protein source, a carb source, vegetables/fruit, AND a fat source (oil, nuts, "
    "dairy) so the plan reaches the calorie and fat targets, not just protein. Honor stated preferences "
    "and dislikes. Call plan_day; it returns a scorecard. You may refine and call plan_day ONCE more if "
    "calories or a macro are well off target, then present the plan and scorecard and briefly explain it. "
    "Do not chase perfect micronutrients (e.g. vitamin D is hard from food) — just note which are low. "
    "Use save_meal to store a reusable meal and log_food to record eating. Keep replies short; never "
    "fabricate numbers."
)


def build_coach_agent(session: Session, user_id: int, model=None, nutrition_provider=None,
                      checkpointer=_CHECKPOINTER):
    tools = build_tools(session, user_id, nutrition_provider=nutrition_provider)
    return create_agent(
        model=model or make_chat_model(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
