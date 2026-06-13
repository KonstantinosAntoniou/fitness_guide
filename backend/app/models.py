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
