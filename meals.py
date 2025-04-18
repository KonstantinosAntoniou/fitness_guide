from sqlalchemy.orm import Session
from db import SessionLocal
from models import Meal as MealModel, Food as FoodModel, MealFood as MealFoodModel

class Meal:
    def __init__(self, name: str):
        self.name = name
        self.db: Session = SessionLocal()

    def create_meal(self, foods: list[tuple[str, str, float]]) -> str | None:
        existing = self.db.query(MealModel).filter(MealModel.name.ilike(self.name)).first()
        if existing:
            return f"Meal '{self.name}' already exists."

        meal = MealModel(name=self.name)
        self.db.add(meal)
        self.db.flush()

        for food_name, label, multiplier in foods:
            food = self.db.query(FoodModel).filter(
                FoodModel.name.ilike(food_name),
                FoodModel.label.ilike(label)
            ).first()
            if not food:
                return f"Food '{food_name}' with label '{label}' not found in database."

            assoc = MealFoodModel(
                meal_id=meal.id,
                food_id=food.id,
                multiplier=multiplier
            )
            self.db.add(assoc)

        self.db.commit()
        return None

    def get_meal_macros(self, meal_name: str) -> dict:
        meal = self.db.query(MealModel).filter(MealModel.name.ilike(meal_name)).first()
        if not meal:
            return {}

        total = { 'calories': 0, 'protein': 0, 'carbs': 0, 'fat_saturated': 0, 'fat_regular': 0, 'sodium': 0 }
        for mf in meal.meal_food_items:
            total['calories'] += mf.food.calories * mf.multiplier
            total['protein']  += mf.food.protein * mf.multiplier
            total['carbs']    += mf.food.carbs * mf.multiplier
            total['fat_saturated'] += mf.food.fat_saturated * mf.multiplier
            total['fat_regular']   += mf.food.fat_regular * mf.multiplier
            total['sodium']  += mf.food.sodium * mf.multiplier
        return total
