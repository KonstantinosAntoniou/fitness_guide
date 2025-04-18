import pandas as pd
from db import SessionLocal, init_db, get_db

from models import Food as FoodModel, Meal as MealModel, MealFood as MealFoodMeal

def load_foods(excel_path: str = 'foods_log.xlsx'):

    df = pd.read_excel(excel_path)
    with get_db() as session:
        for index, row  in df.iterrows():
            existing = session.query(FoodModel).filter(
                FoodModel.name.ilike(row['Name']),
                FoodModel.label.ilike(row['Label'])
            ).first()
            if not existing:
                new_food = FoodModel(
                    name=row['Name'],
                    label=row['Label'],
                    measurement=row['Measurement'],
                    calories=row['Calories'],
                    protein=row['Protein'],
                    carbs=row['Carbs'],
                    fat_saturated=row['Fat_Saturated'],
                    fat_regular=row['Fat_Regular'],
                    sodium=row['Sodium']
                )
                session.add(new_food)
        
        session.commit()
        print("Foods loaded from Excel file.")

def load_meals(excel_path: str = 'meals_log.xlsx'):
    df = pd.read_excel(excel_path)
    grouped = df.groupby('Meal_Name')
    with get_db() as session:
        for meal_name, group in grouped:
            meal = MealModel(name=meal_name)
            session.add(meal)
            session.flush()

            foods = group[~group['Food_Name'].str.contains('Total')]

            for index, row in foods.iterrows():
                mult, food_name = row['Food_Name'].split('x', 1)
                multiplier = float(mult)
                label = row['Label']
                food = session.query(FoodModel).filter(
                    FoodModel.name.ilike(food_name),
                    FoodModel.label.ilike(label)
                ).first()
                if food:
                    meal_food = MealFoodMeal(
                        meal_id=meal.id,
                        food_id=food.id,
                        multiplier=multiplier
                    )
                    session.add(meal_food)
        session.commit()
        print("Meals loaded from Excel file.")

def main():
    init_db()
    load_foods()
    load_meals()
    print("Data migraded from Excel to database.")

if __name__ == "__main__":
    main()
