import streamlit as st
import pandas as pd
import os
from db import init_db, SessionLocal
from models import Food as FoodModel, Meal as MealModel
from foods import Food as FoodService
from meals import Meal as MealService
from sqlalchemy.orm import joinedload
from models import MealFood as MealFoodModel

st.set_page_config(layout='wide')

def main():
    # ─── Initialize Database ─────────────────────────────────────────────────────
    init_db()
    st.title("🚀 Fitness Tracker & Planner (PostgreSQL)")

    # ─── Tabs Setup ───────────────────────────────────────────────────────────────
    tab_calc, tab_log, tab_view, tab_create, tab_view_meals, tab_planner, tab_daily = st.tabs([
        "Calculator",
        "Log/Delete Food",
        "View Foods",
        "Create Meal",
        "View Meals",
        "Daily Planner",
        "Saved Day Plans"
    ])

    # ─── Utilities ────────────────────────────────────────────────────────────────
    def load_logged_foods() -> pd.DataFrame:
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
            'Fat_Regular': f.fat_regular,
            'Fat_Saturated': f.fat_saturated,
            'Sodium': f.sodium
        } for f in foods])

    def load_logged_meals() -> pd.DataFrame:
        db = SessionLocal()
        meals = (
        db.query(MealModel)
          .options(
             joinedload(MealModel.meal_food_items)
               .joinedload(MealFoodModel.food)
          )
          .all()
        )
        rows = []
        for m in meals:
            svc = MealService(m.name)
            macros = svc.get_meal_macros(m.name)
            foods_list = [f"{mf.multiplier}x {mf.food.name}" for mf in m.meal_food_items]
            rows.append({
                'Meal Name': m.name,
                'Food Names': "\n".join(foods_list),
                'Calories': macros.get('calories', 0),
                'Protein': macros.get('protein', 0),
                'Carbs': macros.get('carbs', 0),
                'Fat_Regular': macros.get('fat_regular', 0),
                'Fat_Saturated': macros.get('fat_saturated', 0),
                'Sodium': macros.get('sodium', 0),
            })
        db.close()
        return pd.DataFrame(rows)

    # ─── Tab 1: BMR, TDEE & BMI Calculator ────────────────────────────────────────
    with tab_calc:
        st.header("⚖️ BMR, TDEE & BMI Calculator")
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Age (years)", min_value=0, max_value=120, step=1)
            sex = st.selectbox("Sex", ("Male", "Female"))
            weight = st.number_input("Weight (kg)", min_value=0.0, step=0.1)
        with col2:
            height_cm = st.number_input("Height (cm)", min_value=0.0, step=0.1)
            activity_levels = {
                "Sedentary (little/no exercise)": 1.2,
                "Lightly active (1–3 days/week)": 1.375,
                "Moderately active (3–5 days/week)": 1.55,
                "Very active (6–7 days/week)": 1.725,
                "Extra active (hard physical work)": 1.9
            }
            activity = st.selectbox("Activity Level", list(activity_levels.keys()))

        if st.button("Calculate BMR & TDEE"):
            h_m = height_cm / 100 if height_cm > 0 else 0
            bmi = weight / (h_m**2) if h_m > 0 else 0

            # Harris-Benedict
            if sex == "Male":
                bmr_hb = 88.362 + (13.397 * weight) + (4.799 * height_cm) - (5.677 * age)
            else:
                bmr_hb = 447.593 + (9.247 * weight) + (3.098 * height_cm) - (4.330 * age)

            # Mifflin-St Jeor
            if sex == "Male":
                bmr_ms = (10 * weight) + (6.25 * height_cm) - (5 * age) + 5
            else:
                bmr_ms = (10 * weight) + (6.25 * height_cm) - (5 * age) - 161

            factor = activity_levels[activity]
            tdee_hb = bmr_hb * factor
            tdee_ms = bmr_ms * factor

            st.markdown(f"""
            **BMI:** {bmi:.2f}  
            **BMR (Harris‑Benedict):** {bmr_hb:.0f} kcal/day  
            **BMR (Mifflin‑St Jeor):** {bmr_ms:.0f} kcal/day  
            **TDEE (HB):** {tdee_hb:.0f} kcal/day  
            **TDEE (MSJ):** {tdee_ms:.0f} kcal/day
            """)

        st.subheader("🎯 Calorie Goal for Weight Change")
        goal          = st.selectbox("Goal",             ("Lose weight", "Gain weight"))
        weight_change = st.number_input("Weight change (kg)", min_value=0.0, step=0.1)
        period        = st.selectbox("Period",           ("Per week", "Per month", "Per year"))
        if st.button("Calculate Calorie Goal"):
            # 1) Recalculate BMR & TDEE from current inputs
            h_m = height_cm / 100 if height_cm > 0 else 0

            if sex == "Male":
                bmr_hb = 88.362 + (13.397 * weight) + (4.799 * height_cm) - (5.677 * age)
                bmr_ms = (10 * weight) + (6.25 * height_cm) - (5 * age) + 5
            else:
                bmr_hb = 447.593 + (9.247 * weight) + (3.098 * height_cm) - (4.330 * age)
                bmr_ms = (10 * weight) + (6.25 * height_cm) - (5 * age) - 161

            factor  = activity_levels[activity]
            tdee_hb = bmr_hb * factor
            tdee_ms = bmr_ms * factor

            # 2) Compute the daily calorie adjustment
            days_map  = {"Per week": 7, "Per month": 30, "Per year": 365}
            days      = days_map[period]
            # ~7700 kcal per kg of bodyweight
            cal_adjust = (weight_change * 7700) / days

            if goal == "Lose weight":
                target_hb = tdee_hb - cal_adjust
                target_ms = tdee_ms - cal_adjust
            else:
                target_hb = tdee_hb + cal_adjust
                target_ms = tdee_ms + cal_adjust

            st.markdown(f"""
            To **{goal.lower()} {weight_change} kg {period.lower()},**  
            • Target (HB): **{target_hb:.0f} kcal/day**  
            • Target (MSJ): **{target_ms:.0f} kcal/day**
            """)

    # ─── Tab 2: Log/Delete Food ───────────────────────────────────────────────────
    with tab_log:
        st.header("➕ Log or ❌ Delete Food")
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

            col1, col2 = st.columns(2)
            submit = col1.form_submit_button("Log Food")
            delete = col2.form_submit_button("Delete Food")

        if submit:
            if not name.strip() or not label.strip() or not measurement.strip():
                st.error("Name, Label, and Measurement cannot be empty.")
            else:
                msg = FoodService(
                    name, label, measurement,
                    calories, protein, carbs,
                    fat_sat, fat_reg, sodium
                ).log_food()
                st.success(msg) if "logged" in msg else st.error(msg)

        if delete:
            db = SessionLocal()
            food = db.query(FoodModel).filter(
                FoodModel.name.ilike(name),
                FoodModel.label.ilike(label)
            ).first()
            if food:
                db.delete(food)
                db.commit()
                st.success(f"Deleted {name} ({label}) from database.")
            else:
                st.error("Food not found.")
            db.close()

    # ─── Tab 3: View Foods ────────────────────────────────────────────────────────
    with tab_view:
        st.header("📋 Logged Foods")
        df_foods = load_logged_foods()
        if df_foods.empty:
            st.write("No foods found.")
        else:
            st.dataframe(df_foods, use_container_width=True)

    # ─── Tab 4: Create Meal ──────────────────────────────────────────────────────
    with tab_create:
        st.header("🥗 Create Meal")
        df_foods = load_logged_foods()
        meal_name = st.text_input("Meal Name", key='meal_name')
        selected = st.multiselect("Select Foods", df_foods['Name'].unique())
        meal_data = []
        for food in selected:
            info = df_foods[df_foods['Name'] == food].iloc[0]
            mult = st.number_input(
                f"{food} multiplier",
                min_value=0.1, step=0.1,
                key=f"mult_{food}"
            )
            meal_data.append((food, info['Label'], mult))

        if st.button("Create Meal"):
            if not meal_name.strip():
                st.error("Meal name cannot be empty.")
            else:
                err = MealService(meal_name).create_meal(meal_data)
                st.success(f"Meal '{meal_name}' created!") if err is None else st.error(err)

    # ─── Tab 5: View Meals ───────────────────────────────────────────────────────
    with tab_view_meals:
        st.header("📋 Logged Meals")
        df_meals = load_logged_meals()
        if df_meals.empty:
            st.write("No meals found.")
        else:
            df_meals['Food Names'] = df_meals['Food Names'].str.replace("\n", "<br>")
            st.markdown(df_meals.to_html(escape=False, index=False), unsafe_allow_html=True)

    # ─── Tab 6: Daily Planner ────────────────────────────────────────────────────
    with tab_planner:
        st.header("🍽️ Daily Meal Planner")
        df_foods = load_logged_foods()
        df_meals = load_logged_meals()

        num_meals = st.number_input("Meals per day", min_value=1, max_value=10, value=5, step=1)
        plan_items = []
        totals = {
            'Calories': 0, 'Protein': 0, 'Carbs': 0,
            'Fat_Regular': 0, 'Fat_Saturated': 0, 'Sodium': 0
        }

        for i in range(int(num_meals)):
            st.subheader(f"Meal {i+1}")
            choice = st.radio("Add", ("Food", "Meal"), key=f"choice_{i}")
            if choice == "Food":
                food_sel = st.selectbox("Select food", df_foods['Name'].unique(), key=f"food_{i}")
                mult = st.number_input("Portion multiplier", min_value=0.1, step=0.1, key=f"mult_{i}")
                if food_sel:
                    info = df_foods[df_foods['Name'] == food_sel].iloc[0]
                    totals['Calories']     += info['Calories'] * mult
                    totals['Protein']      += info['Protein'] * mult
                    totals['Carbs']        += info['Carbs'] * mult
                    totals['Fat_Regular']  += info['Fat_Regular'] * mult
                    totals['Fat_Saturated']+= info['Fat_Saturated'] * mult
                    totals['Sodium']       += info['Sodium'] * mult
                    plan_items.append(f"{food_sel} x{mult}")
            else:
                meal_sel = st.selectbox("Select meal", df_meals['Meal Name'].unique(), key=f"meal_{i}")
                if meal_sel:
                    macros = MealService(meal_sel).get_meal_macros(meal_sel)
                    totals['Calories']     += macros.get('calories', 0)
                    totals['Protein']      += macros.get('protein', 0)
                    totals['Carbs']        += macros.get('carbs', 0)
                    totals['Fat_Regular']  += macros.get('fat_regular', 0)
                    totals['Fat_Saturated']+= macros.get('fat_saturated', 0)
                    totals['Sodium']       += macros.get('sodium', 0)
                    plan_items.append(meal_sel)

        if st.button("Calculate Total Macros"):
            st.write("## Total Macros for Today")
            for k, v in totals.items():
                st.write(f"**{k.replace('_',' ')}:** {v:.2f}")

        if st.button("Save This Day’s Plan"):
            record = {
                'Date': pd.Timestamp.today().strftime('%Y-%m-%d'),
                'Plan': "; ".join(plan_items),
                'Calories': totals['Calories'],
                'Protein': totals['Protein'],
                'Carbs': totals['Carbs'],
                'Fat_Regular': totals['Fat_Regular'],
                'Fat_Saturated': totals['Fat_Saturated'],
                'Sodium': totals['Sodium']
            }
            file = 'daily_meal_plans.xlsx'
            if os.path.exists(file):
                df_exist = pd.read_excel(file)
                df_exist = df_exist.append(record, ignore_index=True)
            else:
                df_exist = pd.DataFrame([record])
            df_exist.to_excel(file, index=False)
            st.success("Day plan saved!")

    # ─── Tab 7: Saved Day Plans ──────────────────────────────────────────────────
    with tab_daily:
        st.header("📆 Saved Daily Plans")
        file = 'daily_meal_plans.xlsx'
        if os.path.exists(file):
            df_plans = pd.read_excel(file)
            if df_plans.empty:
                st.write("No saved plans.")
            else:
                st.dataframe(df_plans, use_container_width=True)
        else:
            st.write("No saved plans yet.")

if __name__ == '__main__':
    main()
