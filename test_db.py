from db import init_db, SessionLocal
from models import Food


init_db()

db = SessionLocal() 

test_food = Food(
    name="Test Food",
    label="Test Label",
    measurement="Test Measurement",
    calories=100,
    protein=10,
    carbs=20,
    fat_saturated=5,
    fat_regular=5,
    sodium=100
)

db.add(test_food)
db.commit()
print("Test food added to the database.")   

foods = db.query(Food).all()
print(f"Foods in database: {[f.name for f in foods]}")
print(f"Test food ID: {[f.id for f in foods]}")

db.close()