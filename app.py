import streamlit as st
import pandas as pd
from db import init_db, SessionLocal
from models import Food as FoodModel, Meal as MealModel
from foods import Food as FoodService
from meals import Meal as MealService

st.set_page_config(layout='wide')

# Initialize database and tables
def main():
    init_db()
    st.title("Meal Planning and Food Logging (PostgreSQL)")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Log a Food", "View Foods", "Create Meal", "View Meals"
    ])

    # Utility: Load foods into DataFrame
    def load_logged_foods():
        db = SessionLocal()
        foods = db.query(FoodModel).all()
        db.close()
        df = pd.DataFrame([{
            'Name': f.name,
            'Label': f.label,
            'Measurement': f.measurement,
            'Calories': f.calories,
            'Protein': f.protein,
            'Carbs': f.carbs,
            'Fat_Saturated': f.fat_saturated,
            'Fat_Regular': f.fat_regular,
            'Sodium': f.sodium
        } for f in foods])
        return df

    # Utility: Load meals into DataFrame
    def load_logged_meals():
        db = SessionLocal()
        meals = db.query(MealModel).all()
        db.close()
        rows = []
        for m in meals:
            macros = MealService(m.name).get_meal_macros(m.name)
            foods_list = [f"{mf.multiplier}x {mf.food.name}" for mf in m.meal_food_items]
            rows.append({
                'Meal Name': m.name,
                'Food Names': "\n".join(foods_list),
                'Total Calories': macros.get('calories',0),
                'Total Protein': macros.get('protein',0),
                'Total Carbs': macros.get('carbs',0),
                'Total Fat (Regular)': macros.get('fat_regular',0),
                'Total Fat (Saturated)': macros.get('fat_saturated',0),
                'Total Sodium': macros.get('sodium',0)
            })
        return pd.DataFrame(rows)

    # Tab1: Log Food
    with tab1:
        with st.form(key='food_form'):
            name = st.text_input("Name")
            label = st.text_input("Label")
            measurement = st.text_input("Measurement")
            calories = st.number_input("Calories", min_value=0.0)
            protein = st.number_input("Protein", min_value=0.0)
            carbs = st.number_input("Carbs", min_value=0.0)
            fat_sat = st.number_input("Fat Saturated", min_value=0.0)
            fat_reg = st.number_input("Fat Regular", min_value=0.0)
            sodium = st.number_input("Sodium", min_value=0.0)
            submit = st.form_submit_button("Log Food")
        if submit:
            msg = FoodService(name,label,measurement,calories,protein,carbs,fat_sat,fat_reg,sodium).log_food()
            if "logged" in msg:
                st.success(msg)
            else:
                st.error(msg)

    # Tab2: View Foods
    with tab2:
        df_foods = load_logged_foods()
        if not df_foods.empty:
            st.dataframe(df_foods, use_container_width=True)
        else:
            st.write("No foods found.")

    # Tab3: Create Meal
    with tab3:
        df_foods = load_logged_foods()
        name = st.text_input("Meal Name", key='meal_name')
        selected = st.multiselect("Select Foods", df_foods['Name'].unique())
        meal_data = []
        for food in selected:
            info = df_foods[df_foods['Name']==food].iloc[0]
            mult = st.number_input(f"{food} multiplier", min_value=0.1, step=0.1, key=f"mult_{food}")
            meal_data.append((food, info['Label'], mult))
        if st.button("Create Meal"):
            err = MealService(name).create_meal(meal_data)
            if err:
                st.error(err)
            else:
                st.success(f"Meal '{name}' created.")

    # Tab4: View Meals
    with tab4:
        df_meals = load_logged_meals()
        if not df_meals.empty:
            st.dataframe(df_meals, use_container_width=True)
        else:
            st.write("No meals found.")

if __name__ == '__main__':
    main()