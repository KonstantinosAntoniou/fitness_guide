from sqlalchemy.orm import Session
from db import SessionLocal
from models import Meal as MealModel, Food as FoodModel, MealFood as MealFoodModel
from db import get_db
from sqlalchemy.orm import relationship, joinedload

class Meal:
    def __init__(self, name: str):
        self.name = name

    def create_meal(self, foods: list[tuple[str, str, float]]) -> str | None:
        with get_db() as db:
            existing = db.query(MealModel).filter(MealModel.name.ilike(self.name)).first()
            if existing:
                return f"Meal '{self.name}' already exists."
            meal = MealModel(name=self.name)
            db.add(meal)
            db.flush()
            for food_name, label, multiplier in foods:
                f = db.query(FoodModel).filter(
                    FoodModel.name.ilike(food_name),
                    FoodModel.label.ilike(label)
                ).first()
                if not f:
                    return f"Food '{food_name}' ({label}) not found."
                db.add(MealFoodModel(meal_id=meal.id, food_id=f.id, multiplier=multiplier))
            db.commit()
        return None

    def get_meal_macros(self, meal_name: str) -> dict:
        totals = {
            'calories':      0.0,
            'protein':       0.0,
            'carbs':         0.0,
            'fat_saturated': 0.0,
            'fat_regular':   0.0,
            'sodium':        0.0
        }
        with get_db() as db:
            meal = (
                db.query(MealModel)
                  .options(
                      joinedload(MealModel.meal_food_items)
                        .joinedload(MealFoodModel.food)
                  )
                  .filter(MealModel.name.ilike(meal_name))
                  .first()
            )
            if not meal:
                return totals

            for mf in meal.meal_food_items:
                f = mf.food
                mul = mf.multiplier
                totals['calories']      += f.calories      * mul
                totals['protein']       += f.protein       * mul
                totals['carbs']         += f.carbs         * mul
                totals['fat_saturated'] += f.fat_saturated * mul
                totals['fat_regular']   += f.fat_regular   * mul
                totals['sodium']        += f.sodium        * mul

        return totals