import streamlit as st
import pandas as pd
import os
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from db import init_db, SessionLocal, get_db
from models import Food as FoodModel, Meal as MealModel, MealFood as MealFoodModel, DailyPlan, User
from foods import Food as FoodService
from meals import Meal as MealService
from openai import OpenAI
from openai import OpenAIError
from datetime import date


def update_daily_plans_for_food(food_name: str):
    """
    Recalculate all DailyPlan totals for plans whose 'meals' string mentions this food.
    """
    from db import get_db
    with get_db() as db:
        plans = db.query(DailyPlan) \
                  .filter(DailyPlan.meals.ilike(f"%{food_name}%")) \
                  .all()

        for plan in plans:
            items = [item.strip() for item in plan.meals.split(";")]
            totals = {
                'calories': 0.0,
                'protein': 0.0,
                'carbs': 0.0,
                'fat_regular': 0.0,
                'fat_saturated': 0.0,
                'sodium': 0.0
            }
            for item in items:
                if " x" in item:
                    # it's a food entry like "Chicken x2.0"
                    name_part, mult_part = item.rsplit(" x", 1)
                    try:
                        mult = float(mult_part)
                        f = db.query(FoodModel).filter(FoodModel.name == name_part).first()
                        if f:
                            totals['calories']      += f.calories * mult
                            totals['protein']       += f.protein  * mult
                            totals['carbs']         += f.carbs    * mult
                            totals['fat_regular']   += f.fat_regular   * mult
                            totals['fat_saturated'] += f.fat_saturated * mult
                            totals['sodium']        += f.sodium   * mult
                    except:
                        continue
                else:
                    # it's a meal name
                    m = db.query(MealModel).filter(MealModel.name == item).first()
                    if m:
                        macros = MealService(m.name).get_meal_macros(m.name)
                        totals['calories']      += macros.get('calories', 0)
                        totals['protein']       += macros.get('protein',  0)
                        totals['carbs']         += macros.get('carbs',    0)
                        totals['fat_regular']   += macros.get('fat_regular',   0)
                        totals['fat_saturated'] += macros.get('fat_saturated', 0)
                        totals['sodium']        += macros.get('sodium',   0)

            # write back to plan
            plan.calories      = totals['calories']
            plan.protein       = totals['protein']
            plan.carbs         = totals['carbs']
            plan.fat_regular   = totals['fat_regular']
            plan.fat_saturated = totals['fat_saturated']
            plan.sodium        = totals['sodium']

        db.commit()


# Load OpenAI key from env
client = OpenAI()
if not client.api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

st.set_page_config(layout='wide')

def main():
    # ─── Initialize DB ───────────────────────────────────────────────
    init_db()
    st.title("🚀 Fitness Tracker & Planner")

    # ─── Tabs ────────────────────────────────────────────────────────
    tabs = st.tabs([
        "Calculator",
        "Log/Delete Food",
        "View Foods",
        "Create Meal",
        "Manage Meals",
        "View Meals",
        "Daily Planner",
        "Saved Day Plans",
        "ChatGPT"
    ])
    (tab_calc, tab_log, tab_view,
     tab_create, tab_manage_meals,
     tab_view_meals,
     tab_planner, tab_daily,
     tab_chat) = tabs

    # ─── Utils ───────────────────────────────────────────────────────
    def load_logged_foods() -> pd.DataFrame:
        from db import get_db
        with get_db() as db:
            foods = db.query(FoodModel).all()
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
        from db import get_db
        with get_db() as db:
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
                    'Protein':  macros.get('protein',  0),
                    'Carbs':    macros.get('carbs',    0),
                    'Fat_Regular':   macros.get('fat_regular',   0),
                    'Fat_Saturated': macros.get('fat_saturated', 0),
                    'Sodium':   macros.get('sodium',   0),
                })
            return pd.DataFrame(rows)


    # ─── Tab 1: Calculator ────────────────────────────────────────────
    with tab_calc:
        st.header("⚖️ BMR, TDEE & BMI Calculator")
        st.subheader("👤 User Profile (optional)")
        name       = st.text_input("Name", value="")
        age        = st.number_input("Age (years)", min_value=0, max_value=120, step=1)
        sex        = st.selectbox("Sex", ("Male", "Female"))
        weight     = st.number_input("Weight (kg)", min_value=0.0, step=0.1)
        height_cm  = st.number_input("Height (cm)", min_value=0.0, step=0.1)
        activity_levels = {
            "Sedentary (Little to no exercise)":     1.2,
            "Lightly active (1 to 3 Days a week light exercise)":1.375,
            "Moderate (3 to 5 Days a week moderate exercise)":      1.55,
            "Very active (6 to 7 Days a week)":   1.725,
            "Extra active (extremely active / professional athlete)":  1.9
        }
        activity   = st.selectbox("Activity Level", list(activity_levels.keys()))

        if st.button("Calculate BMR & TDEE", key="btn_calc_bmr_tdee"):
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

            factor    = activity_levels[activity]
            tdee_hb   = bmr_hb * factor
            tdee_ms   = bmr_ms * factor

            st.markdown(f"""
            **BMI:** {bmi:.2f}  
            **BMR (Harris‑Benedict):** {bmr_hb:.0f} kcal/day  
            **BMR (Mifflin‑St Jeor):** {bmr_ms:.0f} kcal/day  
            **TDEE (HB):** {tdee_hb:.0f} kcal/day  
            **TDEE (MSJ):** {tdee_ms:.0f} kcal/day
            """)

        st.subheader("🎯 Calorie Goal for Weight Change")
        goal          = st.selectbox("Goal", ("Lose weight", "Gain weight"))
        weight_change = st.number_input("Weight change (kg)", min_value=0.0, step=0.1)
        period        = st.selectbox("Period", ("Per week", "Per month", "Per year"))

        if st.button("Calculate Calorie Goal", key="btn_calc_calorie_goal"):
            # re‑compute TDEE to ensure variables are in scope
            if sex == "Male":
                bmr_hb = 88.362 + (13.397 * weight) + (4.799 * height_cm) - (5.677 * age)
                bmr_ms = (10 * weight) + (6.25 * height_cm) - (5 * age) + 5
            else:
                bmr_hb = 447.593 + (9.247 * weight) + (3.098 * height_cm) - (4.330 * age)
                bmr_ms = (10 * weight) + (6.25 * height_cm) - (5 * age) - 161

            factor  = activity_levels[activity]
            tdee_hb = bmr_hb * factor
            tdee_ms = bmr_ms * factor

            days_map  = {"Per week": 7, "Per month": 30, "Per year": 365}
            days      = days_map[period]
            # ≈7700 kcal per kg
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

        avg_target = (target_hb + target_ms)/2 if 'target_hb' in locals() else None

        if st.button("Save Profile", key="btn_save_profile"):
            if not name.strip():
                st.error("Name cannot be empty.")
            else:
                with get_db() as db:
                    user = db.query(User).filter(User.name == name).first()
                    if not user:
                        user = User(name=name)
                        db.add(user)
                    # update fields
                    user.age            = int(age)
                    user.sex            = sex
                    user.weight_kg      = float(weight)
                    user.height_cm      = float(height_cm)
                    user.activity_level = activity
                    user.bmr_hb         = bmr_hb
                    user.bmr_msj        = bmr_ms
                    user.tdee_hb        = tdee_hb
                    user.tdee_msj       = tdee_ms
                    user.goal_type      = goal       # "Lose weight" or "Gain weight"
                    user.target_calories= float(avg_target) if avg_target else None
                    db.commit()
                st.success(f"Profile for {name} saved.")

        # ─── Tab 2: Log / Edit / Delete Food ────────────────────────────────────
    with tab_log:
        st.header("➕ Log • ✏️ Edit • ❌ Delete Food")

        # 1️⃣ Fetch existing foods
        with get_db() as db:
            foods_list = db.query(FoodModel).all()

        options = ["-- New Food --"] + [f"{f.name} ({f.label})" for f in foods_list]
        choice  = st.selectbox("Select food to edit/delete, or choose New:", options)
        is_new  = (choice == "-- New Food --")

        # 2️⃣ Prefill values
        if is_new:
            name0 = label0 = meas0 = ""
            cal0 = prot0 = carb0 = fsat0 = freg0 = sod0 = 0.0
        else:
            idx  = options.index(choice) - 1
            f0   = foods_list[idx]
            name0, label0, meas0 = f0.name, f0.label, f0.measurement
            cal0, prot0, carb0  = f0.calories, f0.protein, f0.carbs
            fsat0, freg0, sod0  = f0.fat_saturated, f0.fat_regular, f0.sodium

        # 3️⃣ The form itself
        with st.form(key="food_form"):
            name        = st.text_input("Name",        value=name0)
            label       = st.text_input("Label",       value=label0)
            measurement = st.text_input("Measurement", value=meas0)

            calories  = st.number_input("Calories",      value=float(cal0), min_value=0.0)
            protein   = st.number_input("Protein",       value=float(prot0), min_value=0.0)
            carbs     = st.number_input("Carbs",         value=float(carb0), min_value=0.0)
            fat_sat   = st.number_input("Fat Saturated", value=float(fsat0), min_value=0.0)
            fat_reg   = st.number_input("Fat Regular",   value=float(freg0), min_value=0.0)
            sodium    = st.number_input("Sodium",        value=float(sod0), min_value=0.0)

            # Unconditionally include all three, but disable the irrelevant ones
            submit_btn = st.form_submit_button("Log Food", disabled=not is_new)
            update_btn = st.form_submit_button("Update Food", disabled=is_new)
            delete_btn = st.form_submit_button("Delete Food", disabled=is_new)

        # 4️⃣ Handle the actions
        if submit_btn:
            if not name.strip() or not label.strip() or not measurement.strip():
                st.error("Name, Label, and Measurement cannot be empty.")
            else:
                msg = FoodService(
                    name, label, measurement,
                    calories, protein, carbs,
                    fat_sat, fat_reg, sodium
                ).log_food()
                st.success(msg) if "logged" in msg else st.error(msg)

        if update_btn:
            with get_db() as db:
                f_db = db.query(FoodModel).filter(
                    FoodModel.name  == name0,
                    FoodModel.label == label0
                ).first()
                if f_db:
                    f_db.name           = name
                    f_db.label          = label
                    f_db.measurement    = measurement
                    f_db.calories       = float(calories)
                    f_db.protein        = float(protein)
                    f_db.carbs          = float(carbs)
                    f_db.fat_saturated  = float(fat_sat)
                    f_db.fat_regular    = float(fat_reg)
                    f_db.sodium         = float(sodium)
                    db.commit()
                    update_daily_plans_for_food(name0)
                    st.success(f"Updated '{name0} ({label0})'.")
                else:
                    st.error("Original food not found.")

        if delete_btn:
            with get_db() as db:
                f_db = db.query(FoodModel).filter(
                    FoodModel.name  == name0,
                    FoodModel.label == label0
                ).first()
                if f_db:
                    # Delete meals that include this food
                    meals_with = (
                        db.query(MealModel)
                          .join(MealFoodModel)
                          .filter(MealFoodModel.food_id == f_db.id)
                          .all()
                    )
                    for m in meals_with:
                        db.delete(m)
                    db.delete(f_db)
                    db.commit()

                    # Clean up any now‑empty meals
                    empties = (
                        db.query(MealModel)
                          .outerjoin(MealFoodModel)
                          .group_by(MealModel.id)
                          .having(func.count(MealFoodModel.food_id) == 0)
                          .all()
                    )
                    for m in empties:
                        db.delete(m)
                    db.commit()

                    update_daily_plans_for_food(name0)
                    st.success(f"Deleted '{name0} ({label0})' and related meals.")
                else:
                    st.error("Food not found.")



    # ─── Tab 3: View Foods ─────────────────────────────────────────────
    with tab_view:
        st.header("📋 Logged Foods")
        df_foods = load_logged_foods()
        if df_foods.empty:
            st.write("No foods found.")
        else:
            st.dataframe(df_foods, use_container_width=True)

    # ─── Tab 4: Create Meal ────────────────────────────────────────────
    with tab_create:
        st.header("🥗 Create Meal")
        df_foods  = load_logged_foods()
        meal_name = st.text_input("Meal Name", key='meal_name')
        selected  = st.multiselect("Select Foods", df_foods['Name'].unique())

        meal_data = []
        for food in selected:
            info = df_foods[df_foods['Name'] == food].iloc[0]
            mult = st.number_input(
                f"{info['Label']} {food} multiplier ({info['Measurement']})",
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

    with tab_manage_meals:
        st.header("✏️ Manage Meals")

        # 1️⃣ Load all meals with their food associations eagerly
        with get_db() as db:
            meals = (
                db.query(MealModel)
                .options(
                    joinedload(MealModel.meal_food_items)
                        .joinedload(MealFoodModel.food)
                )
                .all()
            )

        meal_names = [m.name for m in meals]
        options     = ["-- New Meal --"] + meal_names
        choice      = st.selectbox("Select meal to edit/delete, or New:", options)
        is_new      = (choice == "-- New Meal --")

        # 2️⃣ Prefill form values
        if not is_new:
            m0            = choice
            meal_instance = next(m for m in meals if m.name == m0)
            foods0        = [
                (mf.food.name, mf.food.label, mf.multiplier)
                for mf in meal_instance.meal_food_items
            ]
        else:
            m0     = ""
            foods0 = []

        new_name = st.text_input("Meal Name", value=m0)
        df_foods = load_logged_foods()

        # 3️⃣ Let user pick foods + multipliers
        selected = st.multiselect("Select Foods", df_foods['Name'].tolist(), default=[f[0] for f in foods0])
        meal_data = []
        for fname in selected:
            lbl = df_foods.loc[df_foods['Name']==fname, 'Label'].iloc[0]
            default_mult = next((mult for (n,l,mult) in foods0 if n==fname), 1.0)
            mult = st.number_input(
                f"{fname} multiplier",
                min_value=0.1, step=0.1,
                value=float(default_mult),
                key=f"mult_{fname}"
            )
            meal_data.append((fname, lbl, mult))

        # 4️⃣ Action buttons (each with unique keys!)
        create_btn = st.button("Create Meal", key="manage_create_meal", disabled=not is_new or not new_name.strip())
        update_btn = st.button("Update Meal", key="manage_update_meal", disabled=is_new or not new_name.strip())
        delete_btn = st.button("Delete Meal", key="manage_delete_meal", disabled=is_new)

        # 5️⃣ Handle Create
        if create_btn:
            err = MealService(new_name).create_meal(meal_data)
            if err:
                st.error(err)
            else:
                st.success(f"Meal '{new_name}' created!")
                st.experimental_rerun()

        # 6️⃣ Handle Update (re-fetch inside session!)
        if update_btn:
            with get_db() as db:
                m_db = db.query(MealModel).filter(MealModel.name == m0).first()
                if m_db:
                    # clear old associations
                    db.query(MealFoodModel).filter(MealFoodModel.meal_id == m_db.id).delete()
                    db.flush()
                    # add new ones
                    for fname, lbl, mult in meal_data:
                        f_db = db.query(FoodModel).filter(
                            FoodModel.name == fname,
                            FoodModel.label == lbl
                        ).first()
                        db.add(MealFoodModel(
                            meal_id    = m_db.id,
                            food_id    = f_db.id,
                            multiplier = mult
                        ))
                    # rename if changed
                    m_db.name = new_name
                    db.commit()
                    st.success(f"Meal '{m0}' updated to '{new_name}'.")
                    st.rerun()
                else:
                    st.error(f"Meal '{m0}' not found in DB.")

        # 7️⃣ Handle Delete (also re-fetch)
        if delete_btn:
            with get_db() as db:
                m_db = db.query(MealModel).filter(MealModel.name == m0).first()
                if m_db:
                    db.delete(m_db)
                    db.commit()
                    st.success(f"Meal '{m0}' deleted.")
                    st.rerun()
                else:
                    st.error(f"Meal '{m0}' not found in DB.")

    # ─── Tab 5: View Meals ─────────────────────────────────────────────
    with tab_view_meals:
        st.header("📋 Logged Meals")
        df_meals = load_logged_meals()
        if df_meals.empty:
            st.write("No meals found.")
        else:
            df_meals['Food Names'] = df_meals['Food Names'].str.replace("\n", "<br>")
            st.markdown(df_meals.to_html(escape=False, index=False), unsafe_allow_html=True)

    # ─── Tab 6: Daily Planner ─────────────────────────────────────────
    with tab_planner:
        with get_db() as db:
            users = db.query(User).all()
        user_opts = ["-- None --"] + [u.name for u in users]
        chosen_user = st.selectbox("Select User (optional)", user_opts)
        if chosen_user != "-- None --":
            user = next(u for u in users if u.name==chosen_user)
            avg_bmr  = (user.bmr_hb + user.bmr_msj) / 2
            avg_tdee = (user.tdee_hb + user.tdee_msj) / 2
            st.markdown(f"**BMR avg:** {avg_bmr:.0f}  **TDEE avg:** {avg_tdee:.0f}  "
                        + (f"**Target:** {user.target_calories:.0f}" if user.target_calories else ""))
        else:
            user = None

        st.header("🍽️ Daily Planner")
        df_foods = load_logged_foods()
        df_meals = load_logged_meals()

        num_meals = st.number_input("Meals per day", min_value=1, max_value=10, value=5, step=1)
        plan_items = []
        totals = dict.fromkeys(['Calories','Protein','Carbs','Fat_Regular','Fat_Saturated','Sodium'], 0.0)

        for i in range(int(num_meals)):
            st.subheader(f"Meal #{i+1}")
            choice = st.radio("Add", ("Food","Meal"), key=f"choice_{i}")
            
            if choice == "Food":
                sel = st.selectbox("Select food", df_foods['Name'].unique(), key=f"food_{i}")
                mult = st.number_input("Portion multiplier", min_value=0.1, step=0.1, key=f"pmult_{i}")
                if sel:
                    info = df_foods[df_foods['Name']==sel].iloc[0]
                    for k in totals:
                        totals[k] += info[k] * mult
                    plan_items.append(f"{sel} x{mult}")
            else:
                if df_meals.empty:
                    st.warning("No meals logged yet. Please create meals first.")
                    break
                sel = st.selectbox("Select meal", df_meals['Meal Name'].unique(), key=f"meal_{i}")
                mult_meal = st.number_input("Meal multiplier", min_value=0.1, step=0.1, key=f"mmult_{i}", value=1.0)
                if sel:
                    macros = MealService(sel).get_meal_macros(sel)
                    totals['Calories']     += macros['calories']     * mult_meal
                    totals['Protein']      += macros['protein']      * mult_meal
                    totals['Carbs']        += macros['carbs']        * mult_meal
                    totals['Fat_Regular']  += macros['fat_regular']  * mult_meal
                    totals['Fat_Saturated']+= macros['fat_saturated']* mult_meal
                    totals['Sodium']       += macros['sodium']       * mult_meal
                    plan_items.append(f"{sel} x{mult_meal}")

        if st.button("Calculate Total Macros", key="planner_calc_macros"):
            st.write("## Total Macros for Today")
            for k,v in totals.items():
                if k == "Calories":
                    C = totals['Calories']
                    color = "black"
                    if user:
                        if user.target_calories:
                            if user.goal_type == "Lose weight":
                                color = "green" if C <= user.target_calories else "red"
                            else:
                                color = "green" if C >= user.target_calories else "red"
                        else:
                            tgt = (user.tdee_hb + user.tdee_msj)/2
                            tol = tgt * 0.1
                            color = "green" if abs(C - tgt) <= tol else "red"
                    st.markdown(f"**Total Calories:** <span style='color:{color}'>{C:.2f}</span>", unsafe_allow_html=True)
                st.write(f"**{k.replace('_',' ')}:** {v:.2f}")

        if st.button("Save This Day’s Plan to DB", key="planner_save_plan"):
            if not plan_items:
                st.warning("No meals or foods selected.")
                return
            totals = {k: float(v) for k,v in totals.items()}
            plan_str = "; ".join(plan_items)
            db = SessionLocal()
            new_plan = DailyPlan(
                date=date.today(),
                meals=plan_str,
                calories=totals['Calories'],
                protein=totals['Protein'],
                carbs=totals['Carbs'],
                fat_regular=totals['Fat_Regular'],
                fat_saturated=totals['Fat_Saturated'],
                sodium=totals['Sodium']
            )
            with get_db() as db:
                db.add(new_plan)
                db.commit()
            st.success("Saved today's meal plan!")
            st.balloons()   

    # ─── Tab 7: Saved Day Plans ───────────────────────────────────────
    with tab_daily:
        st.header("📆 Saved Day Plans")
        with get_db() as db:
            plans = db.query(DailyPlan).order_by(DailyPlan.date.desc()).all()


        if not plans:
            st.write("No saved plans found.")
        else:
            df_plans = pd.DataFrame([{
                'Date': p.date,
                'Meals': p.meals,
                'Calories': p.calories,
                'Protein': p.protein,
                'Carbs': p.carbs,
                'Fat_Regular': p.fat_regular,
                'Fat_Saturated': p.fat_saturated,
                'Sodium': p.sodium
            } for p in plans])
            st.dataframe(df_plans, use_container_width=True)
            st.markdown(
                """
                <style>
                    div[data-testid="stHorizontalBlock"] > div:first-child {
                        width: 100%;
                    }
                </style>
                """, unsafe_allow_html=True
            )
    # ─── Tab 8: ChatGPT Assistant ─────────────────────────────────────
    with tab_chat:
        st.header("💬 Nutrition & Training ChatGPT")
        question = st.text_area("Ask a question about nutrition or training:")
        if st.button("Send", key="chat_send"):
            if not question.strip():
                st.warning("Please enter a question.")
            else:
                messages = [
                    {"role":"system","content":
                    "You’re an assistant specialized in nutrition/training. Only answer those topics."
                    },
                    {"role":"user","content":question}
                ]
                try:
                    resp = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=messages,
                        max_tokens=500,
                        temperature=0.7
                    )
                    st.markdown(resp.choices[0].message.content)
                except OpenAIError as e:
                    if "quota" in str(e).lower():
                        st.error(
                            "😬 It looks like your OpenAI quota is exhausted. "
                            "Please check your plan and billing at platform.openai.com."
                        )
                    else:
                        st.error(f"OpenAI error: {e}")

if __name__ == "__main__":
    main()
