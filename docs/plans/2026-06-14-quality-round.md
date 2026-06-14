# Quality Round — Assistant + Legacy Food Enrichment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise quality on two fronts the user picked — (a) the coach assistant: conversation memory, a sharper planning prompt, and the missing meal/plan tools; (b) the 66 legacy foods: keep their user-entered macros but backfill the 5 micronutrients (+ fiber/sugar) from category-appropriate sources, scaled to each serving.

**Architecture:** Coach gets a shared LangGraph checkpointer + a per-user thread (multi-turn memory). New `save_meal` / `list_my_plans` tools. Enrichment mirrors the seed: a curated `legacy_sources` map (legacy food → USDA query + serving grams) → a build script fetches USDA micros, scales to the serving, and writes a committed `legacy_micros.json`; an idempotent `enrich_legacy` applies it, preserving macros.

**Tech Stack:** langgraph checkpointer, LangChain tools, USDA provider, SQLAlchemy, pytest. Builds on the merged smart-planning work.

---

### Task 1: Conversation memory (coach checkpointer + per-user thread)

**Files:**
- Modify: `backend/app/agent/coach.py` (shared checkpointer)
- Modify: `backend/app/api/coach.py` (per-user thread_id)
- Test: `backend/tests/agent/test_coach_memory.py`

- [ ] **Step 1: Write the failing test** (a real 2-turn memory check with a scripted fake model)

```python
# backend/tests/agent/test_coach_memory.py
import pytest
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from app.db import Base, new_engine, new_session_factory
from app.models import User
from app.agent.coach import build_coach_agent


def test_agent_remembers_within_thread():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
        s.commit()
        # scripted model: never calls tools, just replies
        model = GenericFakeChatModel(messages=iter([AIMessage("Noted."), AIMessage("You said: blue.")]))
        agent = build_coach_agent(s, user_id=1, model=model)
        cfg = {"configurable": {"thread_id": "t1"}}
        agent.invoke({"messages": [{"role": "user", "content": "My favorite color is blue."}]}, config=cfg)
        out = agent.invoke({"messages": [{"role": "user", "content": "What did I say?"}]}, config=cfg)
        # the second turn's input history includes the first turn (checkpointer persisted it)
        assert out["messages"][0].content == "My favorite color is blue."
        assert len(out["messages"]) >= 3  # turn1 user+ai + turn2 user(+ai)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/agent/test_coach_memory.py -v`
Expected: FAIL — no checkpointer, so the second invoke starts fresh (only 1-2 messages).

- [ ] **Step 3: Add a shared checkpointer in `coach.py`**

```python
# at top of backend/app/agent/coach.py
from langgraph.checkpoint.memory import InMemorySaver

_CHECKPOINTER = InMemorySaver()
```

Update `build_coach_agent` to use it:

```python
def build_coach_agent(session, user_id, model=None, nutrition_provider=None, checkpointer=_CHECKPOINTER):
    tools = build_tools(session, user_id, nutrition_provider=nutrition_provider)
    return create_agent(
        model=model or make_chat_model(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 4: Pass a per-user thread in the API** (`backend/app/api/coach.py`)

Change the invoke config:

```python
        config={"recursion_limit": 30, "configurable": {"thread_id": f"user-{user_id}"}},
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/agent/test_coach_memory.py -v`
Expected: PASS (history persisted across the two invokes on thread "t1").

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/coach.py backend/app/api/coach.py backend/tests/agent/test_coach_memory.py
git commit -m "feat(agent): conversation memory (shared checkpointer + per-user thread)"
```

---

### Task 2: Sharper coaching/planning prompt

**Files:**
- Modify: `backend/app/agent/coach.py` (SYSTEM_PROMPT)
- Test: `backend/tests/agent/test_coach_build.py` (extend the prompt assertion)

- [ ] **Step 1: Update the assertion**

In `backend/tests/agent/test_coach_build.py`, replace `test_system_prompt_mentions_coaching` with:

```python
def test_system_prompt_covers_key_behaviors():
    p = SYSTEM_PROMPT.lower()
    assert "coach" in p
    assert "fat" in p          # must cover all macros incl. fat
    assert "calorie" in p      # aim for the calorie target
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/agent/test_coach_build.py -v`
Expected: FAIL (current prompt lacks "fat"/"calorie" explicitly) or import error for renamed test — fix by updating the prompt next.

- [ ] **Step 3: Rewrite `SYSTEM_PROMPT`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/agent/test_coach_build.py -v`
Expected: PASS (1 passed, 1 skipped live).

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/coach.py backend/tests/agent/test_coach_build.py
git commit -m "feat(agent): sharper planning prompt (cover all macros, hit calories, explain)"
```

---

### Task 3: `save_meal` + `list_my_plans` tools

**Files:**
- Modify: `backend/app/agent/tools.py` (import `MealItem`; add two tools)
- Test: `backend/tests/agent/test_meal_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/agent/test_meal_tools.py
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food
from app.repositories import MealRepository
from app.agent.tools import build_tools


@pytest.fixture
def ctx():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = new_session_factory(engine)()
    s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
    s.add(Food(name="Oats", serving_description="100g", calories=375, protein=11, carbs=69))
    s.add(Food(name="Banana", serving_description="1", calories=105, protein=1, carbs=27))
    s.commit()
    tools = {t.name: t for t in build_tools(s, user_id=1)}
    yield s, tools
    s.close()


def test_save_meal_creates_meal_with_items(ctx):
    session, tools = ctx
    out = tools["save_meal"].invoke({"name": "Breakfast Bowl",
                                     "items": [{"food": "Oats", "servings": 1}, {"food": "Banana", "servings": 1}]})
    assert "saved" in out.lower()
    meal = MealRepository(session).find_by_name("Breakfast Bowl")
    assert meal is not None and len(meal.items) == 2


def test_list_my_plans_empty_then_after(ctx):
    _, tools = ctx
    assert "no" in tools["list_my_plans"].invoke({}).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/agent/test_meal_tools.py -v`
Expected: FAIL — `KeyError: 'save_meal'`.

- [ ] **Step 3: Add the tools in `build_tools`** (`backend/app/agent/tools.py`)

Add `MealItem` to the models import (`from app.models import Food, MealItem`), then add these two tools and include them in the returned list:

```python
    @tool
    def save_meal(name: str, items: list[dict]) -> str:
        """Save a reusable meal from library foods. items = [{"food": name, "servings": number}]."""
        if meals_repo.find_by_name(name):
            return f"A meal named '{name}' already exists."
        meal = meals_repo.create(name)
        session.flush()
        added = 0
        for it in items:
            hits = foods.search(it.get("food", ""))
            if hits:
                session.add(MealItem(meal_id=meal.id, food_id=hits[0].id,
                                     servings=float(it.get("servings", 1))))
                added += 1
        session.commit()
        return f"Saved meal '{name}' with {added} item(s)."

    @tool
    def list_my_plans() -> str:
        """List the user's saved day plans (id, name, number of meals)."""
        ps = plans.list_for_user(user_id)
        if not ps:
            return "No saved plans yet."
        return "\n".join(f"#{p.id} {p.name} — {len(p.entries)} meals" for p in ps)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/agent/test_meal_tools.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/tools.py backend/tests/agent/test_meal_tools.py
git commit -m "feat(agent): save_meal + list_my_plans tools"
```

---

### Task 4: Legacy food enrichment (keep macros, add micros)

**Files:**
- Create: `backend/scripts/build_enrichment.py` (curated map + USDA fetch → committed JSON)
- Create: `backend/app/seed/legacy_micros.json` (generated, committed)
- Create: `backend/app/seed/enrich.py` (`enrich_legacy(session)`)
- Modify: `backend/app/main.py` (run `enrich_legacy` at startup, after seeding)
- Test: `backend/tests/test_enrich.py`

Macros are **preserved**; only `serving_grams`, `fiber`, `sugar_g`, and the 5 micros are filled, scaled `usda_per_100g * serving_grams / 100`.

- [ ] **Step 1: Write the generator** with a curated `(name → usda_query, serving_grams)` map for all 66 legacy foods (Greek items mapped to their category, e.g. `Fakes→"lentils cooked"`, `Tsipoura→"fish sea bass raw"`, `Kefalotiri→"cheese parmesan"`, `Paksimadi→"melba toast"`, branded protein powders→`"whey protein powder"`). For each, fetch USDA, scale micros to grams, write `app/seed/legacy_micros.json` keyed by lowercase name. Foods with no sensible source are skipped (micros stay null).

```python
# backend/scripts/build_enrichment.py  (skeleton — full map authored here)
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import load_project_env
from app.integrations.usda import USDAProvider

# name (lowercase, matches legacy Food.name) -> (usda query, serving grams)
SOURCES = {
    "honey": ("honey", 21), "apple": ("apples raw", 182), "oats": ("oats raw", 100),
    "egg": ("egg whole raw", 50), "banana": ("bananas raw", 118), "spinach": ("spinach raw", 100),
    "chichen": ("chicken breast raw", 100), "fakes": ("lentils cooked", 100),
    "feta_cheese": ("cheese feta", 100), "kefalotiri": ("cheese parmesan", 100),
    "tsipoura": ("fish sea bass raw", 100), "walnuts": ("walnuts raw", 100),
    "cashews": ("cashew nuts raw", 100), "olives": ("olives ripe canned", 4),
    "oliveoil": ("oil olive", 14),
    # ... (all 66 authored from the dumped legacy list)
}


def main():
    load_project_env()
    p = USDAProvider()
    out = {}
    for name, (query, grams) in SOURCES.items():
        hits = p.search(query, limit=5)
        if not hits:
            print(f"no usda for {name!r} ({query!r})"); continue
        r = hits[0]
        f = grams / 100.0
        out[name] = {
            "serving_grams": grams,
            "fiber": round((r.fiber or 0) * f, 2),
            "sugar_g": round((r.sugar_g or 0) * f, 2),
            "iron_mg": round((r.iron_mg or 0) * f, 3),
            "calcium_mg": round((r.calcium_mg or 0) * f, 1),
            "potassium_mg": round((r.potassium_mg or 0) * f, 1),
            "vitamin_c_mg": round((r.vitamin_c_mg or 0) * f, 1),
            "vitamin_d_ug": round((r.vitamin_d_ug or 0) * f, 2),
        }
        print(f"ok {name} <- {r.name}")
    dest = Path(__file__).resolve().parents[1] / "app" / "seed" / "legacy_micros.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} enrichments")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate** `legacy_micros.json` (live USDA): `cd backend && PYTHONPATH=$(pwd) uv run python scripts/build_enrichment.py`. Web-search any food USDA can't resolve and add it to the map. Commit the JSON.

- [ ] **Step 3: Write the failing applier test**

```python
# backend/tests/test_enrich.py
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import Food
from app.seed.enrich import enrich_legacy


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_enrich_fills_micros_keeps_macros(session):
    f = Food(name="Spinach", serving_description="100g", calories=23, protein=2.9, source="legacy")
    session.add(f); session.commit()
    n = enrich_legacy(session)
    session.commit()
    session.refresh(f)
    assert f.calories == 23 and f.protein == 2.9     # macros preserved
    assert (f.iron_mg or 0) > 0 or (f.potassium_mg or 0) > 0   # micros added
    assert n >= 1
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_enrich.py -v`
Expected: FAIL — `ModuleNotFoundError: app.seed.enrich`.

- [ ] **Step 5: Implement the applier**

```python
# backend/app/seed/enrich.py
"""Apply legacy_micros.json onto legacy foods — fills micros + serving_grams, keeps macros."""
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.repositories import FoodRepository

_FILE = Path(__file__).resolve().parent / "legacy_micros.json"
_FIELDS = ("serving_grams", "fiber", "sugar_g", "iron_mg", "calcium_mg",
           "potassium_mg", "vitamin_c_mg", "vitamin_d_ug")


def enrich_legacy(session: Session) -> int:
    if not _FILE.exists():
        return 0
    data = json.loads(_FILE.read_text())
    n = 0
    for food in FoodRepository(session).list_all():
        rec = data.get(food.name.lower())
        if not rec:
            continue
        if food.iron_mg is not None:  # already enriched
            continue
        for field in _FIELDS:
            if rec.get(field) is not None:
                setattr(food, field, rec[field])
        n += 1
    session.flush()
    return n
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_enrich.py -v`
Expected: 1 passed.

- [ ] **Step 7: Run enrichment at startup** — in `backend/app/main.py` lifespan, after `seed_staples`:

```python
        from app.seed.enrich import enrich_legacy
        enrich_legacy(s)
        s.commit()
```

- [ ] **Step 8: Run the full suite + commit**

Run: `cd backend && uv run pytest -q`  (all pass)

```bash
git add backend/scripts/build_enrichment.py backend/app/seed/legacy_micros.json backend/app/seed/enrich.py backend/app/main.py backend/tests/test_enrich.py
git commit -m "feat(data): enrich legacy foods with micronutrients (macros preserved)"
```

---

## Done when

- `cd backend && uv run pytest` is green.
- The coach holds a multi-turn conversation (memory) and plans cover all macros incl. fat.
- `save_meal` / `list_my_plans` work.
- Legacy foods carry micros (+ serving_grams) while keeping their original macros.

## Out of scope (this round)

- USDA-first agent search + seed expansion (deferred earlier)
- Persistent (cross-restart) conversation memory — InMemorySaver is per-process for now
