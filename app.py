import streamlit as st
import pandas as pd
from sqlalchemy.orm import joinedload
from db import init_db, SessionLocal
from models import Food as FoodModel, Meal as MealModel, MealFood as MealFoodModel
from foods import Food as FoodService
from meals import Meal as MealService

st.set_page_config(layout='wide')

def main():
    # Initialize DB and tables
    init_db()
    st.title("Meal Planning and Food Logging (PostgreSQL)")

    tabs = st.tabs([
        "Log Food", "View Foods", "Create Meal", "View Meals", "Delete Food"
    ])
    tab1, tab2, tab3, tab4, tab5 = tabs

    # Utility: Load foods
    def load_logged_foods():
        db = SessionLocal()
        foods = db.query(FoodModel).all()
        db.close()
        return pd.DataFrame([{
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

    # Utility: Load meals with eager relationships
    def load_logged_meals():
        db = SessionLocal()
        meals = db.query(MealModel).options(
            joinedload(MealModel.meal_food_items).joinedload(MealFoodModel.food)
        ).all()
        rows = []
        for m in meals:
            foods_list = [f"{mf.multiplier}x {mf.food.name}" for mf in m.meal_food_items]
            # Calculate totals directly
            totals = {'calories':0,'protein':0,'carbs':0,'fat_regular':0,'fat_saturated':0,'sodium':0}
            for mf in m.meal_food_items:
                totals['calories'] += mf.food.calories * mf.multiplier
                totals['protein']  += mf.food.protein  * mf.multiplier
                totals['carbs']    += mf.food.carbs    * mf.multiplier
                totals['fat_regular']   += mf.food.fat_regular   * mf.multiplier
                totals['fat_saturated'] += mf.food.fat_saturated * mf.multiplier
                totals['sodium']  += mf.food.sodium  * mf.multiplier

            rows.append({
                'Meal Name': m.name,
                'Food Names': "\n".join(foods_list),
                'Total Calories': totals['calories'],
                'Total Protein': totals['protein'],
                'Total Carbs': totals['carbs'],
                'Total Fat (Regular)': totals['fat_regular'],
                'Total Fat (Saturated)': totals['fat_saturated'],
                'Total Sodium': totals['sodium']
            })
        db.close()
        return pd.DataFrame(rows)

    # Tab1: Log Food
    with tab1:
        with st.form(key='food_form'):
            name       = st.text_input("Name")
            label      = st.text_input("Label")
            measurement= st.text_input("Measurement")
            calories   = st.number_input("Calories", min_value=0.0)
            protein    = st.number_input("Protein", min_value=0.0)
            carbs      = st.number_input("Carbs", min_value=0.0)
            fat_sat    = st.number_input("Fat Saturated", min_value=0.0)
            fat_reg    = st.number_input("Fat Regular", min_value=0.0)
            sodium     = st.number_input("Sodium", min_value=0.0)
            submit     = st.form_submit_button("Log Food")
        if submit:
            if not name.strip() or not label.strip() or not measurement.strip():
                st.error("Name, Label and Measurement cannot be empty.")
            else:
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
        meal_name = st.text_input("Meal Name", key='meal_name')
        selected  = st.multiselect("Select Foods", df_foods['Name'].unique())
        meal_data = []
        for food in selected:
            info = df_foods[df_foods['Name']==food].iloc[0]
            mult = st.number_input(f"{food} multiplier", min_value=0.1, step=0.1, key=f"mult_{food}")
            meal_data.append((food, info['Label'], mult))
        if st.button("Create Meal"):
            if not meal_name.strip():
                st.error("Meal name cannot be empty.")
            elif not meal_data:
                st.error("Select at least one food.")
            else:
                err = MealService(meal_name).create_meal(meal_data)
                if err:
                    st.error(err)
                else:
                    st.success(f"Meal '{meal_name}' created.")

    # Tab4: View Meals
    with tab4:
        df_meals = load_logged_meals()
        if not df_meals.empty:
            st.dataframe(df_meals, use_container_width=True)
        else:
            st.write("No meals found.")

    # Tab5: Delete Food
    with tab5:
        st.header("Delete a Food")
        del_name  = st.text_input("Name of food to delete", key='del_name')
        del_label = st.text_input("Label of food to delete", key='del_label')
        if st.button("Delete Food"):
            if not del_name.strip() or not del_label.strip():
                st.error("Name and Label are required for deletion.")
            else:
                msg = FoodService.delete_food(del_name, del_label)
                if "deleted successfully" in msg:
                    st.success(msg)
                else:
                    st.error(msg)

if __name__ == '__main__':
    main()