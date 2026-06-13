# Coach Agent (LangChain + Gemini) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A conversational coach agent that can answer grounded in the user's data, look up nutrition, add foods, generate day plans, and log meals from natural language — built on LangChain `create_agent` with Google Gemini.

**Architecture:** Framework choice (per framework-selection): a single-purpose tool-using agent → LangChain **`create_agent`** (runs on LangGraph internally; no custom graph needed). Tools are **closures over a DB session + user_id**, so each request builds an agent bound to that context. The chat model is built by a **provider-agnostic factory** (`agent/model.py`) defaulting to Gemini via `langchain-google-genai`. **Tests mock the LLM** — tools are tested directly over a test DB; the endpoint is tested with a fake agent. A live smoke test runs only when `GOOGLE_API_KEY` is set.

**Tech Stack:** langchain>=1.0, langchain-core>=1.0, langchain-google-genai, FastAPI, pytest.

Implements [the rebuild spec](../specs/2026-06-13-fitness-coach-rebuild-design.md) §7 (the AI agent + tools).

---

### Task 1: Deps + model factory

**Files:**
- Modify: `backend/pyproject.toml` (add `langchain`, `langchain-core`, `langchain-google-genai`)
- Modify: `backend/app/config.py` (add `llm_model`)
- Create: `backend/app/agent/__init__.py`, `backend/app/agent/model.py`
- Test: `backend/tests/agent/__init__.py`, `backend/tests/agent/test_model.py`

- [ ] **Step 1: Add dependencies**

Run: `uv add --directory backend "langchain>=1.0,<2.0" "langchain-core>=1.0,<2.0" langchain-google-genai`
Expected: resolves and installs.

- [ ] **Step 2: Add `llm_model` to settings**

In `backend/app/config.py`, add to `Settings`:

```python
    llm_model: str = "gemini-2.5-flash"
```

- [ ] **Step 3: Write the failing test**

```python
# backend/tests/agent/test_model.py
import pytest
from app.agent.model import make_chat_model


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr("app.agent.model.settings.llm_provider", "nope")
    with pytest.raises(ValueError):
        make_chat_model()


def test_google_model_built(monkeypatch):
    monkeypatch.setattr("app.agent.model.settings.llm_provider", "google")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    model = make_chat_model()
    assert "gemini" in model.model.lower()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/agent/test_model.py -v`
Expected: FAIL — `ModuleNotFoundError: app.agent.model`.

- [ ] **Step 5: Implement the factory**

```python
# backend/app/agent/model.py
"""Provider-agnostic chat-model factory. Defaults to Gemini (AI Studio key)."""
from app.config import settings


def make_chat_model(model_name: str | None = None, temperature: float = 0.2):
    provider = settings.llm_provider
    name = model_name or settings.llm_model
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=name, temperature=temperature)
    if provider == "openai":
        from langchain_openai import ChatOpenAI  # requires `uv add langchain-openai`
        return ChatOpenAI(model=name, temperature=temperature)
    raise ValueError(f"unsupported llm_provider: {provider!r}")
```

(Create empty `backend/app/agent/__init__.py` and `backend/tests/agent/__init__.py`.)

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/agent/test_model.py -v`
Expected: 2 passed. (If `ChatGoogleGenerativeAI` construction needs more than a dummy key, mark `test_google_model_built` with `@pytest.mark.skipif` and move on.)

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/config.py backend/app/agent/__init__.py backend/app/agent/model.py backend/tests/agent/
git commit -m "feat(agent): deps + provider-agnostic Gemini model factory"
```

---

### Task 2: Food search in the repository

**Files:**
- Modify: `backend/app/repositories.py` (add `FoodRepository.search`)
- Test: `backend/tests/test_food_search.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_food_search.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_food_search.py -v`
Expected: FAIL — `AttributeError: 'FoodRepository' object has no attribute 'search'`.

- [ ] **Step 3: Add the method**

Add to `FoodRepository` in `backend/app/repositories.py`:

```python
    def search(self, query: str, limit: int = 20) -> list[Food]:
        like = f"%{query.strip()}%"
        return list(self.s.scalars(
            select(Food).where(Food.name.ilike(like)).order_by(Food.name).limit(limit)
        ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_food_search.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories.py backend/tests/test_food_search.py
git commit -m "feat(repositories): partial food name search"
```

---

### Task 3: Coach tools

**Files:**
- Create: `backend/app/agent/tools.py`
- Test: `backend/tests/agent/test_tools.py`

Tools are closures over `(session, user_id, nutrition_provider)`. Each wraps existing core/repos/integrations and returns concise text for the LLM.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/agent/test_tools.py
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food
from app.repositories import PlanRepository, LogRepository
from app.agent.tools import build_tools
from app.integrations.nutrition import NutritionResult


class FakeProvider:
    def search(self, query, limit=5):
        return [NutritionResult(name="Tofu", calories=144, protein=15, carbs=3,
                                fat_saturated=1, fat_unsaturated=8, sodium=0.01)]


@pytest.fixture
def ctx():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = new_session_factory(engine)()
    s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
    s.add(Food(name="Rice", serving_description="100g", calories=130, protein=2.7))
    s.add(Food(name="Chicken", serving_description="100g", calories=165, protein=31))
    s.commit()
    tools = {t.name: t for t in build_tools(s, user_id=1, nutrition_provider=FakeProvider())}
    yield s, tools
    s.close()


def test_get_profile_tool(ctx):
    _, tools = ctx
    out = tools["get_profile"].invoke({})
    assert "kcal" in out and "K" in out


def test_search_nutrition_tool(ctx):
    _, tools = ctx
    assert "Tofu" in tools["search_nutrition_database"].invoke({"query": "tofu"})


def test_generate_plan_tool_persists(ctx):
    session, tools = ctx
    out = tools["generate_plan"].invoke({"target_calories": 2000, "meals": 2})
    assert "plan" in out.lower()
    assert len(PlanRepository(session).list_for_user(1)) == 1


def test_log_food_tool_persists(ctx):
    import datetime
    session, tools = ctx
    out = tools["log_food"].invoke({"name": "rice", "servings": 2})
    assert "Logged" in out
    assert len(LogRepository(session).for_day(1, datetime.date.today())) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/agent/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: app.agent.tools`.

- [ ] **Step 3: Implement the tools**

```python
# backend/app/agent/tools.py
"""Coach agent tools — closures bound to a DB session + user."""
import datetime
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.models import Food
from app.repositories import FoodRepository, UserRepository, PlanRepository, LogRepository
from app.core.profile import compute_metrics
from app.core.planner import build_day_plan
from app.core.macros import scale_food, sum_macros
from app.integrations.openfoodfacts import OpenFoodFactsProvider


def build_tools(session: Session, user_id: int, nutrition_provider=None):
    provider = nutrition_provider or OpenFoodFactsProvider()
    foods = FoodRepository(session)
    users = UserRepository(session)
    plans = PlanRepository(session)
    logs = LogRepository(session)

    @tool
    def get_profile() -> str:
        """Get the current user's profile and computed daily calorie/macro targets. Use to ground advice in their real data."""
        u = users.get(user_id)
        if not u:
            return "No profile found for this user."
        m = compute_metrics(sex=u.sex, weight_kg=u.weight_kg, height_cm=u.height_cm,
                            age=u.age, activity_level=u.activity_level, goal_type=u.goal_type,
                            goal_period=u.goal_period, amount_kg=u.amount_kg)
        return (f"{u.name}: target {round(m['target_calories'])} kcal/day "
                f"(TDEE {round(m['tdee_msj'])}), BMI {round(m['bmi'], 1)} ({m['bmi_category']}).")

    @tool
    def search_my_foods(query: str) -> str:
        """Search the user's saved food library by name. Returns matches with per-serving calories."""
        results = foods.search(query)
        if not results:
            return f"No saved foods match '{query}'."
        return "\n".join(f"#{f.id} {f.name} ({f.brand}) — {f.calories} kcal / {f.serving_description}"
                         for f in results[:10])

    @tool
    def search_nutrition_database(query: str) -> str:
        """Look up a food's macros from Open Food Facts when it's not in the user's library (values per 100g)."""
        results = provider.search(query, limit=5)
        if not results:
            return f"No nutrition data found for '{query}'."
        return "\n".join(
            f"{r.name} ({r.brand}) — {r.calories} kcal, P{r.protein}/C{r.carbs}/"
            f"F{round(r.fat_saturated + r.fat_unsaturated, 1)} per 100g" for r in results)

    @tool
    def add_food_to_library(name: str, calories: float, protein: float = 0.0,
                            carbs: float = 0.0, fat: float = 0.0,
                            serving_description: str = "100g", brand: str = "") -> str:
        """Add a new food to the user's library (macros per serving) so it can be planned or logged."""
        if foods.find_by_name_brand(name, brand):
            return f"'{name}' is already in the library."
        f = foods.add(Food(name=name, brand=brand, serving_description=serving_description,
                           calories=calories, protein=protein, carbs=carbs,
                           fat_unsaturated=fat, source="agent"))
        session.commit()
        return f"Added '{name}' (#{f.id})."

    @tool
    def generate_plan(target_calories: float, meals: int = 3) -> str:
        """Generate and save a day meal plan from the user's food library hitting the calorie target."""
        candidates = foods.list_all()
        try:
            draft = build_day_plan(target_calories, candidates, meals=meals)
        except ValueError as e:
            return f"Could not build a plan: {e}"
        plan = plans.save_draft(user_id=user_id, name="Coach plan", draft=draft)
        session.commit()
        lines = [f"Saved plan #{plan.id} (~{round(target_calories)} kcal):"]
        for entry in plan.entries:
            items = ", ".join(f"{round(it.servings, 1)}x {it.food.name}" for it in entry.items)
            lines.append(f"- {entry.name}: {items}")
        return "\n".join(lines)

    @tool
    def log_food(name: str, servings: float = 1.0) -> str:
        """Log that the user ate a food from their library, by name. `servings` = how many servings."""
        matches = foods.search(name)
        if not matches:
            return f"'{name}' is not in the library — add it first with add_food_to_library."
        food = matches[0]
        logs.add(user_id=user_id, food_id=food.id, servings=servings, source="agent")
        session.commit()
        return f"Logged {servings}x {food.name} ({round(food.calories * servings)} kcal)."

    @tool
    def todays_intake() -> str:
        """Summarize what the user has logged today (calories + macros)."""
        entries = logs.for_day(user_id, datetime.date.today())
        if not entries:
            return "Nothing logged today yet."
        total = sum_macros([scale_food(e.food, e.servings) for e in entries])
        return (f"Today: {round(total.calories)} kcal, P{round(total.protein)} "
                f"C{round(total.carbs)} F{round(total.fat_total)} across {len(entries)} items.")

    return [get_profile, search_my_foods, search_nutrition_database,
            add_food_to_library, generate_plan, log_food, todays_intake]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/agent/test_tools.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/tools.py backend/tests/agent/test_tools.py
git commit -m "feat(agent): coach tools (profile, search, add, plan, log)"
```

---

### Task 4: Coach agent builder

**Files:**
- Create: `backend/app/agent/coach.py`
- Test: `backend/tests/agent/test_coach_build.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/agent/test_coach_build.py
import os
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User
from app.agent.coach import build_coach_agent, SYSTEM_PROMPT


def test_system_prompt_mentions_coaching():
    assert "coach" in SYSTEM_PROMPT.lower()


@pytest.mark.skipif(not os.getenv("GOOGLE_API_KEY"), reason="needs GOOGLE_API_KEY for live LLM")
def test_live_agent_runs():
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/agent/test_coach_build.py -v`
Expected: FAIL — `ModuleNotFoundError: app.agent.coach` (live test skips without key).

- [ ] **Step 3: Implement the builder**

```python
# backend/app/agent/coach.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/agent/test_coach_build.py -v`
Expected: 1 passed, 1 skipped (live test).

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/coach.py backend/tests/agent/test_coach_build.py
git commit -m "feat(agent): coach agent builder (create_agent + Gemini + tools)"
```

---

### Task 5: Coach chat API

**Files:**
- Create: `backend/app/api/coach.py`
- Modify: `backend/app/main.py` (include coach router)
- Test: `backend/tests/api/test_coach_api.py`

- [ ] **Step 1: Write the failing test (fake agent, no LLM)**

```python
# backend/tests/api/test_coach_api.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_coach_api.py -v`
Expected: FAIL (coach router missing).

- [ ] **Step 3: Implement the coach router**

```python
# backend/app/api/coach.py
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
```

- [ ] **Step 4: Register the router in main.py**

Add to `backend/app/main.py`: `from app.api.coach import router as coach_router` and `app.include_router(coach_router)`.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass (live agent test skipped without key).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/coach.py backend/app/main.py backend/tests/api/test_coach_api.py
git commit -m "feat(api): coach chat endpoint"
```

---

## Done when

- `cd backend && uv run pytest` is green (LLM mocked; live agent test skipped without a key).
- With `GOOGLE_API_KEY` set in `backend/.env`, `POST /users/{id}/coach` drives a real Gemini agent that calls the tools (generate a plan, log food, answer from profile).

## Live smoke (needs the key)

1. Put `GOOGLE_API_KEY=...` in `backend/.env`.
2. `cd backend && uv run pytest tests/agent/test_coach_build.py -v` → the live test now runs.
3. Or run the server and POST a message to `/users/1/coach`.

## Out of scope (later plans)

- Confirm-before-write (human-in-the-loop) on logging — can add `HumanInTheLoopMiddleware` later
- Conversation persistence (checkpointer + thread per user) — add when the frontend has sessions
- Next.js frontend (Plan 6)
