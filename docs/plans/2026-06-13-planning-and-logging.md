# Planning + Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured day plans and food logging — the `Plan/PlanEntry/PlanItem` and `LogEntry` tables, pure macro math, a deterministic day-plan builder, and the repositories + API to generate/save plans and log what was eaten with a day summary.

**Architecture:** Macro math and the plan builder are pure functions in `core/` (the LLM will later choose *which* foods; `core` does the arithmetic — see spec §7). Persistence via repositories; the API exposes generate/save/get plan and log/summary. Macros are computed from structured items, never stored frozen.

**Tech Stack:** SQLAlchemy 2.0, FastAPI, Pydantic v2, pytest.

Implements [the rebuild spec](../specs/2026-06-13-fitness-coach-rebuild-design.md) §6 (Plan/Log tables) and §7 (LLM judges, core computes).

---

### Task 1: Plan / PlanEntry / PlanItem / LogEntry models

**Files:**
- Modify: `backend/app/models.py` (append new models + import `date`)
- Test: `backend/tests/test_plan_models.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_plan_models.py
import datetime
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food, Plan, PlanEntry, PlanItem, LogEntry


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_plan_tree(session):
    food = Food(name="Rice", serving_description="100g", calories=130)
    session.add(food)
    session.flush()
    plan = Plan(name="Day 1", entries=[
        PlanEntry(name="Lunch", position=0, items=[PlanItem(food_id=food.id, servings=2.0)])
    ])
    session.add(plan)
    session.commit()
    assert plan.entries[0].items[0].food.name == "Rice"
    assert plan.entries[0].items[0].servings == 2.0


def test_log_entry_defaults_today(session):
    food = Food(name="Egg", serving_description="1", calories=78)
    session.add(food)
    session.flush()
    log = LogEntry(user_id=1, food_id=food.id, servings=2.0)
    session.add(log)
    session.commit()
    assert log.eaten_on == datetime.date.today()
    assert log.source == "manual"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_plan_models.py -v`
Expected: FAIL — `ImportError` (Plan/PlanEntry/etc not defined).

- [ ] **Step 3: Append the models**

Add `from datetime import date` to the imports at the top of `backend/app/models.py`, then append:

```python
class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), default=None)
    name: Mapped[str] = mapped_column(String, default="Plan")
    entries: Mapped[list["PlanEntry"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanEntry.position"
    )


class PlanEntry(Base):
    __tablename__ = "plan_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    name: Mapped[str] = mapped_column(String, default="Meal")
    position: Mapped[int] = mapped_column(default=0)
    plan: Mapped["Plan"] = relationship(back_populates="entries")
    items: Mapped[list["PlanItem"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class PlanItem(Base):
    __tablename__ = "plan_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("plan_entries.id"))
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    servings: Mapped[float] = mapped_column(default=1.0)
    entry: Mapped["PlanEntry"] = relationship(back_populates="items")
    food: Mapped["Food"] = relationship()


class LogEntry(Base):
    __tablename__ = "log_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    eaten_on: Mapped[date] = mapped_column(default=date.today)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    servings: Mapped[float] = mapped_column(default=1.0)
    source: Mapped[str] = mapped_column(String, default="manual")
    food: Mapped["Food"] = relationship()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_plan_models.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_plan_models.py
git commit -m "feat(models): Plan, PlanEntry, PlanItem, LogEntry"
```

---

### Task 2: Macro math (`core/macros.py`)

**Files:**
- Create: `backend/app/core/macros.py`
- Test: `backend/tests/core/test_macros.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/test_macros.py
import pytest
from app.core.macros import Macros, scale_food, sum_macros


class FakeFood:
    def __init__(self, **kw):
        self.calories = kw.get("calories", 0)
        self.protein = kw.get("protein", 0)
        self.carbs = kw.get("carbs", 0)
        self.fat_saturated = kw.get("fat_saturated", 0)
        self.fat_unsaturated = kw.get("fat_unsaturated", 0)
        self.fiber = kw.get("fiber")
        self.sodium = kw.get("sodium", 0)


def test_scale_food():
    f = FakeFood(calories=100, protein=10, carbs=20, fat_saturated=1, fat_unsaturated=2, sodium=0.5)
    m = scale_food(f, 2.5)
    assert m.calories == 250
    assert m.protein == 25
    assert m.fat_total == pytest.approx(7.5)


def test_scale_food_handles_none_fiber():
    m = scale_food(FakeFood(calories=50, fiber=None), 2)
    assert m.fiber == 0


def test_sum_macros():
    total = sum_macros([
        Macros(calories=100, protein=10),
        Macros(calories=200, protein=5),
    ])
    assert total.calories == 300
    assert total.protein == 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_macros.py -v`
Expected: FAIL — `ModuleNotFoundError: app.core.macros`.

- [ ] **Step 3: Implement macro math**

```python
# backend/app/core/macros.py
"""Pure macro arithmetic. No DB, no frameworks."""
from dataclasses import dataclass, fields
from typing import Iterable, Protocol, Optional


@dataclass
class Macros:
    calories: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat_saturated: float = 0.0
    fat_unsaturated: float = 0.0
    fiber: float = 0.0
    sodium: float = 0.0

    @property
    def fat_total(self) -> float:
        return self.fat_saturated + self.fat_unsaturated

    def __add__(self, other: "Macros") -> "Macros":
        return Macros(**{f.name: getattr(self, f.name) + getattr(other, f.name)
                         for f in fields(self)})


class FoodLike(Protocol):
    calories: float
    protein: float
    carbs: float
    fat_saturated: float
    fat_unsaturated: float
    fiber: Optional[float]
    sodium: float


def scale_food(food: FoodLike, servings: float) -> Macros:
    return Macros(
        calories=(food.calories or 0) * servings,
        protein=(food.protein or 0) * servings,
        carbs=(food.carbs or 0) * servings,
        fat_saturated=(food.fat_saturated or 0) * servings,
        fat_unsaturated=(food.fat_unsaturated or 0) * servings,
        fiber=(food.fiber or 0) * servings,
        sodium=(food.sodium or 0) * servings,
    )


def sum_macros(items: Iterable[Macros]) -> Macros:
    total = Macros()
    for m in items:
        total = total + m
    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_macros.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/macros.py backend/tests/core/test_macros.py
git commit -m "feat(core): macro arithmetic (scale + sum)"
```

---

### Task 3: Deterministic day-plan builder (`core/planner.py`)

**Files:**
- Create: `backend/app/core/planner.py`
- Test: `backend/tests/core/test_planner.py`

The builder does the **math** only: split target calories across meals, pick candidate foods by rotation, and portion each meal evenly by calories to hit its target. (The LLM will later choose smarter foods; this stays deterministic and correct.)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/test_planner.py
import pytest
from app.core.planner import portion_to_calories, build_day_plan


class FakeFood:
    def __init__(self, id, calories):
        self.id = id
        self.calories = calories
        self.protein = self.carbs = self.fat_saturated = self.fat_unsaturated = self.sodium = 0
        self.fiber = 0


def test_portion_to_calories_even_split():
    foods = [FakeFood(1, 100), FakeFood(2, 200)]
    servings = portion_to_calories(foods, 1000)
    # even calorie split: 500 each -> 5.0 and 2.5 servings
    assert servings == pytest.approx([5.0, 2.5])
    total = sum(f.calories * s for f, s in zip(foods, servings))
    assert total == pytest.approx(1000)


def test_portion_rejects_zero_calorie_food():
    with pytest.raises(ValueError):
        portion_to_calories([FakeFood(1, 0)], 500)


def test_build_day_plan_hits_target_and_meal_count():
    candidates = [FakeFood(1, 100), FakeFood(2, 200), FakeFood(3, 50)]
    plan = build_day_plan(target_calories=2000, candidates=candidates, meals=2, foods_per_meal=2)
    assert len(plan) == 2
    total = sum(f.calories * s for entry in plan for f, s in entry["items"])
    assert total == pytest.approx(2000)
    assert plan[0]["name"] == "Meal 1"


def test_build_day_plan_requires_candidates():
    with pytest.raises(ValueError):
        build_day_plan(2000, candidates=[FakeFood(1, 0)], meals=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_planner.py -v`
Expected: FAIL — `ModuleNotFoundError: app.core.planner`.

- [ ] **Step 3: Implement the builder**

```python
# backend/app/core/planner.py
"""Deterministic day-plan math. The LLM picks foods; this portions them."""
from typing import Protocol


class FoodLike(Protocol):
    calories: float


def portion_to_calories(foods: list, target_calories: float) -> list[float]:
    """Servings per food so the group hits target_calories with an even calorie split."""
    if not foods:
        raise ValueError("no foods to portion")
    share = target_calories / len(foods)
    servings = []
    for f in foods:
        if not f.calories or f.calories <= 0:
            raise ValueError(f"food {getattr(f, 'id', '?')} has non-positive calories")
        servings.append(share / f.calories)
    return servings


def build_day_plan(target_calories: float, candidates: list, meals: int = 3,
                   foods_per_meal: int = 2) -> list[dict]:
    """Split target across `meals`; fill each meal by rotating through candidates.

    Returns a list of {"name": str, "items": [(food, servings), ...]}.
    """
    usable = [f for f in candidates if getattr(f, "calories", 0) and f.calories > 0]
    if not usable:
        raise ValueError("no usable candidate foods (need positive calories)")

    per_meal = target_calories / meals
    plan: list[dict] = []
    cursor = 0
    for i in range(meals):
        chosen = []
        for _ in range(foods_per_meal):
            chosen.append(usable[cursor % len(usable)])
            cursor += 1
        servings = portion_to_calories(chosen, per_meal)
        plan.append({
            "name": f"Meal {i + 1}",
            "items": list(zip(chosen, servings)),
        })
    return plan
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_planner.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/planner.py backend/tests/core/test_planner.py
git commit -m "feat(core): deterministic day-plan builder (portion to calories)"
```

---

### Task 4: Plan & Log repositories

**Files:**
- Modify: `backend/app/repositories.py` (add `PlanRepository`, `LogRepository`)
- Test: `backend/tests/test_plan_repositories.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_plan_repositories.py
import datetime
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import Food
from app.repositories import PlanRepository, LogRepository


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def _food(session, **kw):
    f = Food(name=kw.get("name", "X"), serving_description="100g", **{k: v for k, v in kw.items() if k != "name"})
    session.add(f)
    session.flush()
    return f


def test_save_and_get_plan(session):
    f = _food(session, name="Rice", calories=130)
    repo = PlanRepository(session)
    draft = [{"name": "Lunch", "items": [(f, 2.0)]}]
    plan = repo.save_draft(user_id=1, name="Day 1", draft=draft)
    session.commit()
    loaded = repo.get(plan.id)
    assert loaded.name == "Day 1"
    assert loaded.entries[0].items[0].servings == 2.0


def test_log_and_day_entries(session):
    f = _food(session, name="Egg", calories=78)
    repo = LogRepository(session)
    repo.add(user_id=1, food_id=f.id, servings=3.0)
    session.commit()
    today = datetime.date.today()
    entries = repo.for_day(user_id=1, day=today)
    assert len(entries) == 1
    assert entries[0].servings == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_plan_repositories.py -v`
Expected: FAIL — `ImportError` (PlanRepository/LogRepository missing).

- [ ] **Step 3: Add the repositories**

Append to `backend/app/repositories.py` (and add `import datetime` at top):

```python
from app.models import Plan, PlanEntry, PlanItem, LogEntry


class PlanRepository:
    def __init__(self, session: Session):
        self.s = session

    def save_draft(self, user_id: Optional[int], name: str, draft: list[dict]) -> Plan:
        plan = Plan(user_id=user_id, name=name)
        for pos, entry in enumerate(draft):
            pe = PlanEntry(name=entry.get("name", f"Meal {pos + 1}"), position=pos)
            for food, servings in entry["items"]:
                pe.items.append(PlanItem(food_id=food.id, servings=servings))
            plan.entries.append(pe)
        self.s.add(plan)
        return plan

    def get(self, plan_id: int) -> Optional[Plan]:
        return self.s.get(Plan, plan_id)

    def list_for_user(self, user_id: int) -> list[Plan]:
        return list(self.s.scalars(select(Plan).where(Plan.user_id == user_id)))


class LogRepository:
    def __init__(self, session: Session):
        self.s = session

    def add(self, user_id: int, food_id: int, servings: float, source: str = "manual") -> LogEntry:
        entry = LogEntry(user_id=user_id, food_id=food_id, servings=servings, source=source)
        self.s.add(entry)
        return entry

    def for_day(self, user_id: int, day: "datetime.date") -> list[LogEntry]:
        return list(self.s.scalars(
            select(LogEntry).where(LogEntry.user_id == user_id, LogEntry.eaten_on == day)
        ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_plan_repositories.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories.py backend/tests/test_plan_repositories.py
git commit -m "feat(repositories): Plan and Log data access"
```

---

### Task 5: Plan generation + retrieval API

**Files:**
- Create: `backend/app/api/plans.py`
- Modify: `backend/app/main.py` (include plans router)
- Test: `backend/tests/api/test_plans_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_plans_api.py
import pytest
from fastapi.testclient import TestClient
from app.db import Base, new_engine, new_session_factory, get_session
from app.main import app
from app.models import User, Food


@pytest.fixture
def client():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestingSession = new_session_factory(engine)
    # seed a user + foods
    with TestingSession() as s:
        s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
        s.add(Food(name="Rice", serving_description="100g", calories=130, protein=2.7))
        s.add(Food(name="Chicken", serving_description="100g", calories=165, protein=31))
        s.commit()

    def override():
        with TestingSession() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_generate_plan_hits_target(client):
    r = client.post("/users/1/plans/generate", json={"target_calories": 2000, "meals": 2, "foods_per_meal": 2})
    assert r.status_code == 201
    body = r.json()
    assert body["name"]
    assert body["totals"]["calories"] == pytest.approx(2000, abs=1)
    assert len(body["entries"]) == 2

    # it was persisted and is retrievable
    plan_id = body["id"]
    r2 = client.get(f"/plans/{plan_id}")
    assert r2.status_code == 200
    assert r2.json()["totals"]["calories"] == pytest.approx(2000, abs=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_plans_api.py -v`
Expected: FAIL (plans router missing).

- [ ] **Step 3: Implement the plans router**

```python
# backend/app/api/plans.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.repositories import FoodRepository, PlanRepository
from app.core.planner import build_day_plan
from app.core.macros import scale_food, sum_macros

router = APIRouter(tags=["plans"])


class GenerateRequest(BaseModel):
    target_calories: float
    meals: int = 3
    foods_per_meal: int = 2


class ItemOut(BaseModel):
    food_id: int
    name: str
    servings: float
    calories: float


class EntryOut(BaseModel):
    name: str
    items: list[ItemOut]


class PlanOut(BaseModel):
    id: int
    name: str
    entries: list[EntryOut]
    totals: dict


def _plan_out(plan) -> PlanOut:
    entries, all_macros = [], []
    for entry in plan.entries:
        items = []
        for it in entry.items:
            m = scale_food(it.food, it.servings)
            all_macros.append(m)
            items.append(ItemOut(food_id=it.food_id, name=it.food.name,
                                 servings=round(it.servings, 3), calories=round(m.calories, 1)))
        entries.append(EntryOut(name=entry.name, items=items))
    t = sum_macros(all_macros)
    totals = {"calories": round(t.calories, 1), "protein": round(t.protein, 1),
              "carbs": round(t.carbs, 1), "fat_total": round(t.fat_total, 1)}
    return PlanOut(id=plan.id, name=plan.name, entries=entries, totals=totals)


@router.post("/users/{user_id}/plans/generate", status_code=201, response_model=PlanOut)
def generate_plan(user_id: int, req: GenerateRequest, db: Session = Depends(get_session)) -> PlanOut:
    candidates = FoodRepository(db).list_all()
    try:
        draft = build_day_plan(req.target_calories, candidates, req.meals, req.foods_per_meal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    plan = PlanRepository(db).save_draft(user_id=user_id, name="Generated plan", draft=draft)
    db.commit()
    db.refresh(plan)
    return _plan_out(plan)


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: int, db: Session = Depends(get_session)) -> PlanOut:
    plan = PlanRepository(db).get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="not found")
    return _plan_out(plan)
```

- [ ] **Step 4: Register the router in main.py**

Add to `backend/app/main.py`: `from app.api.plans import router as plans_router` and `app.include_router(plans_router)`.

- [ ] **Step 5: Run the test + full suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/plans.py backend/app/main.py backend/tests/api/test_plans_api.py
git commit -m "feat(api): generate + retrieve day plans with macro totals"
```

---

### Task 6: Food logging API + day summary

**Files:**
- Create: `backend/app/api/logs.py`
- Modify: `backend/app/main.py` (include logs router)
- Test: `backend/tests/api/test_logs_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_logs_api.py
import pytest
from fastapi.testclient import TestClient
from app.db import Base, new_engine, new_session_factory, get_session
from app.main import app
from app.models import User, Food


@pytest.fixture
def client():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestingSession = new_session_factory(engine)
    with TestingSession() as s:
        s.add(User(name="K", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate"))
        s.add(Food(name="Egg", serving_description="1", calories=78, protein=6))
        s.commit()

    def override():
        with TestingSession() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_log_food_and_day_summary(client):
    r = client.post("/users/1/log", json={"food_id": 1, "servings": 2})
    assert r.status_code == 201

    s = client.get("/users/1/log/today")
    assert s.status_code == 200
    body = s.json()
    assert body["totals"]["calories"] == pytest.approx(156)  # 78 * 2
    assert len(body["entries"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_logs_api.py -v`
Expected: FAIL (logs router missing).

- [ ] **Step 3: Implement the logs router**

```python
# backend/app/api/logs.py
import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.repositories import LogRepository
from app.core.macros import scale_food, sum_macros

router = APIRouter(tags=["logs"])


class LogRequest(BaseModel):
    food_id: int
    servings: float = 1.0
    source: str = "manual"


class LogItemOut(BaseModel):
    food_id: int
    name: str
    servings: float
    calories: float


class DaySummary(BaseModel):
    day: datetime.date
    entries: list[LogItemOut]
    totals: dict


@router.post("/users/{user_id}/log", status_code=201)
def log_food(user_id: int, req: LogRequest, db: Session = Depends(get_session)) -> dict:
    entry = LogRepository(db).add(user_id=user_id, food_id=req.food_id,
                                  servings=req.servings, source=req.source)
    db.commit()
    return {"id": entry.id}


@router.get("/users/{user_id}/log/today", response_model=DaySummary)
def day_summary(user_id: int, db: Session = Depends(get_session)) -> DaySummary:
    today = datetime.date.today()
    entries = LogRepository(db).for_day(user_id, today)
    items, macros = [], []
    for e in entries:
        m = scale_food(e.food, e.servings)
        macros.append(m)
        items.append(LogItemOut(food_id=e.food_id, name=e.food.name,
                                servings=e.servings, calories=round(m.calories, 1)))
    t = sum_macros(macros)
    totals = {"calories": round(t.calories, 1), "protein": round(t.protein, 1),
              "carbs": round(t.carbs, 1), "fat_total": round(t.fat_total, 1)}
    return DaySummary(day=today, entries=items, totals=totals)
```

- [ ] **Step 4: Register the router in main.py**

Add to `backend/app/main.py`: `from app.api.logs import router as logs_router` and `app.include_router(logs_router)`.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/logs.py backend/app/main.py backend/tests/api/test_logs_api.py
git commit -m "feat(api): food logging + today summary"
```

---

## Done when

- `cd backend && uv run pytest` is green.
- `POST /users/{id}/plans/generate` builds a calorie-accurate plan from the food library, persists it, and returns macro totals; `GET /plans/{id}` retrieves it.
- `POST /users/{id}/log` records eaten food; `GET /users/{id}/log/today` returns the day's entries + macro totals.

## Out of scope (later plans)

- LLM-driven food selection / smarter builder (the agent will call `build_day_plan` and refine) — Plan 5
- LangGraph + Gemini agent — Plan 5
- Frontend — Plan 6
