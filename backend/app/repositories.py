import datetime
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models import User, Food, Meal, Plan, PlanEntry, PlanItem, LogEntry


class FoodRepository:
    def __init__(self, session: Session):
        self.s = session

    def add(self, food: Food) -> Food:
        self.s.add(food)
        return food

    def find_by_name_brand(self, name: str, brand: str) -> Optional[Food]:
        # exact, case-insensitive, whitespace-tolerant — robust dedup
        return self.s.scalar(
            select(Food).where(
                func.lower(Food.name) == name.strip().lower(),
                func.lower(Food.brand) == (brand or "").strip().lower(),
            )
        )

    def get(self, food_id: int) -> Optional[Food]:
        return self.s.get(Food, food_id)

    def list_all(self) -> list[Food]:
        return list(self.s.scalars(select(Food).order_by(Food.name)))

    def search(self, query: str, limit: int = 20) -> list[Food]:
        like = f"%{query.strip()}%"
        return list(self.s.scalars(
            select(Food).where(Food.name.ilike(like)).order_by(Food.name).limit(limit)
        ))


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

    def for_day(self, user_id: int, day: datetime.date) -> list[LogEntry]:
        return list(self.s.scalars(
            select(LogEntry).where(LogEntry.user_id == user_id, LogEntry.eaten_on == day)
        ))
