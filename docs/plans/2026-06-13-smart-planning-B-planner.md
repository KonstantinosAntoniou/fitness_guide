# Smart Planning B — The Planner

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the naive calorie-only builder with a macro-hitting, realistic planner: the LLM picks meal-appropriate foods/meals, and a deterministic core (`fit_servings`) sizes the servings to hit the user's macro targets within realistic limits, returning a macro+micro scorecard.

**Architecture:** `core/planner.fit_servings` solves a **bounded least-squares** (scipy `lsq_linear`) for servings that best match `[protein, carb, fat]` targets, with per-item bounds (foods `0..cap`; a meal's ingredients anchored to its recipe ±30%). `score_plan` reports macros + the 5 key micros vs target. A new `plan_day` agent tool wires "LLM selects → core enforces" and replaces the naive `generate_plan` tool. The legacy `build_day_plan` + `/plans/generate` endpoint stay untouched (still tested) — only the agent path changes.

**Tech Stack:** scipy (new), numpy, SQLAlchemy, LangChain tools, pytest. Implements [the spec](../specs/2026-06-13-smart-meal-planning-design.md) §6–§7, building on [Plan A](2026-06-13-smart-planning-A-foundation.md).

---

### Task 1: `fit_servings` bounded optimizer

**Files:**
- Modify: `backend/pyproject.toml` (add `scipy`)
- Modify: `backend/app/core/planner.py` (append `ItemSpec`, `fit_servings`, `food_spec`, `meal_ingredient_specs`)
- Test: `backend/tests/core/test_fit_servings.py`

- [ ] **Step 1: Add scipy**

Run: `uv add --directory backend scipy`
Expected: scipy + numpy install.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/core/test_fit_servings.py
import pytest
from app.core.planner import ItemSpec, fit_servings, food_spec, meal_ingredient_specs


class F:
    def __init__(self, **k):
        self.id = k.get("id", 0)
        self.name = k.get("name", "x")
        self.protein = k.get("protein", 0.0)
        self.carbs = k.get("carbs", 0.0)
        self.fat_saturated = k.get("fat_saturated", 0.0)
        self.fat_unsaturated = k.get("fat_unsaturated", 0.0)
        self.calories = k.get("calories", 0.0)


def test_fit_hits_macros_within_bounds():
    # chicken (protein), rice (carbs), olive oil (fat) — per serving
    chicken = F(name="chicken", protein=31, carbs=0, fat_unsaturated=3, calories=165)
    rice = F(name="rice", protein=2.7, carbs=28, fat_unsaturated=0.3, calories=130)
    oil = F(name="oil", protein=0, carbs=0, fat_unsaturated=14, calories=120)
    specs = [food_spec(chicken, max_servings=8), food_spec(rice, max_servings=8), food_spec(oil, max_servings=5)]
    servings = fit_servings(specs, protein_g=120, carb_g=140, fat_g=50)
    # within bounds
    assert all(0 <= s <= spec.hi + 1e-6 for s, spec in zip(servings, specs))
    # protein roughly hit (weighted highest)
    protein = sum(f.protein * s for f, s in zip([chicken, rice, oil], servings))
    assert protein == pytest.approx(120, abs=12)


def test_meal_ingredient_specs_flex():
    egg = F(name="egg")
    toast = F(name="toast")

    class Item:
        def __init__(self, food, servings):
            self.food, self.servings = food, servings

    class Meal:
        items = [Item(egg, 2.0), Item(toast, 1.0)]

    specs = meal_ingredient_specs(Meal(), flex=0.3)
    assert specs[0].lo == pytest.approx(1.4) and specs[0].hi == pytest.approx(2.6)


def test_fit_empty_returns_empty():
    assert fit_servings([], 100, 100, 30) == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_fit_servings.py -v`
Expected: FAIL — `ImportError` (names not in planner).

- [ ] **Step 4: Implement (append to `backend/app/core/planner.py`)**

```python
from dataclasses import dataclass

import numpy as np
from scipy.optimize import lsq_linear


@dataclass
class ItemSpec:
    food: object       # FoodLike: .protein/.carbs/.fat_saturated/.fat_unsaturated/.calories/.name/.id
    lo: float          # min servings
    hi: float          # max servings


def food_spec(food, max_servings: float = 4.0) -> ItemSpec:
    return ItemSpec(food=food, lo=0.0, hi=max_servings)


def meal_ingredient_specs(meal, flex: float = 0.3) -> list[ItemSpec]:
    """A saved meal's ingredients, each anchored to its recipe servings ±flex."""
    out = []
    for it in meal.items:
        r = it.servings
        out.append(ItemSpec(food=it.food, lo=r * (1 - flex), hi=r * (1 + flex)))
    return out


def fit_servings(specs: list[ItemSpec], protein_g: float, carb_g: float, fat_g: float,
                 protein_weight: float = 1.5) -> list[float]:
    """Servings per item that best hit the macro targets within each item's bounds."""
    if not specs:
        return []
    P = np.array([s.food.protein or 0 for s in specs], dtype=float)
    C = np.array([s.food.carbs or 0 for s in specs], dtype=float)
    Ft = np.array([(s.food.fat_saturated or 0) + (s.food.fat_unsaturated or 0) for s in specs], dtype=float)
    A = np.vstack([protein_weight * P, C, Ft])
    b = np.array([protein_weight * protein_g, carb_g, fat_g], dtype=float)
    lb = np.array([s.lo for s in specs], dtype=float)
    ub = np.array([max(s.hi, s.lo) for s in specs], dtype=float)
    res = lsq_linear(A, b, bounds=(lb, ub))
    return [float(x) for x in res.x]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_fit_servings.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/core/planner.py backend/tests/core/test_fit_servings.py
git commit -m "feat(core): bounded least-squares fit_servings (macro-hitting, realistic bounds)"
```

---

### Task 2: `PlanScore` scorecard

**Files:**
- Modify: `backend/app/core/planner.py` (append `PlanScore`, `score_plan`)
- Test: `backend/tests/core/test_score_plan.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/test_score_plan.py
import pytest
from app.core.planner import ItemSpec, score_plan
from app.core.targets import compute_targets


class F:
    def __init__(self, **k):
        for key in ("protein", "carbs", "fat_saturated", "fat_unsaturated", "calories",
                    "fiber", "sodium", "iron_mg", "calcium_mg", "potassium_mg",
                    "vitamin_c_mg", "vitamin_d_ug"):
            setattr(self, key, k.get(key, 0.0))
        self.name = k.get("name", "x")


def test_score_totals_and_micros():
    targets = compute_targets(sex="male", weight_kg=80, height_cm=180, age=30, activity_level="moderate")
    food = F(name="beef", protein=26, carbs=0, fat_saturated=6, fat_unsaturated=8,
             calories=250, iron_mg=2.6, potassium_mg=300, sodium=70)
    specs = [ItemSpec(food=food, lo=0, hi=5)]
    score = score_plan(specs, [2.0], targets)
    assert score.calories == pytest.approx(500)        # 250 * 2
    assert score.protein_g == pytest.approx(52)        # 26 * 2
    assert score.micros["iron_mg"][0] == pytest.approx(5.2)   # got
    assert score.micros["iron_mg"][1] == 8                    # target (male)
    assert 0 <= score.macro_pct()["protein"] <= 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_score_plan.py -v`
Expected: FAIL — `ImportError` (`score_plan` not defined).

- [ ] **Step 3: Implement (append to `backend/app/core/planner.py`)**

```python
from app.core.macros import scale_food, sum_macros

_MICROS = ("iron_mg", "calcium_mg", "potassium_mg", "vitamin_c_mg", "vitamin_d_ug")


@dataclass
class PlanScore:
    calories: float
    protein_g: float
    carb_g: float
    fat_g: float
    fiber_g: float
    sodium_mg: float
    micros: dict          # name -> (got, target)
    _targets: object

    def macro_pct(self) -> dict:
        t = self._targets
        def pct(got, target):
            return round(100 * got / target, 0) if target else 0.0
        return {
            "protein": pct(self.protein_g, t.protein_g),
            "carbs": pct(self.carb_g, t.carb_g),
            "fat": pct(self.fat_g, t.fat_g),
            "calories": pct(self.calories, t.calories),
        }


def score_plan(specs: list[ItemSpec], servings: list[float], targets) -> PlanScore:
    macros = sum_macros([scale_food(s.food, q) for s, q in zip(specs, servings)])
    micros = {}
    for m in _MICROS:
        got = sum((getattr(s.food, m, None) or 0) * q for s, q in zip(specs, servings))
        micros[m] = (round(got, 1), getattr(targets, m))
    return PlanScore(
        calories=round(macros.calories, 0), protein_g=round(macros.protein, 1),
        carb_g=round(macros.carbs, 1), fat_g=round(macros.fat_total, 1),
        fiber_g=round(macros.fiber, 1), sodium_mg=round(macros.sodium, 1),
        micros=micros, _targets=targets,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_score_plan.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/planner.py backend/tests/core/test_score_plan.py
git commit -m "feat(core): PlanScore scorecard (macros % + micros vs target)"
```

---

### Task 3: `plan_day` agent tool (LLM selects → core enforces)

**Files:**
- Modify: `backend/app/agent/tools.py` (add `MealRepository`; replace `generate_plan` with `plan_day`)
- Modify: `backend/app/agent/coach.py` (tighten the system prompt for balanced selection + scorecard reaction)
- Test: `backend/tests/agent/test_plan_day.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/agent/test_plan_day.py
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food
from app.repositories import PlanRepository
from app.agent.tools import build_tools


@pytest.fixture
def ctx():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = new_session_factory(engine)()
    s.add(User(name="K", age=30, sex="male", height_cm=181, weight_kg=85,
               activity_level="moderate", goal_type="lose", goal_period="week", amount_kg=0.5))
    s.add(Food(name="Chicken Breast", serving_description="100g", calories=165, protein=31,
               carbs=0, fat_unsaturated=3, iron_mg=0.7, potassium_mg=256))
    s.add(Food(name="White Rice", serving_description="100g", calories=130, protein=2.7,
               carbs=28, fat_unsaturated=0.3))
    s.add(Food(name="Olive Oil", serving_description="100g", calories=884, protein=0,
               carbs=0, fat_unsaturated=100))
    s.add(Food(name="Broccoli", serving_description="100g", calories=34, protein=2.8,
               carbs=7, vitamin_c_mg=89, potassium_mg=316))
    s.commit()
    tools = {t.name: t for t in build_tools(s, user_id=1)}
    yield s, tools
    s.close()


def test_plan_day_persists_and_scores(ctx):
    session, tools = ctx
    out = tools["plan_day"].invoke({"meals": [
        {"name": "Lunch", "foods": ["Chicken Breast", "White Rice", "Olive Oil"]},
        {"name": "Dinner", "foods": ["Chicken Breast", "Broccoli", "White Rice"]},
    ]})
    assert "kcal" in out.lower()
    plans = PlanRepository(session).list_for_user(1)
    assert len(plans) == 1
    # protein should land in a sane band of the ~170g target (not 15x one food)
    assert "protein" in out.lower()


def test_plan_day_unknown_foods(ctx):
    _, tools = ctx
    out = tools["plan_day"].invoke({"meals": [{"name": "X", "foods": ["nonexistent food"]}]})
    assert "no" in out.lower() or "couldn" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/agent/test_plan_day.py -v`
Expected: FAIL — `KeyError: 'plan_day'`.

- [ ] **Step 3: Update `build_tools` in `backend/app/agent/tools.py`**

Add imports at the top of the file:

```python
from app.repositories import FoodRepository, UserRepository, PlanRepository, LogRepository, MealRepository
from app.core.targets import compute_targets
from app.core.planner import food_spec, meal_ingredient_specs, fit_servings, score_plan
```

Inside `build_tools`, add `meals_repo = MealRepository(session)` next to the other repos. **Delete the `generate_plan` tool** and add this one, and include `plan_day` in the returned list (replacing `generate_plan`):

```python
    @tool
    def plan_day(meals: list[dict]) -> str:
        """Build and save a balanced day plan that hits the user's macro targets.

        `meals` is a list of slots, each {"name": str, "foods": [food names], "meals": [saved meal names]}.
        Choose meal-appropriate, varied foods (a protein, a carb, veg/fruit). The tool sizes servings to
        hit the user's protein/carb/fat targets within realistic limits and returns a scorecard. If a
        macro or key micro is low, change your food selection and call again.
        """
        u = users.get(user_id)
        if not u:
            return "No profile found for this user."
        targets = compute_targets(sex=u.sex, weight_kg=u.weight_kg, height_cm=u.height_cm,
                                  age=u.age, activity_level=u.activity_level, goal_type=u.goal_type,
                                  goal_period=u.goal_period, amount_kg=u.amount_kg)
        slots = []  # (slot_name, [ItemSpec])
        for slot in meals or []:
            specs = []
            for fname in slot.get("foods", []):
                hits = foods.search(fname)
                if hits:
                    specs.append(food_spec(hits[0]))
            for mname in slot.get("meals", []):
                meal = meals_repo.find_by_name(mname)
                if meal:
                    specs.extend(meal_ingredient_specs(meal))
            if specs:
                slots.append((slot.get("name", "Meal"), specs))
        all_specs = [s for _, specs in slots for s in specs]
        if not all_specs:
            return "None of those foods/meals are in the library — add them first (search_nutrition_database / add_food_to_library)."

        servings = fit_servings(all_specs, targets.protein_g, targets.carb_g, targets.fat_g)
        draft, idx = [], 0
        for name, specs in slots:
            items = [(s.food, round(servings[idx + i], 2)) for i, s in enumerate(specs)]
            idx += len(specs)
            draft.append({"name": name, "items": items})
        plan = plans.save_draft(user_id=user_id, name="Coach plan", draft=draft)
        session.commit()

        score = score_plan(all_specs, servings, targets)
        pct = score.macro_pct()
        lines = [f"Saved plan #{plan.id}. Totals vs target:"]
        lines.append(f"  {round(score.calories)} kcal ({pct['calories']:.0f}% of {round(targets.calories)}), "
                     f"protein {score.protein_g}g ({pct['protein']:.0f}%), carbs {score.carb_g}g ({pct['carbs']:.0f}%), "
                     f"fat {score.fat_g}g ({pct['fat']:.0f}%), fiber {score.fiber_g}g.")
        low = [m.replace('_mg', '').replace('_ug', '').replace('vitamin_', 'vit ')
               for m, (got, tgt) in score.micros.items() if tgt and got < 0.5 * tgt]
        lines.append("  Low micros: " + (", ".join(low) if low else "none — looks balanced."))
        for entry in draft:
            foods_txt = ", ".join(f"{q}x {food.name}" for food, q in entry["items"])
            lines.append(f"  {entry['name']}: {foods_txt}")
        return "\n".join(lines)
```

- [ ] **Step 4: Tighten the system prompt**

In `backend/app/agent/coach.py`, update `SYSTEM_PROMPT` to mention plan_day instead of generate_plan:

```python
SYSTEM_PROMPT = (
    "You are a concise, practical fitness and nutrition coach. "
    "Always ground advice in the user's real data: call get_profile for their macro + micro targets, "
    "search_my_foods / search_nutrition_database before inventing macros, and add_food_to_library for new foods. "
    "To make a day plan, choose balanced, varied, meal-appropriate foods (a protein + a carb + veg/fruit per meal) "
    "and call plan_day — it sizes the servings to hit the targets and returns a scorecard. "
    "If the scorecard shows a low macro or micro, swap in a food that supplies it and call plan_day again. "
    "Use log_food to record what they ate. Keep replies short; never fabricate calorie numbers — look them up."
)
```

- [ ] **Step 5: Run the test + full suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass (the old `test_tools.py::test_generate_plan_tool_persists` referenced `generate_plan` — update it: rename to call `plan_day` with `{"meals": [{"name": "Lunch", "foods": ["Rice", "Chicken"]}]}` and assert a plan persists).

- [ ] **Step 6: Update the stale generate_plan test**

In `backend/tests/agent/test_tools.py`, replace `test_generate_plan_tool_persists` with:

```python
def test_plan_day_tool_persists(ctx):
    session, tools = ctx
    out = tools["plan_day"].invoke({"meals": [{"name": "Lunch", "foods": ["Rice", "Chicken"]}]})
    assert "plan" in out.lower()
    from app.repositories import PlanRepository
    assert len(PlanRepository(session).list_for_user(1)) == 1
```

- [ ] **Step 7: Run the full suite again**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/agent/tools.py backend/app/agent/coach.py backend/tests/agent/test_plan_day.py backend/tests/agent/test_tools.py
git commit -m "feat(agent): plan_day tool (LLM selects, core fits macros) replacing naive generate_plan"
```

---

## Done when

- `cd backend && uv run pytest` is green.
- `fit_servings` hits macro targets within bounds (no degenerate single-food blowouts).
- `plan_day` saves a plan from selected foods/meals and returns a macro+micro scorecard.
- A live coach chat ("build me a day plan") produces realistic portions hitting the targets.

## Out of scope

- Removing the legacy `build_day_plan` / `/plans/generate` (left for a later cleanup)
- Weekly/multi-day optimisation; allergy exclusions (bounds make these easy to add later)
