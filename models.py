from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Date
from sqlalchemy.orm import relationship
from db import Base


class User(Base):
    __tablename__ = 'users'

    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String, unique=True, nullable=False)
    age              = Column(Integer, nullable=False)
    sex              = Column(String, nullable=False)
    height_cm        = Column(Float,   nullable=False)
    weight_kg        = Column(Float,   nullable=False)
    activity_level   = Column(String,  nullable=False)
    # algorithm outputs
    bmr_hb           = Column(Float,   nullable=False)
    bmr_msj          = Column(Float,   nullable=False)
    tdee_hb          = Column(Float,   nullable=False)
    tdee_msj         = Column(Float,   nullable=False)
    # optional goal
    goal_type        = Column(String,  nullable=True)   # "Lose weight" / "Gain weight"
    target_calories  = Column(Float,   nullable=True)

    daily_plans = relationship("DailyPlan", back_populates="user", cascade="all, delete-orphan")

class Food(Base):
    __tablename__ = "foods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    label = Column(String, nullable=False) 
    measurement = Column(String, nullable=False)
    calories = Column(Integer)
    protein = Column(Integer)
    carbs = Column(Integer)
    fat_saturated = Column(Integer)
    fat_regular = Column(Integer)
    sodium = Column(Integer)

    meal_food_items = relationship("MealFood", back_populates="food", cascade="all, delete-orphan")


class Meal(Base):
    __tablename__ = 'meals'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)

    meal_food_items = relationship('MealFood', back_populates='meal', cascade='all, delete-orphan')

class MealFood(Base):
    __tablename__ = 'meal_food'

    meal_id = Column(Integer, ForeignKey('meals.id'), primary_key=True)
    food_id = Column(Integer, ForeignKey('foods.id'), primary_key=True)
    multiplier = Column(Float, nullable=False)

    meal = relationship('Meal', back_populates='meal_food_items')
    food = relationship('Food', back_populates='meal_food_items')

class DailyPlan(Base):
    __tablename__ = 'daily_plans'

    id            = Column(Integer, primary_key=True, index=True)
    date          = Column(Date,   nullable=False)
    user_id         = Column(Integer, ForeignKey('users.id'), nullable=True)   # ← FK to users.id
    meals         = Column(String, nullable=False)   # e.g. "Chicken x2; Salad x1"
    calories      = Column(Float,  nullable=False)
    protein       = Column(Float,  nullable=False)
    carbs         = Column(Float,  nullable=False)
    fat_regular   = Column(Float,  nullable=False)
    fat_saturated = Column(Float,  nullable=False)
    sodium        = Column(Float,  nullable=False)

    user = relationship("User", back_populates="daily_plans")