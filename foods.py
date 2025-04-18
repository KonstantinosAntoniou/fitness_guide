from sqlalchemy.orm import Session
from db import SessionLocal
from models import Food as FoodModel

class Food:
    def __init__(self, name: str, label: str, measurement: str,
                 calories: float, protein: float, carbs: float,
                 fat_saturated: float, fat_regular: float, sodium: float):
        self.name = name
        self.label = label
        self.measurement = measurement
        self.calories = calories
        self.protein = protein
        self.carbs = carbs
        self.fat_saturated = fat_saturated
        self.fat_regular = fat_regular
        self.sodium = sodium
        self.db: Session = SessionLocal()

    def log_food(self) -> str:
        exists = self.db.query(FoodModel).filter(
            FoodModel.name.ilike(self.name),
            FoodModel.label.ilike(self.label)
        ).first()
        if exists:
            return f"{self.name} ({self.label}) already exists in database."

        new_food = FoodModel(
            name=self.name,
            label=self.label,
            measurement=self.measurement,
            calories=self.calories,
            protein=self.protein,
            carbs=self.carbs,
            fat_saturated=self.fat_saturated,
            fat_regular=self.fat_regular,
            sodium=self.sodium
        )
        self.db.add(new_food)
        self.db.commit()
        return f"{self.name} ({self.label}) logged successfully to database!"

    def get_all_foods(self):
        return self.db.query(FoodModel).all()