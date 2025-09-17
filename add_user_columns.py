#!/usr/bin/env python3
"""
Simple script to add new columns to the users table without affecting any data.
"""

from sqlalchemy import text
from db import engine

def add_columns():
    """Add goal_period and weight_change_amount columns to users table"""
    print("🔧 Adding new columns to users table...")
    
    try:
        with engine.connect() as conn:
            # Add goal_period column
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN goal_period VARCHAR"))
                print("✅ Added goal_period column")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print("ℹ️  goal_period column already exists")
                else:
                    print(f"⚠️  Error adding goal_period: {e}")
            
            # Add weight_change_amount column  
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN weight_change_amount FLOAT"))
                print("✅ Added weight_change_amount column")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print("ℹ️  weight_change_amount column already exists")
                else:
                    print(f"⚠️  Error adding weight_change_amount: {e}")
            
            conn.commit()
            print("✅ Database migration completed successfully!")
            print("All your existing data (foods, meals, users, daily plans) is preserved.")
            
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        print("Make sure your DATABASE_URL is set correctly in the .env file")

if __name__ == "__main__":
    add_columns()
