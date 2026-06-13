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
