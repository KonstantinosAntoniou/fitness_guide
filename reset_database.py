from db import get_db, Base, engine
from models import Food, Meal, MealFood, DailyPlan

def reset_all():
    with get_db() as db:
        # Optional: Delete child tables first to avoid FK errors
        db.query(MealFood).delete()
        db.query(Meal).delete()
        db.query(Food).delete()
        db.query(DailyPlan).delete()
        db.commit()

    print("✅ All records deleted. Database is now clean.")

if __name__ == "__main__":
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_all()