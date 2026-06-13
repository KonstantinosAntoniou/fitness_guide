# Nutrition Integration (Open Food Facts) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve foods not yet in the database via Open Food Facts — normalize results into our per-serving `Food` shape, search them through the API, and save chosen ones to the food library.

**Architecture:** A provider-agnostic `integrations/` layer. `parse_off_product` is a pure normalization function (OFF JSON → `NutritionResult`), unit-tested with fixtures. `OpenFoodFactsProvider` wraps an injectable `httpx.Client` so tests use `httpx.MockTransport` (no live network). The API exposes search + a save endpoint; the provider is a FastAPI dependency that tests override with a fake.

**Tech Stack:** httpx, Pydantic v2, FastAPI, pytest.

Implements [the rebuild spec](../specs/2026-06-13-fitness-coach-rebuild-design.md) §8 (nutrition source). USDA can be added later behind the same `NutritionProvider` protocol.

---

### Task 1: httpx dep + NutritionResult DTO + OFF normalization (pure)

**Files:**
- Modify: `backend/pyproject.toml` (add `httpx` to main deps)
- Create: `backend/app/integrations/__init__.py`, `backend/app/integrations/nutrition.py`
- Create: `backend/tests/integrations/__init__.py`, `backend/tests/integrations/test_normalize.py`

- [ ] **Step 1: Add httpx as a runtime dependency**

Run: `uv add --directory backend httpx`
Expected: `httpx` moves into `[project].dependencies`.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/integrations/test_normalize.py
import pytest
from app.integrations.nutrition import parse_off_product, NutritionResult

SAMPLE = {
    "code": "3017620422003",
    "product_name": "Nutella",
    "brands": "Ferrero",
    "nutriments": {
        "energy-kcal_100g": 539,
        "proteins_100g": 6.3,
        "carbohydrates_100g": 57.5,
        "fat_100g": 30.9,
        "saturated-fat_100g": 10.6,
        "fiber_100g": 0,
        "sodium_100g": 0.0428,
    },
}


def test_parse_off_product():
    r = parse_off_product(SAMPLE)
    assert isinstance(r, NutritionResult)
    assert r.name == "Nutella"
    assert r.brand == "Ferrero"
    assert r.source == "openfoodfacts"
    assert r.source_id == "3017620422003"
    assert r.serving_description == "100g"
    assert r.serving_grams == 100
    assert r.calories == 539
    assert r.fat_saturated == 10.6
    # unsaturated = total - saturated, clamped at >= 0
    assert r.fat_unsaturated == pytest.approx(20.3)
    assert r.sodium == pytest.approx(0.0428)


def test_parse_off_product_missing_fields_default_zero():
    r = parse_off_product({"product_name": "Mystery", "nutriments": {}})
    assert r.name == "Mystery"
    assert r.calories == 0
    assert r.fat_unsaturated == 0


def test_parse_off_product_clamps_negative_unsaturated():
    # saturated > total (dirty data) must not produce negative unsaturated
    r = parse_off_product({"product_name": "X", "nutriments": {"fat_100g": 1, "saturated-fat_100g": 5}})
    assert r.fat_unsaturated == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integrations/test_normalize.py -v`
Expected: FAIL — `ModuleNotFoundError: app.integrations.nutrition`.

- [ ] **Step 4: Implement DTO + normalization + provider protocol**

```python
# backend/app/integrations/nutrition.py
"""Provider-agnostic nutrition lookup types + Open Food Facts normalization."""
from typing import Optional, Protocol
from pydantic import BaseModel


class NutritionResult(BaseModel):
    name: str
    brand: str = ""
    serving_description: str = "100g"
    serving_grams: Optional[float] = 100
    source: str = "openfoodfacts"
    source_id: Optional[str] = None
    calories: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat_saturated: float = 0.0
    fat_unsaturated: float = 0.0
    fiber: Optional[float] = None
    sodium: float = 0.0


class NutritionProvider(Protocol):
    def search(self, query: str, limit: int = 5) -> list[NutritionResult]:
        ...


def _num(d: dict, key: str, default: float = 0.0) -> float:
    v = d.get(key)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_off_product(product: dict) -> NutritionResult:
    """Open Food Facts product JSON -> NutritionResult (values are per 100g)."""
    n = product.get("nutriments", {}) or {}
    fat_total = _num(n, "fat_100g")
    saturated = _num(n, "saturated-fat_100g")
    fiber = n.get("fiber_100g")
    return NutritionResult(
        name=str(product.get("product_name") or "Unknown").strip(),
        brand=str((product.get("brands") or "").split(",")[0]).strip(),
        serving_description="100g",
        serving_grams=100,
        source="openfoodfacts",
        source_id=str(product["code"]) if product.get("code") else None,
        calories=_num(n, "energy-kcal_100g"),
        protein=_num(n, "proteins_100g"),
        carbs=_num(n, "carbohydrates_100g"),
        fat_saturated=saturated,
        fat_unsaturated=max(0.0, fat_total - saturated),
        fiber=float(fiber) if fiber is not None else None,
        sodium=_num(n, "sodium_100g"),
    )
```

(Also create empty `backend/app/integrations/__init__.py` and `backend/tests/integrations/__init__.py`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/integrations/test_normalize.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/integrations/__init__.py backend/app/integrations/nutrition.py backend/tests/integrations/
git commit -m "feat(integrations): nutrition DTO + Open Food Facts normalization"
```

---

### Task 2: OpenFoodFactsProvider (httpx client)

**Files:**
- Create: `backend/app/integrations/openfoodfacts.py`
- Test: `backend/tests/integrations/test_openfoodfacts.py`

- [ ] **Step 1: Write the failing test (mocked HTTP, no network)**

```python
# backend/tests/integrations/test_openfoodfacts.py
import json
import httpx
from app.integrations.openfoodfacts import OpenFoodFactsProvider

OFF_RESPONSE = {
    "count": 1,
    "products": [{
        "code": "111",
        "product_name": "Greek Yogurt",
        "brands": "Total",
        "nutriments": {
            "energy-kcal_100g": 59, "proteins_100g": 10, "carbohydrates_100g": 3.6,
            "fat_100g": 0.4, "saturated-fat_100g": 0.3, "sodium_100g": 0.05,
        },
    }],
}


def _provider_with(response: dict) -> OpenFoodFactsProvider:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=response)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=OpenFoodFactsProvider.BASE)
    p = OpenFoodFactsProvider(client=client)
    p._captured = captured  # for assertions
    return p


def test_search_parses_results():
    p = _provider_with(OFF_RESPONSE)
    results = p.search("yogurt", limit=3)
    assert len(results) == 1
    assert results[0].name == "Greek Yogurt"
    assert results[0].calories == 59
    assert results[0].source == "openfoodfacts"
    # the query reached the search endpoint with our term
    assert "search_terms=yogurt" in p._captured["url"]


def test_search_skips_products_without_calories():
    resp = {"products": [{"product_name": "No Macros", "nutriments": {}}]}
    p = _provider_with(resp)
    assert p.search("x") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integrations/test_openfoodfacts.py -v`
Expected: FAIL — `ModuleNotFoundError: app.integrations.openfoodfacts`.

- [ ] **Step 3: Implement the provider**

```python
# backend/app/integrations/openfoodfacts.py
"""Open Food Facts nutrition provider."""
import httpx
from app.integrations.nutrition import NutritionResult, parse_off_product

_FIELDS = "code,product_name,brands,nutriments"


class OpenFoodFactsProvider:
    BASE = "https://world.openfoodfacts.org"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            base_url=self.BASE,
            timeout=10.0,
            headers={"User-Agent": "fitness-coach/0.1 (personal project)"},
        )

    def search(self, query: str, limit: int = 5) -> list[NutritionResult]:
        resp = self._client.get(
            "/cgi/search.pl",
            params={
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": limit,
                "fields": _FIELDS,
            },
        )
        resp.raise_for_status()
        products = resp.json().get("products", [])
        results = [parse_off_product(p) for p in products]
        # keep only usable results (real calorie data)
        return [r for r in results if r.calories > 0][:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/integrations/test_openfoodfacts.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/openfoodfacts.py backend/tests/integrations/test_openfoodfacts.py
git commit -m "feat(integrations): Open Food Facts search provider (httpx)"
```

---

### Task 3: API — save foods + nutrition search

**Files:**
- Modify: `backend/app/api/foods.py` (add `POST /foods`)
- Create: `backend/app/api/nutrition.py` (`GET /nutrition/search` + provider dependency)
- Modify: `backend/app/main.py` (include nutrition router)
- Test: `backend/tests/api/test_foods_api.py`, `backend/tests/api/test_nutrition_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/api/test_foods_api.py
import pytest
from fastapi.testclient import TestClient
from app.db import Base, new_engine, new_session_factory, get_session
from app.main import app


@pytest.fixture
def client():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestingSession = new_session_factory(engine)

    def override():
        with TestingSession() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_food_and_list(client):
    payload = {"name": "Banana", "brand": "", "serving_description": "1 medium",
               "calories": 105, "protein": 1.3, "carbs": 27,
               "fat_saturated": 0.1, "fat_unsaturated": 0.2, "sodium": 0.001}
    r = client.post("/foods", json=payload)
    assert r.status_code == 201
    assert r.json()["name"] == "Banana"
    listed = client.get("/foods").json()
    assert any(f["name"] == "Banana" for f in listed)


def test_create_food_duplicate_rejected(client):
    payload = {"name": "Banana", "brand": "Dole", "calories": 105}
    assert client.post("/foods", json=payload).status_code == 201
    assert client.post("/foods", json=payload).status_code == 409
```

```python
# backend/tests/api/test_nutrition_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.nutrition import get_nutrition_provider
from app.integrations.nutrition import NutritionResult


class FakeProvider:
    def search(self, query: str, limit: int = 5):
        return [NutritionResult(name=f"{query}-result", calories=100, protein=5,
                                carbs=10, fat_saturated=1, fat_unsaturated=2, sodium=0.01)]


@pytest.fixture
def client():
    app.dependency_overrides[get_nutrition_provider] = lambda: FakeProvider()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_nutrition_search(client):
    r = client.get("/nutrition/search", params={"q": "apple"})
    assert r.status_code == 200
    body = r.json()
    assert body[0]["name"] == "apple-result"
    assert body[0]["calories"] == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_foods_api.py tests/api/test_nutrition_api.py -v`
Expected: FAIL (POST /foods 405/404; nutrition router import error).

- [ ] **Step 3: Add `POST /foods` to the foods router**

Replace `backend/app/api/foods.py` with:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.models import Food
from app.repositories import FoodRepository

router = APIRouter(prefix="/foods", tags=["foods"])


class FoodOut(BaseModel):
    id: int
    name: str
    brand: str
    serving_description: str
    calories: float
    protein: float
    carbs: float
    fat_total: float
    sodium: float


class FoodCreate(BaseModel):
    name: str
    brand: str = ""
    serving_description: str = "100g"
    serving_grams: float | None = None
    source: str = "manual"
    source_id: str | None = None
    calories: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat_saturated: float = 0.0
    fat_unsaturated: float = 0.0
    fiber: float | None = None
    sodium: float = 0.0


def _to_out(f: Food) -> FoodOut:
    return FoodOut(
        id=f.id, name=f.name, brand=f.brand, serving_description=f.serving_description,
        calories=f.calories, protein=f.protein, carbs=f.carbs,
        fat_total=f.fat_total, sodium=f.sodium,
    )


@router.get("", response_model=list[FoodOut])
def list_foods(db: Session = Depends(get_session)) -> list[FoodOut]:
    return [_to_out(f) for f in FoodRepository(db).list_all()]


@router.post("", status_code=201, response_model=FoodOut)
def create_food(payload: FoodCreate, db: Session = Depends(get_session)) -> FoodOut:
    repo = FoodRepository(db)
    if repo.find_by_name_brand(payload.name, payload.brand):
        raise HTTPException(status_code=409, detail="food with that name+brand exists")
    food = repo.add(Food(**payload.model_dump()))
    db.commit()
    db.refresh(food)
    return _to_out(food)
```

- [ ] **Step 4: Create the nutrition router**

```python
# backend/app/api/nutrition.py
from fastapi import APIRouter, Depends, Query
from app.integrations.nutrition import NutritionResult, NutritionProvider
from app.integrations.openfoodfacts import OpenFoodFactsProvider

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


def get_nutrition_provider() -> NutritionProvider:
    return OpenFoodFactsProvider()


@router.get("/search", response_model=list[NutritionResult])
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=25),
    provider: NutritionProvider = Depends(get_nutrition_provider),
) -> list[NutritionResult]:
    return provider.search(q, limit=limit)
```

- [ ] **Step 5: Register the nutrition router in main.py**

In `backend/app/main.py`, add the import and `app.include_router(nutrition_router)`:

```python
from app.api.nutrition import router as nutrition_router
# ... after the other include_router calls:
app.include_router(nutrition_router)
```

- [ ] **Step 6: Run the targeted tests, then the full suite**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass (Plans 1–2 + normalization + provider + foods/nutrition API).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/foods.py backend/app/api/nutrition.py backend/app/main.py backend/tests/api/test_foods_api.py backend/tests/api/test_nutrition_api.py
git commit -m "feat(api): save foods + Open Food Facts nutrition search"
```

---

## Done when

- `cd backend && uv run pytest` is green (no live network used in tests).
- `GET /nutrition/search?q=banana` returns normalized candidates from Open Food Facts (live).
- `POST /foods` saves a food (dedup on name+brand); `GET /foods` lists it.

## Out of scope (later plans)

- USDA FoodData Central provider (same `NutritionProvider` protocol)
- Plan/PlanEntry/PlanItem/LogEntry + meal-plan builder (Plan 4)
- LangGraph + Gemini agent wiring the search/save as tools (Plan 5)
