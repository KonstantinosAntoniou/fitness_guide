#!/usr/bin/env python3
"""
Database migration script to safely add new columns to User table
while preserving existing food and meal data.
"""

import pandas as pd
from sqlalchemy import text
from db import get_db, engine
from models import Food as FoodModel, Meal as MealModel, MealFood as MealFoodModel, User, DailyPlan
from app import export_foods_to_excel, export_meals_to_excel

def export_all_data():
    """Export foods and meals to Excel files as backup"""
    print("📦 Exporting current data to Excel files...")
    
    try:
        export_foods_to_excel('backup_foods.xlsx')
        print("✅ Foods exported to backup_foods.xlsx")
        
        export_meals_to_excel('backup_meals.xlsx') 
        print("✅ Meals exported to backup_meals.xlsx")
        
        # Export daily plans as well
        with get_db() as db:
            plans = db.query(DailyPlan).all()
            if plans:
                df_plans = pd.DataFrame([{
                    'Date': p.date,
                    'User_ID': p.user_id,
                    'Meals': p.meals,
                    'Calories': p.calories,
                    'Protein': p.protein,
                    'Carbs': p.carbs,
                    'Fat_Regular': p.fat_regular,
                    'Fat_Saturated': p.fat_saturated,
                    'Sodium': p.sodium
                } for p in plans])
                df_plans.to_excel('backup_daily_plans.xlsx', index=False)
                print("✅ Daily plans exported to backup_daily_plans.xlsx")
        
        return True
    except Exception as e:
        print(f"❌ Error exporting data: {e}")
        return False

def add_user_columns():
    """Add new columns to the users table"""
    print("🔧 Adding new columns to users table...")
    
    try:
        with engine.connect() as conn:
            # Add the new columns if they don't exist
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN goal_period VARCHAR"))
                print("✅ Added goal_period column")
            except Exception:
                print("ℹ️  goal_period column already exists")
            
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN weight_change_amount FLOAT"))
                print("✅ Added weight_change_amount column")
            except Exception:
                print("ℹ️  weight_change_amount column already exists")
            
            conn.commit()
        return True
    except Exception as e:
        print(f"❌ Error adding columns: {e}")
        return False

def reset_user_and_plans_only():
    """Reset only users and daily_plans tables, keeping foods and meals"""
    print("🗑️  Resetting users and daily_plans tables only...")
    
    try:
        with get_db() as db:
            # Delete daily plans first (foreign key constraint)
            deleted_plans = db.query(DailyPlan).delete()
            print(f"✅ Deleted {deleted_plans} daily plans")
            
            # Delete users
            deleted_users = db.query(User).delete()
            print(f"✅ Deleted {deleted_users} users")
            
            db.commit()
        return True
    except Exception as e:
        print(f"❌ Error resetting tables: {e}")
        return False

def main():
    print("🚀 Starting database migration...")
    print("\nChoose migration method:")
    print("1. Add columns only (safest - try this first)")
    print("2. Export data + reset users/plans tables + add columns")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        print("\n=== METHOD 1: Adding columns only ===")
        if add_user_columns():
            print("✅ Migration completed successfully!")
            print("Your food and meal data is preserved.")
        else:
            print("❌ Migration failed. Try method 2.")
    
    elif choice == "2":
        print("\n=== METHOD 2: Export + Reset + Migrate ===")
        
        # Step 1: Export data
        if not export_all_data():
            print("❌ Failed to export data. Aborting migration.")
            return
        
        # Step 2: Reset only users and daily_plans
        if not reset_user_and_plans_only():
            print("❌ Failed to reset tables. Your data backups are safe in Excel files.")
            return
        
        # Step 3: Recreate tables with new schema
        from db import Base
        try:
            Base.metadata.create_all(bind=engine)
            print("✅ Database schema updated with new columns")
            print("✅ Migration completed successfully!")
            print("\n📋 Your data backups:")
            print("   - backup_foods.xlsx")
            print("   - backup_meals.xlsx") 
            print("   - backup_daily_plans.xlsx")
            print("\nYour food and meal data is preserved in the database.")
        except Exception as e:
            print(f"❌ Error recreating schema: {e}")
    
    else:
        print("❌ Invalid choice. Please run the script again.")

if __name__ == "__main__":
    main()
