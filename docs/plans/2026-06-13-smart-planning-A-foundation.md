# Smart Planning A — Targets + Rich Data Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lay the foundation for nutritionally-sound planning — real macro + soft micro **targets**, a **Food** schema that stores key micros, a **USDA FoodData Central** provider, and a **~150-food rich seed** so the planner (Plan B) has good data to work with.

**Architecture:** Pure target math in `core/targets.py`. `Food` gains nullable per-serving micro columns (additive migration). A `USDAProvider` mirrors the existing `OpenFoodFactsProvider` but returns an expanded `NutritionResult` carrying micros. A committed `staples.json` (generated once from USDA) seeds the DB with no runtime key needed.

**Units (standardised):** kcal; **grams** for protein/carbs/fat/fiber/sugar; **mg** for sodium/calcium/iron/potassium/vitamin C; **µg** for vitamin D. (Open Food Facts gives sodium in grams → convert ×1000.)

**Tech Stack:** SQLAlchemy, httpx, Pydantic v2, pytest. Implements [the spec](../specs/2026-06-13-smart-meal-planning-design.md) §3–§5.

---

### Task 1: Nutrition targets (`core/targets.py`)

**Files:**
- Create: `backend/app/core/targets.py`
- Test: `backend/tests/core/test_targets.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/core/test_targets.py
import pytest
from app.core.targets import compute_targets, NutritionTargets


def test_targets_male_lose():
    t = compute_targets(sex="male", weight_kg=85, height_cm=181, age=30,
                        activity_level="moderate", goal_type="lose",
                        goal_period="week", amount_kg=0.5)
    assert isinstance(t, NutritionTargets)
    assert t.calories == pytest.approx(2296.19, abs=0.5)
    assert t.protein_g == pytest.approx(170.0)          # 2.0 g/kg
    assert t.fat_g == pytest.approx(68.0)               # max(25% kcal/9, 0.8 g/kg) -> 68
    assert t.carb_g == pytest.approx(251.05, abs=0.5)   # remainder
    assert t.fiber_g == pytest.approx(32.15, abs=0.1)   # 14 g / 1000 kcal
    assert t.sodium_mg_max == 2300
    # male RDAs
    assert (t.iron_mg, t.calcium_mg, t.potassium_mg, t.vitamin_c_mg, t.vitamin_d_ug) == (8, 1000, 3400, 90, 15)


def test_targets_female_maintain_micros():
    t = compute_targets(sex="female", weight_kg=60, height_cm=165, age=30,
                        activity_level="light")
    assert t.protein_g == pytest.approx(96.0)           # 1.6 g/kg, no goal -> maintain
    assert (t.iron_mg, t.potassium_mg, t.vitamin_c_mg) == (18, 2600, 75)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/test_targets.py -v`
Expected: FAIL — `ModuleNotFoundError: app.core.targets`.

- [ ] **Step 3: Implement**

```python
# backend/app/core/targets.py
"""Turn a profile into concrete daily macro + soft micro targets. Pure."""
from dataclasses import dataclass
from typing import Optional
from app.core.energy import mifflin_st_jeor, tdee
from app.core.goals import target_calories

PROTEIN_G_PER_KG = {"lose": 2.0, "maintain": 1.6, "gain": 1.8}
_RDA = {
    "male": dict(iron_mg=8, calcium_mg=1000, potassium_mg=3400, vitamin_c_mg=90, vitamin_d_ug=15),
    "female": dict(iron_mg=18, calcium_mg=1000, potassium_mg=2600, vitamin_c_mg=75, vitamin_d_ug=15),
}


@dataclass
class NutritionTargets:
    calories: float
    protein_g: float
    carb_g: float
    fat_g: float
    fiber_g: float
    sodium_mg_max: float
    sat_fat_g_max: float
    sugar_g_max: float
    iron_mg: float
    calcium_mg: float
    potassium_mg: float
    vitamin_c_mg: float
    vitamin_d_ug: float


def compute_targets(*, sex: str, weight_kg: float, height_cm: float, age: int,
                    activity_level: str, goal_type: Optional[str] = None,
                    goal_period: Optional[str] = None,
                    amount_kg: Optional[float] = None) -> NutritionTargets:
    cals = target_calories(tdee(mifflin_st_jeor(sex, weight_kg, height_cm, age), activity_level),
                           goal_type, goal_period, amount_kg)
    goal_key = goal_type if goal_type in PROTEIN_G_PER_KG else "maintain"
    protein_g = PROTEIN_G_PER_KG[goal_key] * weight_kg
    fat_g = max(0.25 * cals / 9, 0.8 * weight_kg)
    carb_g = max(0.0, (cals - protein_g * 4 - fat_g * 9) / 4)
    rda = _RDA["male" if sex == "male" else "female"]
    return NutritionTargets(
        calories=cals, protein_g=protein_g, carb_g=carb_g, fat_g=fat_g,
        fiber_g=14 * cals / 1000, sodium_mg_max=2300,
        sat_fat_g_max=0.10 * cals / 9, sugar_g_max=0.10 * cals / 4, **rda,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/test_targets.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/targets.py backend/tests/core/test_targets.py
git commit -m "feat(core): macro + soft micronutrient targets"
```

---

### Task 2: Food micronutrient columns + additive migration

**Files:**
- Modify: `backend/app/models.py` (add 6 nullable micro columns to `Food`)
- Create: `backend/app/migration/schema_upgrade.py`
- Test: `backend/tests/migration/test_schema_upgrade.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/migration/test_schema_upgrade.py
import pytest
from sqlalchemy import text
from app.db import Base, new_engine, new_session_factory
from app.models import Food
from app.migration.schema_upgrade import ensure_food_micro_columns


def test_food_has_micro_fields():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        f = Food(name="Spinach", calories=23, iron_mg=2.7, calcium_mg=99,
                 potassium_mg=558, vitamin_c_mg=28, vitamin_d_ug=0, sugar_g=0.4)
        s.add(f)
        s.commit()
        assert f.iron_mg == 2.7 and f.potassium_mg == 558


def test_ensure_columns_idempotent_on_old_table():
    # simulate an old DB whose `foods` table predates the micro columns
    engine = new_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE foods (id INTEGER PRIMARY KEY, name VARCHAR, calories FLOAT)"))
    ensure_food_micro_columns(engine)
    ensure_food_micro_columns(engine)  # second run must not error
    with engine.begin() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(foods)"))}
    assert {"iron_mg", "calcium_mg", "potassium_mg", "vitamin_c_mg", "vitamin_d_ug", "sugar_g"} <= cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/migration/test_schema_upgrade.py -v`
Expected: FAIL — `TypeError`/`ImportError` (Food has no `iron_mg`; module missing).

- [ ] **Step 3: Add columns to `Food`**

In `backend/app/models.py`, add these fields to the `Food` class (after `sodium`):

```python
    sugar_g: Mapped[Optional[float]] = mapped_column(default=None)
    iron_mg: Mapped[Optional[float]] = mapped_column(default=None)
    calcium_mg: Mapped[Optional[float]] = mapped_column(default=None)
    potassium_mg: Mapped[Optional[float]] = mapped_column(default=None)
    vitamin_c_mg: Mapped[Optional[float]] = mapped_column(default=None)
    vitamin_d_ug: Mapped[Optional[float]] = mapped_column(default=None)
```

- [ ] **Step 4: Implement the additive migration**

```python
# backend/app/migration/schema_upgrade.py
"""Idempotent additive schema upgrades for the existing SQLite dev DB."""
from sqlalchemy import text
from sqlalchemy.engine import Engine

_FOOD_MICRO_COLUMNS = {
    "sugar_g": "FLOAT", "iron_mg": "FLOAT", "calcium_mg": "FLOAT",
    "potassium_mg": "FLOAT", "vitamin_c_mg": "FLOAT", "vitamin_d_ug": "FLOAT",
}


def ensure_food_micro_columns(engine: Engine) -> None:
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(foods)"))}
        for name, sqltype in _FOOD_MICRO_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE foods ADD COLUMN {name} {sqltype}"))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/migration/test_schema_upgrade.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/migration/schema_upgrade.py backend/tests/migration/test_schema_upgrade.py
git commit -m "feat(models): Food micronutrient columns + additive migration"
```

---

### Task 3: Expand NutritionResult + fix Open Food Facts units

**Files:**
- Modify: `backend/app/integrations/nutrition.py` (micro fields + sodium→mg)
- Modify: `backend/tests/integrations/test_normalize.py`

- [ ] **Step 1: Update the normalization test**

Replace `backend/tests/integrations/test_normalize.py` with:

```python
import pytest
from app.integrations.nutrition import parse_off_product, NutritionResult

SAMPLE = {
    "code": "3017620422003", "product_name": "Nutella", "brands": "Ferrero",
    "nutriments": {
        "energy-kcal_100g": 539, "proteins_100g": 6.3, "carbohydrates_100g": 57.5,
        "sugars_100g": 56.3, "fat_100g": 30.9, "saturated-fat_100g": 10.6,
        "fiber_100g": 0, "sodium_100g": 0.0428,  # grams in OFF
    },
}


def test_parse_off_product_macros_and_sugar():
    r = parse_off_product(SAMPLE)
    assert isinstance(r, NutritionResult)
    assert r.calories == 539
    assert r.fat_unsaturated == pytest.approx(20.3)
    assert r.sugar_g == pytest.approx(56.3)
    assert r.sodium == pytest.approx(42.8)   # 0.0428 g -> 42.8 mg


def test_parse_off_product_micros_default_none_when_absent():
    r = parse_off_product({"product_name": "X", "nutriments": {}})
    assert r.iron_mg is None and r.calcium_mg is None and r.sugar_g is None


def test_parse_off_product_clamps_negative_unsaturated():
    r = parse_off_product({"product_name": "X", "nutriments": {"fat_100g": 1, "saturated-fat_100g": 5}})
    assert r.fat_unsaturated == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integrations/test_normalize.py -v`
Expected: FAIL (sugar_g attr missing; sodium still grams).

- [ ] **Step 3: Update `NutritionResult` + `parse_off_product`**

In `backend/app/integrations/nutrition.py`, add the micro fields to `NutritionResult` (after `sodium`):

```python
    sugar_g: Optional[float] = None
    iron_mg: Optional[float] = None
    calcium_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    vitamin_c_mg: Optional[float] = None
    vitamin_d_ug: Optional[float] = None
```

Then replace the `return NutritionResult(...)` in `parse_off_product` with one that adds sugar and converts sodium to mg (OFF has little reliable micro data, so micros stay `None`):

```python
    sugars = n.get("sugars_100g")
    sodium_g = _num(n, "sodium_100g")
    return NutritionResult(
        name=str(product.get("product_name") or "Unknown").strip(),
        brand=str((product.get("brands") or "").split(",")[0]).strip(),
        serving_description="100g", serving_grams=100,
        source="openfoodfacts",
        source_id=str(product["code"]) if product.get("code") else None,
        calories=_num(n, "energy-kcal_100g"), protein=_num(n, "proteins_100g"),
        carbs=_num(n, "carbohydrates_100g"),
        fat_saturated=saturated, fat_unsaturated=max(0.0, fat_total - saturated),
        fiber=float(fiber) if fiber is not None else None,
        sodium=sodium_g * 1000,  # OFF sodium is grams -> store mg
        sugar_g=float(sugars) if sugars is not None else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/integrations/test_normalize.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/nutrition.py backend/tests/integrations/test_normalize.py
git commit -m "feat(integrations): NutritionResult micros + Open Food Facts sodium in mg"
```

---

### Task 4: USDA FoodData Central provider

**Files:**
- Modify: `backend/app/config.py` (add `USDA_API_KEY` to `_SHARED_ENV_KEYS`)
- Create: `backend/app/integrations/usda.py`
- Test: `backend/tests/integrations/test_usda.py`

- [ ] **Step 1: Write the failing test (mocked HTTP)**

```python
# backend/tests/integrations/test_usda.py
import httpx
from app.integrations.usda import USDAProvider, parse_usda_food

# Trimmed real-shape FDC search hit for chicken breast (per 100 g)
FDC = {"foods": [{
    "fdcId": 171077, "description": "Chicken, broiler, breast, raw", "dataType": "SR Legacy",
    "foodNutrients": [
        {"nutrientNumber": "208", "value": 165}, {"nutrientNumber": "203", "value": 31},
        {"nutrientNumber": "205", "value": 0}, {"nutrientNumber": "204", "value": 3.6},
        {"nutrientNumber": "606", "value": 1.0}, {"nutrientNumber": "307", "value": 74},
        {"nutrientNumber": "303", "value": 0.7}, {"nutrientNumber": "306", "value": 256},
        {"nutrientNumber": "401", "value": 0}, {"nutrientNumber": "328", "value": 0.1},
    ],
}]}


def test_parse_usda_food():
    r = parse_usda_food(FDC["foods"][0])
    assert r.name.lower().startswith("chicken")
    assert r.source == "usda" and r.source_id == "171077"
    assert r.calories == 165 and r.protein == 31
    assert r.fat_saturated == 1.0 and r.fat_unsaturated == pytest.approx(2.6)
    assert r.sodium == 74 and r.iron_mg == 0.7 and r.potassium_mg == 256


def test_search_hits_api_and_parses():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=FDC)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=USDAProvider.BASE)
    results = USDAProvider(api_key="k", client=client).search("chicken breast", limit=3)
    assert results[0].calories == 165
    assert "api_key=k" in captured["url"] and "chicken" in captured["url"]
```

(Add `import pytest` at the top.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integrations/test_usda.py -v`
Expected: FAIL — `ModuleNotFoundError: app.integrations.usda`.

- [ ] **Step 3: Implement the provider**

```python
# backend/app/integrations/usda.py
"""USDA FoodData Central provider — rich macros + micros (per 100 g)."""
import os
import httpx
from app.integrations.nutrition import NutritionResult

# legacy SR nutrient numbers
_N = {"kcal": "208", "protein": "203", "carbs": "205", "fat": "204", "sat": "606",
      "sugar": "269", "fiber": "291", "sodium": "307", "calcium": "301", "iron": "303",
      "potassium": "306", "vit_c": "401", "vit_d": "328"}


def parse_usda_food(food: dict) -> NutritionResult:
    vals = {str(n.get("nutrientNumber")): n.get("value") for n in food.get("foodNutrients", [])}

    def num(key):
        v = vals.get(_N[key])
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    fat_total = num("fat") or 0.0
    sat = num("sat") or 0.0
    return NutritionResult(
        name=str(food.get("description") or "Unknown").strip().title(),
        brand=str(food.get("brandOwner") or "").strip(),
        serving_description="100g", serving_grams=100,
        source="usda", source_id=str(food.get("fdcId")) if food.get("fdcId") else None,
        calories=num("kcal") or 0.0, protein=num("protein") or 0.0, carbs=num("carbs") or 0.0,
        fat_saturated=sat, fat_unsaturated=max(0.0, fat_total - sat),
        fiber=num("fiber"), sodium=num("sodium") or 0.0,
        sugar_g=num("sugar"), iron_mg=num("iron"), calcium_mg=num("calcium"),
        potassium_mg=num("potassium"), vitamin_c_mg=num("vit_c"), vitamin_d_ug=num("vit_d"),
    )


class USDAProvider:
    BASE = "https://api.nal.usda.gov"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.environ.get("USDA_API_KEY", "DEMO_KEY")
        self._client = client or httpx.Client(base_url=self.BASE, timeout=15.0)

    def search(self, query: str, limit: int = 5) -> list[NutritionResult]:
        resp = self._client.get("/fdc/v1/foods/search", params={
            "query": query, "pageSize": limit, "api_key": self.api_key,
            "dataType": "Foundation,SR Legacy",
        })
        resp.raise_for_status()
        foods = resp.json().get("foods", [])
        return [parse_usda_food(f) for f in foods][:limit]
```

In `backend/app/config.py`, add `"USDA_API_KEY"` to the `_SHARED_ENV_KEYS` tuple.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/integrations/test_usda.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/integrations/usda.py backend/tests/integrations/test_usda.py
git commit -m "feat(integrations): USDA FoodData Central provider (rich micros)"
```

---

### Task 5: Staples seed (generate from USDA) + seeder

**Files:**
- Create: `backend/scripts/build_seed.py` (one-off generator)
- Create: `backend/app/seed/staples.json` (generated, committed)
- Create: `backend/app/seed/__init__.py`, `backend/app/seed/seeder.py`
- Test: `backend/tests/test_seeder.py`

- [ ] **Step 1: Write the generator**

```python
# backend/scripts/build_seed.py
"""One-off: fetch curated staples from USDA and write app/seed/staples.json.
Run with USDA_API_KEY available: `uv run python scripts/build_seed.py`."""
import json
from pathlib import Path
from app.config import load_project_env
from app.integrations.usda import USDAProvider

STAPLES = [
    "chicken breast raw", "egg whole raw", "salmon atlantic raw", "ground beef 90 lean raw",
    "canned tuna in water", "greek yogurt plain nonfat", "milk 2%", "cheddar cheese",
    "tofu firm", "lentils cooked", "black beans cooked", "chickpeas cooked",
    "white rice cooked", "brown rice cooked", "rolled oats dry", "whole wheat bread",
    "pasta cooked", "potato baked", "sweet potato baked", "quinoa cooked",
    "broccoli raw", "spinach raw", "carrot raw", "tomato raw", "bell pepper red raw",
    "cucumber", "zucchini", "green beans", "mushroom", "onion raw",
    "banana", "apple", "orange", "strawberries", "blueberries", "grapes", "avocado",
    "almonds", "peanut butter", "walnuts", "olive oil", "butter",
    "honey", "dark chocolate 70", "cottage cheese", "shrimp raw", "pork loin raw",
    "turkey breast raw", "cod raw", "edamame",
]  # ~50 high-value staples; extend toward ~150 as desired


def main():
    load_project_env()
    provider = USDAProvider()
    out = []
    for term in STAPLES:
        try:
            hits = provider.search(term, limit=1)
        except Exception as e:  # noqa: BLE001
            print(f"skip {term!r}: {e}")
            continue
        if hits:
            out.append(hits[0].model_dump())
            print(f"ok  {term!r} -> {hits[0].name}")
    dest = Path(__file__).resolve().parents[1] / "app" / "seed" / "staples.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {len(out)} foods to {dest}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the seed (real USDA call, needs the key in .env)**

Run: `cd backend && uv run python scripts/build_seed.py`
Expected: prints `ok ...` per food and `wrote N foods to .../staples.json`. Commit the generated `staples.json`.

- [ ] **Step 3: Write the failing seeder test**

```python
# backend/tests/test_seeder.py
import pytest
from app.db import Base, new_engine, new_session_factory
from app.repositories import FoodRepository
from app.seed.seeder import seed_staples


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_seed_is_idempotent_and_has_micros(session):
    added = seed_staples(session)
    session.commit()
    assert added >= 30
    foods = FoodRepository(session).list_all()
    assert any(f.iron_mg is not None for f in foods)  # micros present
    before = len(foods)
    seed_staples(session)            # second run adds nothing
    session.commit()
    assert len(FoodRepository(session).list_all()) == before
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_seeder.py -v`
Expected: FAIL — `ModuleNotFoundError: app.seed.seeder`.

- [ ] **Step 5: Implement the seeder**

```python
# backend/app/seed/seeder.py
"""Load the committed staples.json into the food library (idempotent on name+brand)."""
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Food
from app.repositories import FoodRepository

_SEED_FILE = Path(__file__).resolve().parent / "staples.json"
_FOOD_FIELDS = {
    "name", "brand", "serving_description", "serving_grams", "source", "source_id",
    "calories", "protein", "carbs", "fat_saturated", "fat_unsaturated", "fiber", "sodium",
    "sugar_g", "iron_mg", "calcium_mg", "potassium_mg", "vitamin_c_mg", "vitamin_d_ug",
}


def seed_staples(session: Session) -> int:
    if not _SEED_FILE.exists():
        return 0
    repo = FoodRepository(session)
    records = json.loads(_SEED_FILE.read_text())
    added = 0
    for rec in records:
        name, brand = rec.get("name", ""), rec.get("brand", "") or ""
        if not name or repo.find_by_name_brand(name, brand):
            continue
        repo.add(Food(**{k: v for k, v in rec.items() if k in _FOOD_FIELDS}))
        added += 1
    session.flush()
    return added
```

(Create empty `backend/app/seed/__init__.py`.)

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_seeder.py -v`
Expected: 1 passed (≥30 foods, micros present, idempotent).

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/build_seed.py backend/app/seed/ backend/tests/test_seeder.py
git commit -m "feat(seed): USDA-sourced staples seed + idempotent seeder"
```

---

### Task 6: Surface targets via API + agent tool

**Files:**
- Modify: `backend/app/api/users.py` (include `targets` in the user output)
- Modify: `backend/app/agent/tools.py` (`get_profile` returns macro + micro targets; run seeder + schema upgrade alongside DB init)
- Modify: `backend/app/main.py` (run `seed_staples` + `ensure_food_micro_columns` at startup)
- Test: `backend/tests/api/test_users_api.py` (assert targets present)

- [ ] **Step 1: Extend the users API test**

Append to `backend/tests/api/test_users_api.py`:

```python
def test_user_output_includes_targets(client):
    r = client.post("/users", json={
        "name": "T", "age": 30, "sex": "male", "height_cm": 181, "weight_kg": 85,
        "activity_level": "moderate", "goal_type": "lose", "goal_period": "week", "amount_kg": 0.5,
    })
    assert r.status_code == 201
    targets = r.json()["targets"]
    assert round(targets["protein_g"]) == 170
    assert round(targets["calories"]) == 2296
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_users_api.py::test_user_output_includes_targets -v`
Expected: FAIL (`KeyError: 'targets'`).

- [ ] **Step 3: Add targets to the user output**

In `backend/app/api/users.py`: import `from app.core.targets import compute_targets`, add `targets: dict` to `UserOut`, and in `_to_out` compute and include it:

```python
    targets = compute_targets(
        sex=user.sex, weight_kg=user.weight_kg, height_cm=user.height_cm, age=user.age,
        activity_level=user.activity_level, goal_type=user.goal_type,
        goal_period=user.goal_period, amount_kg=user.amount_kg,
    )
    return UserOut(id=user.id, name=user.name, metrics=metrics, targets=targets.__dict__)
```

- [ ] **Step 4: Update the `get_profile` agent tool**

In `backend/app/agent/tools.py`, replace the `get_profile` body to report targets:

```python
    @tool
    def get_profile() -> str:
        """Get the user's profile and daily macro + key-micro targets. Ground all advice in this."""
        u = users.get(user_id)
        if not u:
            return "No profile found for this user."
        from app.core.targets import compute_targets
        t = compute_targets(sex=u.sex, weight_kg=u.weight_kg, height_cm=u.height_cm, age=u.age,
                            activity_level=u.activity_level, goal_type=u.goal_type,
                            goal_period=u.goal_period, amount_kg=u.amount_kg)
        return (f"{u.name}: {round(t.calories)} kcal/day | protein {round(t.protein_g)}g, "
                f"carbs {round(t.carb_g)}g, fat {round(t.fat_g)}g, fiber {round(t.fiber_g)}g. "
                f"Micro goals: iron {t.iron_mg}mg, calcium {t.calcium_mg}mg, potassium {t.potassium_mg}mg, "
                f"vit C {t.vitamin_c_mg}mg, vit D {t.vitamin_d_ug}ug. Sodium cap {round(t.sodium_mg_max)}mg.")
```

- [ ] **Step 5: Seed + upgrade schema at startup**

In `backend/app/main.py` lifespan, after `init_db()`:

```python
    from app.db import engine, SessionLocal
    from app.migration.schema_upgrade import ensure_food_micro_columns
    from app.seed.seeder import seed_staples
    ensure_food_micro_columns(engine)
    with SessionLocal() as s:
        seed_staples(s)
        s.commit()
```

- [ ] **Step 6: Run the full suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/users.py backend/app/agent/tools.py backend/app/main.py backend/tests/api/test_users_api.py
git commit -m "feat(api/agent): expose macro + micro targets; seed staples at startup"
```

---

## Done when

- `cd backend && uv run pytest` is green.
- `compute_targets` returns correct macro + micro targets.
- `Food` stores micros; the existing dev DB upgrades non-destructively.
- `USDAProvider` returns rich foods; `staples.json` is generated + committed; the seeder loads ~50+ foods idempotently with micros.
- `POST /users` and the `get_profile` tool report full targets.

## Out of scope (Plan B)

- `fit_servings` optimizer + `PlanScore` scorecard
- foods+meals building blocks with meal flex
- the `plan_day` agent tool + prompt
