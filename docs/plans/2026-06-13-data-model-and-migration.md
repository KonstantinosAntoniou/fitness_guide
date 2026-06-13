# Data Model + Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a SQLite-backed persistence layer — User/Food/Meal/MealItem models, repositories, and a migration that seeds the food & meal library from the legacy Excel exports — and persist user profiles through the API.

**Architecture:** SQLAlchemy 2.0 (typed `Mapped` models) on SQLite via the existing `DATABASE_URL` setting. Pure Excel-parsing functions are separated from DB insertion so they're unit-testable without a database. Repositories keep SQL out of the API and (later) the agent.

**Tech Stack:** SQLAlchemy 2.0, openpyxl (migration), SQLite, FastAPI, pytest.

Implements [the rebuild spec](../specs/2026-06-13-fitness-coach-rebuild-design.md) §6 (data model) and §9 (migration).

### Design note — per-serving, not per-100g

Inspecting `foods_log.xlsx` showed macros are stored **per listed serving** (e.g. "1 medium" apple = 97 cal), with no gram weight. So `Food` stores **per-serving** macros plus a `serving_description` and an optional `serving_grams` (populated when known, e.g. from Open Food Facts). Quantities are **servings** (float). The legacy `Fat_Saturated`/`Fat_Regular` columns map to `fat_saturated`/`fat_unsaturated`, with `fat_total` as a computed property. **Task 1 includes amending spec §6 to record this.**

---

### Task 1: Dependencies, DB layer, and spec amendment

**Files:**
- Modify: `backend/pyproject.toml` (add `sqlalchemy`, `openpyxl`)
- Create: `backend/app/db.py`
- Modify: `docs/specs/2026-06-13-fitness-coach-rebuild-design.md` (§6 per-serving note)
- Test: `backend/tests/test_db.py`

- [ ] **Step 1: Add dependencies**

Run: `uv add --directory backend sqlalchemy openpyxl`
Expected: `pyproject.toml` gains `sqlalchemy>=2.0` and `openpyxl>=3.1`; `uv.lock` updates.

- [ ] **Step 2: Amend the spec**

In `docs/specs/2026-06-13-fitness-coach-rebuild-design.md`, replace the §6 line
"**All nutrient values are stored per 100g**; quantities are stored in grams" with:
"**Nutrient values are stored per serving** (legacy data is per-serving with no gram weight). `Food` carries a `serving_description` and an optional `serving_grams`; quantities are **servings** (float). When `serving_grams` is known, grams↔servings conversion is possible."

- [ ] **Step 3: Write the failing test**

```python
# backend/tests/test_db.py
from sqlalchemy import text
from app.db import Base, new_engine, new_session_factory


def test_create_all_and_session_roundtrip():
    engine = new_engine("sqlite://")  # in-memory
    Base.metadata.create_all(engine)
    Session = new_session_factory(engine)
    with Session() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_db.py -v`
Expected: FAIL — `ImportError` (app.db missing).

- [ ] **Step 5: Implement the DB layer**

```python
# backend/app/db.py
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings


class Base(DeclarativeBase):
    pass


def new_engine(url: str | None = None) -> Engine:
    url = url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def new_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


engine = new_engine()
SessionLocal = new_session_factory(engine)


def init_db() -> None:
    import app.models  # noqa: F401  (register mappers)
    Base.metadata.create_all(engine)


def get_session():
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/db.py backend/tests/test_db.py docs/specs/2026-06-13-fitness-coach-rebuild-design.md
git commit -m "feat(db): SQLAlchemy engine/session layer + per-serving spec amendment"
```

---

### Task 2: ORM models (User, Food, Meal, MealItem)

**Files:**
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_models.py
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import User, Food, Meal, MealItem


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_food_fat_total_is_computed(session):
    f = Food(name="Oats", brand="Brown", serving_description="100g",
             calories=375, protein=11, carbs=69, fat_saturated=1, fat_unsaturated=8, sodium=0)
    session.add(f)
    session.commit()
    assert f.fat_total == 9


def test_meal_with_items(session):
    chicken = Food(name="Chicken", brand="Breast", serving_description="100g", calories=165, protein=31)
    session.add(chicken)
    session.flush()
    meal = Meal(name="Lunch", items=[MealItem(food_id=chicken.id, servings=2.0)])
    session.add(meal)
    session.commit()
    assert meal.items[0].food.name == "Chicken"
    assert meal.items[0].servings == 2.0


def test_user_optional_goal(session):
    u = User(name="Kostas", age=30, sex="male", height_cm=180, weight_kg=80, activity_level="moderate")
    session.add(u)
    session.commit()
    assert u.goal_type is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: FAIL — `ImportError` (app.models missing).

- [ ] **Step 3: Implement the models**

```python
# backend/app/models.py
from typing import Optional
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    age: Mapped[int]
    sex: Mapped[str]
    height_cm: Mapped[float]
    weight_kg: Mapped[float]
    activity_level: Mapped[str]
    goal_type: Mapped[Optional[str]] = mapped_column(default=None)
    goal_period: Mapped[Optional[str]] = mapped_column(default=None)
    amount_kg: Mapped[Optional[float]] = mapped_column(default=None)


class Food(Base):
    __tablename__ = "foods"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    brand: Mapped[str] = mapped_column(String, default="")
    serving_description: Mapped[str] = mapped_column(String, default="100g")
    serving_grams: Mapped[Optional[float]] = mapped_column(default=None)
    source: Mapped[str] = mapped_column(String, default="manual")
    source_id: Mapped[Optional[str]] = mapped_column(String, default=None)
    # macros PER SERVING
    calories: Mapped[float] = mapped_column(default=0.0)
    protein: Mapped[float] = mapped_column(default=0.0)
    carbs: Mapped[float] = mapped_column(default=0.0)
    fat_saturated: Mapped[float] = mapped_column(default=0.0)
    fat_unsaturated: Mapped[float] = mapped_column(default=0.0)
    fiber: Mapped[Optional[float]] = mapped_column(default=None)
    sodium: Mapped[float] = mapped_column(default=0.0)

    meal_items: Mapped[list["MealItem"]] = relationship(
        back_populates="food", cascade="all, delete-orphan"
    )

    @property
    def fat_total(self) -> float:
        return self.fat_saturated + self.fat_unsaturated


class Meal(Base):
    __tablename__ = "meals"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )


class MealItem(Base):
    __tablename__ = "meal_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id"))
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    servings: Mapped[float] = mapped_column(default=1.0)

    meal: Mapped["Meal"] = relationship(back_populates="items")
    food: Mapped["Food"] = relationship(back_populates="meal_items")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(models): User, Food (per-serving), Meal, MealItem"
```

---

### Task 3: Repositories

**Files:**
- Create: `backend/app/repositories.py`
- Test: `backend/tests/test_repositories.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_repositories.py
import pytest
from app.db import Base, new_engine, new_session_factory
from app.models import Food
from app.repositories import FoodRepository, MealRepository, UserRepository


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


def test_food_upsert_is_idempotent(session):
    repo = FoodRepository(session)
    repo.add(Food(name="Apple", brand="Green", serving_description="1 medium", calories=97))
    session.commit()
    # same name+brand should be found, not duplicated
    existing = repo.find_by_name_brand("apple", "green")
    assert existing is not None
    assert len(repo.list_all()) == 1


def test_user_create_and_get(session):
    repo = UserRepository(session)
    u = repo.create(name="Kostas", age=30, sex="male", height_cm=180,
                    weight_kg=80, activity_level="moderate")
    session.commit()
    assert repo.get(u.id).name == "Kostas"


def test_meal_get_by_name(session):
    repo = MealRepository(session)
    repo.create(name="Lunch")
    session.commit()
    assert repo.find_by_name("lunch").name == "Lunch"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_repositories.py -v`
Expected: FAIL — `ImportError` (app.repositories missing).

- [ ] **Step 3: Implement repositories**

```python
# backend/app/repositories.py
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import User, Food, Meal


class FoodRepository:
    def __init__(self, session: Session):
        self.s = session

    def add(self, food: Food) -> Food:
        self.s.add(food)
        return food

    def find_by_name_brand(self, name: str, brand: str) -> Optional[Food]:
        return self.s.scalar(
            select(Food).where(Food.name.ilike(name), Food.brand.ilike(brand))
        )

    def get(self, food_id: int) -> Optional[Food]:
        return self.s.get(Food, food_id)

    def list_all(self) -> list[Food]:
        return list(self.s.scalars(select(Food).order_by(Food.name)))


class MealRepository:
    def __init__(self, session: Session):
        self.s = session

    def create(self, name: str) -> Meal:
        meal = Meal(name=name)
        self.s.add(meal)
        return meal

    def find_by_name(self, name: str) -> Optional[Meal]:
        return self.s.scalar(select(Meal).where(Meal.name.ilike(name)))

    def list_all(self) -> list[Meal]:
        return list(self.s.scalars(select(Meal).order_by(Meal.name)))


class UserRepository:
    def __init__(self, session: Session):
        self.s = session

    def create(self, **fields) -> User:
        user = User(**fields)
        self.s.add(user)
        return user

    def get(self, user_id: int) -> Optional[User]:
        return self.s.get(User, user_id)

    def find_by_name(self, name: str) -> Optional[User]:
        return self.s.scalar(select(User).where(User.name.ilike(name)))

    def list_all(self) -> list[User]:
        return list(self.s.scalars(select(User).order_by(User.name)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_repositories.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories.py backend/tests/test_repositories.py
git commit -m "feat(repositories): Food, Meal, User data access"
```

---

### Task 4: Pure Excel parsers

**Files:**
- Create: `backend/app/migration/__init__.py`
- Create: `backend/app/migration/parsers.py`
- Test: `backend/tests/migration/__init__.py`, `backend/tests/migration/test_parsers.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/migration/test_parsers.py
import pytest
from app.migration.parsers import food_from_row, parse_meal_food_name


def test_food_from_row():
    row = {"Name": "Oats", "Label": "Brown", "Measurement": "100g",
           "Calories": 375, "Protein": 11, "Carbs": 69,
           "Fat_Saturated": 1, "Fat_Regular": 8, "Sodium": 0}
    f = food_from_row(row)
    assert f.name == "Oats"
    assert f.brand == "Brown"
    assert f.serving_description == "100g"
    assert f.fat_saturated == 1
    assert f.fat_unsaturated == 8
    assert f.calories == 375


@pytest.mark.parametrize("raw,mult,name", [
    ("2.1x Chichen", 2.1, "Chichen"),
    ("2.0x Pita Kalampokiou", 2.0, "Pita Kalampokiou"),
    ("1x Egg", 1.0, "Egg"),
])
def test_parse_meal_food_name(raw, mult, name):
    assert parse_meal_food_name(raw) == (mult, name)


def test_parse_meal_food_name_rejects_total():
    with pytest.raises(ValueError):
        parse_meal_food_name("Total")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/migration/test_parsers.py -v`
Expected: FAIL — `ModuleNotFoundError` (app.migration.parsers missing).

- [ ] **Step 3: Implement parsers**

```python
# backend/app/migration/parsers.py
"""Pure parsing of legacy Excel rows. No DB, no I/O."""
import re
from app.models import Food

_MULT = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*x\s+(.*\S)\s*$", re.IGNORECASE)


def food_from_row(row: dict) -> Food:
    def num(key):
        v = row.get(key)
        return float(v) if v is not None else 0.0

    return Food(
        name=str(row["Name"]).strip(),
        brand=str(row.get("Label") or "").strip(),
        serving_description=str(row.get("Measurement") or "100g").strip(),
        calories=num("Calories"),
        protein=num("Protein"),
        carbs=num("Carbs"),
        fat_saturated=num("Fat_Saturated"),
        fat_unsaturated=num("Fat_Regular"),
        sodium=num("Sodium"),
        source="legacy",
    )


def parse_meal_food_name(raw: str) -> tuple[float, str]:
    """'2.1x Chichen' -> (2.1, 'Chichen'). Raises ValueError on non-item rows."""
    m = _MULT.match(raw or "")
    if not m:
        raise ValueError(f"not a meal item row: {raw!r}")
    return float(m.group(1)), m.group(2).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/migration/test_parsers.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/migration/__init__.py backend/app/migration/parsers.py backend/tests/migration/
git commit -m "feat(migration): pure parsers for legacy food and meal rows"
```

---

### Task 5: Migration runner (foods + best-effort meals)

**Files:**
- Create: `backend/app/migration/runner.py`
- Test: `backend/tests/migration/test_runner.py`

Foods migrate 1:1 (idempotent on name+brand). Meals are best-effort: group by `Meal_Name`, skip `Total` rows, parse the multiplier, match an existing food by name+brand; **unmatched food rows are skipped and counted** (legacy data has typos, e.g. "Chichen"). Returns a report dict.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/migration/test_runner.py
from pathlib import Path
import pytest
from app.db import Base, new_engine, new_session_factory
from app.migration.runner import migrate

REPO_ROOT = Path(__file__).resolve().parents[3]
FOODS_XLSX = REPO_ROOT / "foods_log.xlsx"
MEALS_XLSX = REPO_ROOT / "meals_log.xlsx"


@pytest.fixture
def session():
    engine = new_engine("sqlite://")
    Base.metadata.create_all(engine)
    with new_session_factory(engine)() as s:
        yield s


@pytest.mark.skipif(not FOODS_XLSX.exists(), reason="legacy Excel not present")
def test_migrate_loads_foods_and_is_idempotent(session):
    report = migrate(session, str(FOODS_XLSX), str(MEALS_XLSX))
    session.commit()
    assert report["foods_added"] >= 60
    from app.repositories import FoodRepository
    count = len(FoodRepository(session).list_all())
    # running again adds no duplicate foods
    migrate(session, str(FOODS_XLSX), str(MEALS_XLSX))
    session.commit()
    assert len(FoodRepository(session).list_all()) == count
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/migration/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError` (app.migration.runner missing).

- [ ] **Step 3: Implement the runner**

```python
# backend/app/migration/runner.py
"""Seed the DB from legacy Excel exports. Idempotent on foods (name+brand)."""
from openpyxl import load_workbook
from sqlalchemy.orm import Session
from app.models import Meal, MealItem
from app.repositories import FoodRepository, MealRepository
from app.migration.parsers import food_from_row, parse_meal_food_name


def _rows(path: str) -> list[dict]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    data = list(ws.iter_rows(values_only=True))
    if not data:
        return []
    header = [str(h) for h in data[0]]
    return [dict(zip(header, r)) for r in data[1:] if any(c is not None for c in r)]


def migrate(session: Session, foods_path: str, meals_path: str | None = None) -> dict:
    foods = FoodRepository(session)
    report = {"foods_added": 0, "meals_added": 0, "meal_items_added": 0, "skipped": 0}

    for row in _rows(foods_path):
        if not row.get("Name"):
            continue
        if foods.find_by_name_brand(str(row["Name"]), str(row.get("Label") or "")):
            continue
        foods.add(food_from_row(row))
        report["foods_added"] += 1
    session.flush()

    if meals_path:
        meals = MealRepository(session)
        grouped: dict[str, list[dict]] = {}
        for row in _rows(meals_path):
            name = row.get("Meal_Name")
            if name:
                grouped.setdefault(str(name), []).append(row)

        for meal_name, items in grouped.items():
            if meals.find_by_name(meal_name):
                continue
            meal = Meal(name=meal_name)
            session.add(meal)
            session.flush()
            for row in items:
                try:
                    mult, food_name = parse_meal_food_name(str(row.get("Food_Name") or ""))
                except ValueError:
                    continue  # Total / summary rows
                food = foods.find_by_name_brand(food_name, str(row.get("Label") or ""))
                if not food:
                    report["skipped"] += 1
                    continue
                session.add(MealItem(meal_id=meal.id, food_id=food.id, servings=mult))
                report["meal_items_added"] += 1
            report["meals_added"] += 1

    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/migration/test_runner.py -v`
Expected: 1 passed (foods loaded, idempotent).

- [ ] **Step 5: Run the migration for real (creates the dev DB)**

Run: `cd backend && uv run python -c "from app.db import init_db, SessionLocal; from app.migration.runner import migrate; init_db(); s=SessionLocal(); print(migrate(s, '../foods_log.xlsx', '../meals_log.xlsx')); s.commit()"`
Expected: prints a report like `{'foods_added': 66, 'meals_added': ..., 'meal_items_added': ..., 'skipped': ...}`. Creates `backend/fitness.db` (gitignored).

- [ ] **Step 6: Commit**

```bash
git add backend/app/migration/runner.py backend/tests/migration/test_runner.py
git commit -m "feat(migration): Excel runner — foods (idempotent) + best-effort meals"
```

---

### Task 6: Persist profiles + expose data through the API

**Files:**
- Create: `backend/app/api/users.py`
- Create: `backend/app/api/foods.py`
- Modify: `backend/app/main.py` (init DB on startup, include routers)
- Test: `backend/tests/api/test_users_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_users_api.py
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


def test_create_and_list_user(client):
    r = client.post("/users", json={
        "name": "Kostas", "age": 30, "sex": "male", "height_cm": 180,
        "weight_kg": 80, "activity_level": "moderate",
        "goal_type": "lose", "goal_period": "week", "amount_kg": 0.5,
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Kostas"
    assert round(body["metrics"]["target_calories"]) == 2209

    r2 = client.get("/users")
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_duplicate_name_rejected(client):
    payload = {"name": "Kostas", "age": 30, "sex": "male", "height_cm": 180,
               "weight_kg": 80, "activity_level": "moderate"}
    assert client.post("/users", json=payload).status_code == 201
    assert client.post("/users", json=payload).status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_users_api.py -v`
Expected: FAIL — `ImportError` / 404 (users router missing).

- [ ] **Step 3: Implement the users router**

```python
# backend/app/api/users.py
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.repositories import UserRepository
from app.core.profile import compute_metrics

router = APIRouter(prefix="/users", tags=["users"])


class UserInput(BaseModel):
    name: str
    age: int
    sex: Literal["male", "female"]
    height_cm: float
    weight_kg: float
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"]
    goal_type: Optional[Literal["lose", "gain"]] = None
    goal_period: Optional[Literal["week", "month", "year"]] = None
    amount_kg: Optional[float] = None


class UserOut(BaseModel):
    id: int
    name: str
    metrics: dict


def _to_out(user) -> UserOut:
    metrics = compute_metrics(
        sex=user.sex, weight_kg=user.weight_kg, height_cm=user.height_cm,
        age=user.age, activity_level=user.activity_level,
        goal_type=user.goal_type, goal_period=user.goal_period, amount_kg=user.amount_kg,
    )
    return UserOut(id=user.id, name=user.name, metrics=metrics)


@router.post("", status_code=201, response_model=UserOut)
def create_user(payload: UserInput, db: Session = Depends(get_session)) -> UserOut:
    repo = UserRepository(db)
    if repo.find_by_name(payload.name):
        raise HTTPException(status_code=409, detail="user with that name exists")
    user = repo.create(**payload.model_dump())
    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_session)) -> list[UserOut]:
    return [_to_out(u) for u in UserRepository(db).list_all()]


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_session)) -> UserOut:
    user = UserRepository(db).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="not found")
    return _to_out(user)
```

- [ ] **Step 4: Implement the foods router**

```python
# backend/app/api/foods.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
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


@router.get("", response_model=list[FoodOut])
def list_foods(db: Session = Depends(get_session)) -> list[FoodOut]:
    out = []
    for f in FoodRepository(db).list_all():
        out.append(FoodOut(
            id=f.id, name=f.name, brand=f.brand, serving_description=f.serving_description,
            calories=f.calories, protein=f.protein, carbs=f.carbs,
            fat_total=f.fat_total, sodium=f.sodium,
        ))
    return out
```

- [ ] **Step 5: Wire routers + DB init into the app**

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import init_db
from app.api.profile import router as profile_router
from app.api.users import router as users_router
from app.api.foods import router as foods_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Fitness Coach API", lifespan=lifespan)
app.include_router(profile_router)
app.include_router(users_router)
app.include_router(foods_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 6: Run the test and full suite**

Run: `cd backend && uv run pytest -v`
Expected: all tests pass (Plan 1 + new db/models/repos/migration/users).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/users.py backend/app/api/foods.py backend/app/main.py backend/tests/api/test_users_api.py
git commit -m "feat(api): persist user profiles + list foods"
```

---

## Done when

- `cd backend && uv run pytest` is green.
- Running the migration loads ~66 foods (idempotent) and best-effort meals into `fitness.db`.
- `POST /users` persists a profile and returns computed metrics; `GET /users`, `GET /users/{id}`, `GET /foods` work.

## Out of scope (later plans)

- Open Food Facts nutrition lookup (Plan 3)
- Plan / PlanEntry / PlanItem / LogEntry tables + meal-plan builder (Plan 4)
- LangGraph + Gemini agent (Plan 5)
