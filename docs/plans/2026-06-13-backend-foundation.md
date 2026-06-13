# Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Python/FastAPI backend skeleton with a pure, fully-tested `core/` domain layer for profile energy math (BMR, TDEE, goal targets, BMI), exposed through a running API.

**Architecture:** A `uv`-managed FastAPI app. All nutrition/energy math lives in `app/core/` as pure functions with zero framework or I/O dependencies (the must-be-correct code, unit-tested against known formula values). `app/api/` is a thin HTTP layer that composes the core functions. No database or external services yet — those arrive in later plans.

**Tech Stack:** Python ≥3.12, uv, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, pytest, httpx (TestClient).

This plan implements the foundation portion of [the rebuild spec](../specs/2026-06-13-fitness-coach-rebuild-design.md) (§5 architecture, §6 User calculations).

---

### Task 1: Scaffold the uv project

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`, `backend/app/core/__init__.py`, `backend/app/api/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/.gitignore`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "fitness-backend"
version = "0.1.0"
description = "AI fitness coach backend"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "httpx>=0.28",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create package directories and `__init__.py` files**

Create empty files: `backend/app/__init__.py`, `backend/app/core/__init__.py`, `backend/app/api/__init__.py`, `backend/tests/__init__.py`.

- [ ] **Step 3: Create `backend/.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
*.db
```

- [ ] **Step 4: Sync the environment**

Run: `cd backend && uv sync`
Expected: creates `backend/.venv` and `backend/uv.lock`, installs FastAPI + dev deps. No errors.

- [ ] **Step 5: Verify the toolchain**

Run: `cd backend && uv run python -c "import fastapi, pydantic_settings; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app backend/tests backend/.gitignore
git commit -m "chore(backend): scaffold uv + FastAPI project structure"
```

---

### Task 2: Settings via pydantic-settings

**Files:**
- Create: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_config.py
from app.config import Settings


def test_defaults_are_local_friendly():
    s = Settings(_env_file=None)
    assert s.database_url == "sqlite:///./fitness.db"
    assert s.llm_provider == "google"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    s = Settings(_env_file=None)
    assert s.database_url == "postgresql://x/y"
    assert s.llm_provider == "openai"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./fitness.db"
    # LLM: "google" (Gemini via LangChain) | "openai"
    llm_provider: str = "google"


settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(backend): env-driven settings (SQLite + provider defaults)"
```

---

### Task 3: BMR — Mifflin-St Jeor & Harris-Benedict

**Files:**
- Create: `backend/app/core/energy.py`
- Test: `backend/tests/core/test_energy.py`
- Create: `backend/tests/core/__init__.py`

Formulas (weight kg, height cm, age years):
- **Mifflin-St Jeor:** `10*w + 6.25*h - 5*age + (5 if male else -161)`
- **Harris-Benedict (Roza-Shizgal 1984 revision):**
  - male: `88.362 + 13.397*w + 4.799*h - 5.677*age`
  - female: `447.593 + 9.247*w + 3.098*h - 4.330*age`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/test_energy.py
import pytest
from app.core.energy import mifflin_st_jeor, harris_benedict


def test_mifflin_male():
    # 10*80 + 6.25*180 - 5*30 + 5 = 1780.0
    assert mifflin_st_jeor("male", 80, 180, 30) == pytest.approx(1780.0)


def test_mifflin_female():
    # 10*65 + 6.25*165 - 5*28 - 161 = 1380.25
    assert mifflin_st_jeor("female", 65, 165, 28) == pytest.approx(1380.25)


def test_harris_benedict_male():
    assert harris_benedict("male", 80, 180, 30) == pytest.approx(1853.632)


def test_harris_benedict_female():
    assert harris_benedict("female", 65, 165, 28) == pytest.approx(1438.578)


def test_invalid_sex_raises():
    with pytest.raises(ValueError):
        mifflin_st_jeor("other", 80, 180, 30)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_energy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.energy'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/core/energy.py
"""Pure energy-expenditure math. No I/O, no frameworks."""
from typing import Literal

Sex = Literal["male", "female"]


def _check_sex(sex: str) -> None:
    if sex not in ("male", "female"):
        raise ValueError(f"sex must be 'male' or 'female', got {sex!r}")


def mifflin_st_jeor(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    _check_sex(sex)
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + (5 if sex == "male" else -161)


def harris_benedict(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    _check_sex(sex)
    if sex == "male":
        return 88.362 + 13.397 * weight_kg + 4.799 * height_cm - 5.677 * age
    return 447.593 + 9.247 * weight_kg + 3.098 * height_cm - 4.330 * age
```

(Also create empty `backend/tests/core/__init__.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_energy.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/energy.py backend/tests/core/
git commit -m "feat(core): BMR via Mifflin-St Jeor and Harris-Benedict"
```

---

### Task 4: TDEE from activity level

**Files:**
- Modify: `backend/app/core/energy.py`
- Modify: `backend/tests/core/test_energy.py`

- [ ] **Step 1: Add the failing test**

```python
# append to backend/tests/core/test_energy.py
from app.core.energy import tdee, ACTIVITY_MULTIPLIERS


def test_tdee_moderate():
    # 1780.0 * 1.55 = 2759.0
    assert tdee(1780.0, "moderate") == pytest.approx(2759.0)


def test_activity_levels_present():
    assert set(ACTIVITY_MULTIPLIERS) == {
        "sedentary", "light", "moderate", "active", "very_active"
    }


def test_tdee_invalid_level_raises():
    with pytest.raises(ValueError):
        tdee(1780.0, "couch")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_energy.py -k tdee -v`
Expected: FAIL with `ImportError: cannot import name 'tdee'`.

- [ ] **Step 3: Add the implementation**

```python
# append to backend/app/core/energy.py
ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


def tdee(bmr: float, activity_level: str) -> float:
    if activity_level not in ACTIVITY_MULTIPLIERS:
        raise ValueError(f"unknown activity_level: {activity_level!r}")
    return bmr * ACTIVITY_MULTIPLIERS[activity_level]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_energy.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/energy.py backend/tests/core/test_energy.py
git commit -m "feat(core): TDEE from BMR and activity level"
```

---

### Task 5: Goal-based target calories

**Files:**
- Create: `backend/app/core/goals.py`
- Test: `backend/tests/core/test_goals.py`

Model: 1 kg body mass ≈ 7700 kcal. Daily delta = `amount_kg * 7700 / period_days`. Lose → subtract from TDEE; gain → add. No goal → return TDEE (maintenance).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/test_goals.py
import pytest
from app.core.goals import target_calories, PERIOD_DAYS, KCAL_PER_KG


def test_constants():
    assert KCAL_PER_KG == 7700
    assert PERIOD_DAYS == {"week": 7, "month": 30, "year": 365}


def test_lose_half_kg_per_week():
    # delta/day = 0.5 * 7700 / 7 = 550 ; 2759 - 550 = 2209
    assert target_calories(2759.0, "lose", "week", 0.5) == pytest.approx(2209.0)


def test_gain_per_month():
    # delta/day = 2 * 7700 / 30 = 513.333... ; 2759 + 513.333 = 3272.333
    assert target_calories(2759.0, "gain", "month", 2.0) == pytest.approx(3272.3333, abs=1e-3)


def test_no_goal_is_maintenance():
    assert target_calories(2759.0, None, None, None) == pytest.approx(2759.0)


def test_invalid_period_raises():
    with pytest.raises(ValueError):
        target_calories(2759.0, "lose", "fortnight", 0.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_goals.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.goals'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/core/goals.py
"""Translate a weight goal into a daily calorie target."""
from typing import Literal, Optional

KCAL_PER_KG = 7700
PERIOD_DAYS = {"week": 7, "month": 30, "year": 365}

GoalType = Literal["lose", "gain"]
GoalPeriod = Literal["week", "month", "year"]


def target_calories(
    tdee: float,
    goal_type: Optional[GoalType],
    goal_period: Optional[GoalPeriod],
    amount_kg: Optional[float],
) -> float:
    if not goal_type or amount_kg is None:
        return tdee
    if goal_period not in PERIOD_DAYS:
        raise ValueError(f"unknown goal_period: {goal_period!r}")
    delta_per_day = amount_kg * KCAL_PER_KG / PERIOD_DAYS[goal_period]
    if goal_type == "lose":
        return tdee - delta_per_day
    if goal_type == "gain":
        return tdee + delta_per_day
    raise ValueError(f"unknown goal_type: {goal_type!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_goals.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/goals.py backend/tests/core/test_goals.py
git commit -m "feat(core): goal-based daily calorie target"
```

---

### Task 6: BMI and category

**Files:**
- Create: `backend/app/core/body.py`
- Test: `backend/tests/core/test_body.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/test_body.py
import pytest
from app.core.body import bmi, bmi_category


def test_bmi():
    # 80 / (1.8^2) = 24.691...
    assert bmi(80, 180) == pytest.approx(24.6914, abs=1e-3)


@pytest.mark.parametrize("value,expected", [
    (17.0, "underweight"),
    (22.0, "normal"),
    (27.0, "overweight"),
    (32.0, "obese"),
])
def test_bmi_category(value, expected):
    assert bmi_category(value) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_body.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.body'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/core/body.py
"""Body-composition helpers."""


def bmi(weight_kg: float, height_cm: float) -> float:
    height_m = height_cm / 100
    return weight_kg / (height_m ** 2)


def bmi_category(value: float) -> str:
    if value < 18.5:
        return "underweight"
    if value < 25:
        return "normal"
    if value < 30:
        return "overweight"
    return "obese"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_body.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/body.py backend/tests/core/test_body.py
git commit -m "feat(core): BMI and category"
```

---

### Task 7: FastAPI app — health + profile metrics endpoint

**Files:**
- Create: `backend/app/core/profile.py` (composes the calculators into one result)
- Create: `backend/app/api/profile.py` (request/response schemas + route)
- Create: `backend/app/main.py`
- Test: `backend/tests/core/test_profile.py`
- Test: `backend/tests/api/test_api.py`
- Create: `backend/tests/api/__init__.py`

- [ ] **Step 1: Write the failing core test**

```python
# backend/tests/core/test_profile.py
import pytest
from app.core.profile import compute_metrics


def test_compute_metrics_male_moderate_lose():
    m = compute_metrics(
        sex="male", weight_kg=80, height_cm=180, age=30,
        activity_level="moderate",
        goal_type="lose", goal_period="week", amount_kg=0.5,
    )
    assert m["bmr_msj"] == pytest.approx(1780.0)
    assert m["bmr_hb"] == pytest.approx(1853.632)
    assert m["tdee_msj"] == pytest.approx(2759.0)
    assert m["bmi"] == pytest.approx(24.6914, abs=1e-3)
    assert m["bmi_category"] == "normal"
    # target uses Mifflin TDEE: 2759 - 550 = 2209
    assert m["target_calories"] == pytest.approx(2209.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.profile'`.

- [ ] **Step 3: Implement the composer**

```python
# backend/app/core/profile.py
"""Compose energy/body math into a single profile metrics result."""
from typing import Optional

from app.core.energy import mifflin_st_jeor, harris_benedict, tdee
from app.core.goals import target_calories
from app.core.body import bmi, bmi_category


def compute_metrics(
    *, sex: str, weight_kg: float, height_cm: float, age: int,
    activity_level: str,
    goal_type: Optional[str] = None,
    goal_period: Optional[str] = None,
    amount_kg: Optional[float] = None,
) -> dict:
    bmr_msj = mifflin_st_jeor(sex, weight_kg, height_cm, age)
    bmr_hb = harris_benedict(sex, weight_kg, height_cm, age)
    tdee_msj = tdee(bmr_msj, activity_level)
    tdee_hb = tdee(bmr_hb, activity_level)
    body_bmi = bmi(weight_kg, height_cm)
    return {
        "bmr_msj": bmr_msj,
        "bmr_hb": bmr_hb,
        "tdee_msj": tdee_msj,
        "tdee_hb": tdee_hb,
        "bmi": body_bmi,
        "bmi_category": bmi_category(body_bmi),
        "target_calories": target_calories(tdee_msj, goal_type, goal_period, amount_kg),
    }
```

- [ ] **Step 4: Run core test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_profile.py -v`
Expected: 1 passed.

- [ ] **Step 5: Write the failing API test**

```python
# backend/tests/api/test_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_profile_metrics():
    r = client.post("/profile/metrics", json={
        "sex": "male", "weight_kg": 80, "height_cm": 180, "age": 30,
        "activity_level": "moderate",
        "goal_type": "lose", "goal_period": "week", "amount_kg": 0.5,
    })
    assert r.status_code == 200
    body = r.json()
    assert round(body["target_calories"]) == 2209
    assert body["bmi_category"] == "normal"


def test_profile_metrics_validation_error():
    r = client.post("/profile/metrics", json={"sex": "male"})
    assert r.status_code == 422
```

(Also create empty `backend/tests/api/__init__.py`.)

- [ ] **Step 6: Run API test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 7: Implement the API layer and app**

```python
# backend/app/api/profile.py
from typing import Literal, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.core.profile import compute_metrics

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileInput(BaseModel):
    sex: Literal["male", "female"]
    weight_kg: float
    height_cm: float
    age: int
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"]
    goal_type: Optional[Literal["lose", "gain"]] = None
    goal_period: Optional[Literal["week", "month", "year"]] = None
    amount_kg: Optional[float] = None


class MetricsOutput(BaseModel):
    bmr_msj: float
    bmr_hb: float
    tdee_msj: float
    tdee_hb: float
    bmi: float
    bmi_category: str
    target_calories: float


@router.post("/metrics", response_model=MetricsOutput)
def profile_metrics(payload: ProfileInput) -> MetricsOutput:
    return MetricsOutput(**compute_metrics(**payload.model_dump()))
```

```python
# backend/app/main.py
from fastapi import FastAPI
from app.api.profile import router as profile_router

app = FastAPI(title="Fitness Coach API")
app.include_router(profile_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 8: Run the full suite to verify everything passes**

Run: `cd backend && uv run pytest -v`
Expected: all tests pass (config, energy, goals, body, profile, api).

- [ ] **Step 9: Smoke-test the running server**

Run: `cd backend && uv run uvicorn app.main:app --port 8000 &` then `sleep 2 && curl -s localhost:8000/health` then kill the server.
Expected: `{"status":"ok"}`.

- [ ] **Step 10: Commit**

```bash
git add backend/app/core/profile.py backend/app/api/profile.py backend/app/main.py backend/tests/core/test_profile.py backend/tests/api/
git commit -m "feat(api): health check + profile metrics endpoint"
```

---

## Done when

- `cd backend && uv run pytest` is green across all modules.
- `GET /health` returns `{"status": "ok"}` and `POST /profile/metrics` returns correct computed metrics.
- All energy/goal/body math is covered by unit tests asserting known formula values.

## Out of scope (later plans)

- Database, ORM models, repositories (Plan 2)
- Persisting users (Plan 2)
- Nutrition API, foods, meals, plan builder, agent, frontend (Plans 3-6)
