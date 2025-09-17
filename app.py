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
import time
from io import BytesIO
import base64


def export_foods_to_excel(path: str = 'foods_log.xlsx'):
    # Grab all foods from the DB and write to Excel
    with get_db() as db:
        foods = db.query(FoodModel).all()
    df = pd.DataFrame([{
        'Name':        f.name,
        'Label':       f.label,
        'Measurement': f.measurement,
        'Calories':    f.calories,
        'Protein':     f.protein,
        'Carbs':       f.carbs,
        'Fat_Saturated': f.fat_saturated,
        'Fat_Regular': f.fat_regular,
        'Sodium':      f.sodium
    } for f in foods])
    df.to_excel(path, index=False)

def export_meals_to_excel(path: str = 'meals_log.xlsx'):
    # Reconstruct each meal → one row per food + Total row
    rows = []
    with get_db() as db:
        meals = db.query(MealModel).all()
        for m in meals:
            # each food in the meal
            for mf in m.meal_food_items:
                f = mf.food
                rows.append({
                    'Meal_Name':  m.name,
                    'Food_Name':  f"{mf.multiplier}x {f.name}",
                    'Label':      f.label,
                    'Measurement': f"{mf.multiplier}x {f.measurement}",
                    'Calories':   f.calories * mf.multiplier,
                    'Protein':    f.protein  * mf.multiplier,
                    'Carbs':      f.carbs    * mf.multiplier,
                    'Fat_Saturated': f.fat_saturated * mf.multiplier,
                    'Fat_Regular':   f.fat_regular   * mf.multiplier,
                    'Sodium':     f.sodium   * mf.multiplier
                })
            # add a total row
            total = MealService(m.name).get_meal_macros(m.name)
            rows.append({
                'Meal_Name':   m.name,
                'Food_Name':   'Total',
                'Label':       '',
                'Measurement': '',
                'Calories':    total['calories'],
                'Protein':     total['protein'],
                'Carbs':       total['carbs'],
                'Fat_Saturated': total['fat_saturated'],
                'Fat_Regular':   total['fat_regular'],
                'Sodium':      total['sodium']
            })
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)


def generate_weekly_pdf_report(user, weekly_data, chart_figures=None):
    """Generate a comprehensive PDF report for weekly meal plan"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus.flowables import Image
        import tempfile
        import os
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        story = []
        temp_files = []  # Keep track of temp files to clean up later
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center
            textColor=colors.darkblue
        )
        story.append(Paragraph(f"Weekly Meal Plan Report", title_style))
        story.append(Spacer(1, 20))
        
        # User Information Section
        user_style = ParagraphStyle(
            'UserInfo',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=10,
            leftIndent=20
        )
        
        story.append(Paragraph("<b>User Information</b>", styles['Heading2']))
        story.append(Paragraph(f"<b>Name:</b> {user.name}", user_style))
        story.append(Paragraph(f"<b>Age:</b> {user.age} years", user_style))
        story.append(Paragraph(f"<b>Sex:</b> {user.sex}", user_style))
        story.append(Paragraph(f"<b>Weight:</b> {user.weight_kg} kg", user_style))
        story.append(Paragraph(f"<b>Height:</b> {user.height_cm} cm", user_style))
        story.append(Paragraph(f"<b>Goal:</b> {user.goal_type or 'Not set'}", user_style))
        if user.weight_change_amount and user.goal_period:
            story.append(Paragraph(f"<b>Target:</b> {user.goal_type} {user.weight_change_amount}kg {user.goal_period.lower()}", user_style))
        if user.target_calories:
            story.append(Paragraph(f"<b>Target Calories:</b> {user.target_calories:.0f} cal/day", user_style))
        
        avg_bmr = (user.bmr_hb + user.bmr_msj) / 2
        avg_tdee = (user.tdee_hb + user.tdee_msj) / 2
        story.append(Paragraph(f"<b>BMR Average:</b> {avg_bmr:.0f} cal/day", user_style))
        story.append(Paragraph(f"<b>TDEE Average:</b> {avg_tdee:.0f} cal/day", user_style))
        
        story.append(Spacer(1, 20))
        
        # Weekly Plan Table
        story.append(Paragraph("<b>Weekly Meal Plan</b>", styles['Heading2']))
        
        # Prepare table data
        table_data = [['Day', 'Date', 'Calories', 'Protein', 'Carbs', 'Fat (Regular)', 'Fat (Saturated)', 'Sodium']]
        
        for item in weekly_data:
            if item['Day'] not in ['**WEEKLY TOTAL**', '**DAILY AVERAGE**']:
                table_data.append([
                    item['Day'],
                    str(item['Date']),
                    f"{item['Calories']:.0f}",
                    f"{item['Protein']:.1f}g",
                    f"{item['Carbs']:.1f}g",
                    f"{item['Fat_Regular']:.1f}g",
                    f"{item['Fat_Saturated']:.1f}g",
                    f"{item['Sodium']:.1f}mg"
                ])
        
        # Add summary rows
        for item in weekly_data:
            if item['Day'] in ['**WEEKLY TOTAL**', '**DAILY AVERAGE**']:
                table_data.append([
                    item['Day'],
                    str(item['Date']),
                    f"{item['Calories']:.0f}",
                    f"{item['Protein']:.1f}g",
                    f"{item['Carbs']:.1f}g",
                    f"{item['Fat_Regular']:.1f}g",
                    f"{item['Fat_Saturated']:.1f}g",
                    f"{item['Sodium']:.1f}mg"
                ])
        
        # Create table
        table = Table(table_data, colWidths=[1*inch, 1*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -3), colors.beige),
            ('BACKGROUND', (0, -2), (-1, -1), colors.lightblue),
            ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
        
        # Detailed Meals Section
        story.append(Paragraph("<b>Detailed Daily Meals</b>", styles['Heading2']))
        
        for item in weekly_data:
            if item['Day'] not in ['**WEEKLY TOTAL**', '**DAILY AVERAGE**'] and item['Calories'] > 0:
                story.append(Paragraph(f"<b>{item['Day']} ({item['Date']})</b>", styles['Heading3']))
                
                # Clean up meals text for PDF and handle HTML spaces
                meals_text = item['Meals'].replace('<br>', '\n').replace('&lt;', '<').replace('&gt;', '>')
                # HTML spaces are already in the correct format for PDF
                meals_para = Paragraph(meals_text.replace('\n', '<br/>'), styles['Normal'])
                story.append(meals_para)
                story.append(Spacer(1, 10))
        
        # Add charts if provided
        if chart_figures:
            story.append(PageBreak())
            story.append(Paragraph("<b>Macro Trends Charts</b>", styles['Heading2']))
            
            for i, fig in enumerate(chart_figures):
                try:
                    # Save figure to BytesIO buffer instead of temp file
                    img_buffer = BytesIO()
                    fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
                    img_buffer.seek(0)
                    
                    # Create image from buffer
                    img = Image(img_buffer, width=6*inch, height=3*inch)
                    story.append(img)
                    story.append(Spacer(1, 10))
                    
                except Exception as e:
                    # If buffer approach fails, try temp file approach with better handling
                    try:
                        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                        temp_files.append(temp_file.name)
                        fig.savefig(temp_file.name, format='png', dpi=150, bbox_inches='tight')
                        temp_file.close()  # Close file before reading
                        
                        # Add image to PDF
                        img = Image(temp_file.name, width=6*inch, height=3*inch)
                        story.append(img)
                        story.append(Spacer(1, 10))
                    except Exception as e2:
                        # Add a text placeholder if chart can't be added
                        story.append(Paragraph(f"<i>Chart {i+1} could not be included</i>", styles['Normal']))
                        story.append(Spacer(1, 10))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
        
        return buffer
        
    except ImportError:
        st.error("reportlab library is not installed. Please install it with: pip install reportlab")
        return None
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        # Clean up any temp files that might have been created
        try:
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except:
                    pass
        except:
            pass
        return None


def format_detailed_plan_item(item_type: str, item_name: str, multiplier: float, db_session) -> str:
    """
    Format a plan item with detailed food information using dots and calculated measurements.
    For foods: returns "• 200g Chicken Breast (Grilled)"
    For meals: expands to show individual foods within the meal with calculated amounts
    """
    
    def parse_measurement_and_calculate(measurement: str, multiplier: float) -> str:
        """Parse measurement and calculate the actual amount."""
        import re
        
        # Handle special case: "1(62.5g)" - extract just the number
        match = re.match(r'^(\d+(?:\.\d+)?)\(.*?\)$', measurement.strip())
        if match:
            amount = float(match.group(1))
            calculated_amount = amount * multiplier
            
            if calculated_amount == int(calculated_amount):
                return f"{int(calculated_amount)}"
            else:
                return f"{calculated_amount:.1f}"
        
        # Handle measurements like "1(from 1 egg)" - just use the number
        match = re.match(r'^(\d+(?:\.\d+)?)\(.*?\)$', measurement.strip())
        if match:
            amount = float(match.group(1))
            calculated_amount = amount * multiplier
            
            if calculated_amount == int(calculated_amount):
                return f"{int(calculated_amount)}"
            else:
                return f"{calculated_amount:.1f}"
        
        # Extract number and unit from measurement like "100g", "1 tbsp", etc.
        match = re.match(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)$', measurement.strip())
        if match:
            amount = float(match.group(1))
            unit = match.group(2)
            calculated_amount = amount * multiplier
            
            # Format nicely - remove .0 for whole numbers
            if calculated_amount == int(calculated_amount):
                return f"{int(calculated_amount)}{unit}"
            else:
                return f"{calculated_amount:.1f}{unit}"
        
        # Handle measurements like "1 medium", "1 large", etc.
        match = re.match(r'^(\d+(?:\.\d+)?)\s+(.+)$', measurement.strip())
        if match:
            amount = float(match.group(1))
            unit = match.group(2)
            calculated_amount = amount * multiplier
            
            if calculated_amount == int(calculated_amount):
                return f"{int(calculated_amount)}{unit}"
            else:
                return f"{calculated_amount:.1f}{unit}"
        
        # Fallback - just add multiplier info
        return f"{multiplier}x {measurement}"
    
    if item_type == "food":
        food = db_session.query(FoodModel).filter(FoodModel.name == item_name).first()
        if food:
            calculated_measurement = parse_measurement_and_calculate(food.measurement, multiplier)
            # Hide label if it's just "-"
            if food.label == "-":
                return f"• {calculated_measurement} {food.name}"
            else:
                return f"• {calculated_measurement} {food.name} ({food.label})"
        return f"• {multiplier}x {item_name}"
    
    elif item_type == "meal":
        meal = (
            db_session.query(MealModel)
            .options(
                joinedload(MealModel.meal_food_items)
                    .joinedload(MealFoodModel.food)
            )
            .filter(MealModel.name == item_name)
            .first()
        )
        if meal:
            meal_foods = []
            for mf in meal.meal_food_items:
                food = mf.food
                total_mult = mf.multiplier * multiplier
                calculated_measurement = parse_measurement_and_calculate(food.measurement, total_mult)
                # Hide label if it's just "-" and use HTML spaces for indentation
                if food.label == "-":
                    meal_foods.append(f"&nbsp;&nbsp;&nbsp;&nbsp;- {calculated_measurement} {food.name}")
                else:
                    meal_foods.append(f"&nbsp;&nbsp;&nbsp;&nbsp;- {calculated_measurement} {food.name} ({food.label})")
            
            # Format as: • meal_name\n\t- ingredients
            ingredients_str = "\n".join(meal_foods)
            return f"• {item_name}:\n{ingredients_str}"
        return f"• {item_name} (meal)"
    
    elif item_type == "customized_meal":
        # For customized meals, multiplier is actually the ingredient_data list
        ingredient_data = multiplier  # This is actually [(food_name, food_label, mult), ...]
        meal_foods = []
        for food_name, food_label, mult in ingredient_data:
            # Get food measurement info
            food = db_session.query(FoodModel).filter(
                FoodModel.name == food_name,
                FoodModel.label == food_label
            ).first()
            if food:
                calculated_measurement = parse_measurement_and_calculate(food.measurement, mult)
                # Hide label if it's just "-" and use HTML spaces for indentation
                if food.label == "-":
                    meal_foods.append(f"&nbsp;&nbsp;&nbsp;&nbsp;- {calculated_measurement} {food.name}")
                else:
                    meal_foods.append(f"&nbsp;&nbsp;&nbsp;&nbsp;- {calculated_measurement} {food.name} ({food.label})")
            else:
                # Fallback case - hide label if it's "-"
                if food_label == "-":
                    meal_foods.append(f"\t- {mult}x {food_name}")
                else:
                    meal_foods.append(f"\t- {mult}x {food_name} ({food_label})")
        
        # Format as: • Custom meal_name:\n\t- ingredients
        ingredients_str = "\n".join(meal_foods)
        return f"• Custom {item_name}:\n{ingredients_str}"
    
    return f"• {multiplier}x {item_name}"


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
        "Manage Users",
        "Log/Delete Food",
        "View Foods",
        "Create Meal",
        "Manage Meals",
        "View Meals",
        "Daily Planner",
        "Saved Day Plans",
        "Weekly Plan",
        "ChatGPT"
    ])
    (tab_calc, tab_manage_users, tab_log, tab_view,
     tab_create, tab_manage_meals,
     tab_view_meals,
     tab_planner, tab_daily,
     tab_weekly,
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
            "Completely Paralyzed, Comatose, Unable to Move Without the Aid of Others (1.0)": 1.0,
            "Immobile, Stationary with Some Arm Movement, Bedridden or Partially Paralyzed (1.05)": 1.05,
            "Constricted Lifestyle, Movement is Limited to a Confined Space, Almost Always Sitting or Laying (1.1)": 1.1,
            "Working From Home with Little to No Travel, No Exercise, Some Walking, Mostly Sitting or Laying (1.16)": 1.16,
            "Sedentary Lifestyle, Little or No Exercise, Moderate Walking, Desk Job (Away from Home) (1.2)": 1.2,
            "Slightly Active, Exercise or Light Sports 1 to 3 Days a Week, Light Jogging or Walking 3 to 4 Days a Week (1.375)": 1.375,
            "Lightly Active, Exercise or Moderate Sports 2 to 3 Days a Week, Light Jogging or Walking 5 to 7 Days a Week (1.425)": 1.425,
            "Moderately Active, Physical Work, Exercise, or Sports 4 to 5 Days a Week, Construction Laborer (1.55)": 1.55,
            "Very Active, Heavy Physical Work, Exercise, or Sports 6 to 7 Days a Week, Hard Laborer (1.75)": 1.75,
            "Extremely Active, Very Heavy Physical Work or Exercise Every Day, Professional/Olympic Athlete (1.9)": 1.9
        }

        activity = st.selectbox("Activity Level", list(activity_levels.keys()))

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
            if sex == "Male":
                bmr_hb = 88.362 + (13.397 * weight) + (4.799 * height_cm) - (5.677 * age)
                bmr_ms = (10 * weight) + (6.25 * height_cm) - (5 * age) + 5
            else:
                bmr_hb = 447.593 + (9.247 * weight) + (3.098 * height_cm) - (4.330 * age)
                bmr_ms = (10 * weight) + (6.25 * height_cm) - (5 * age) - 161

            factor  = activity_levels[activity]
            tdee_hb = bmr_hb * factor
            tdee_ms = bmr_ms * factor
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
                    user.goal_period    = period     # "Per week" / "Per month" / "Per year"
                    user.weight_change_amount = float(weight_change) if weight_change else None
                    user.target_calories= float(avg_target) if avg_target else None
                    db.commit()
                st.success(f"Profile for {name} saved.")

    # ─── Tab 2: Manage Users ─────────────────────────────────────────────
    with tab_manage_users:
        st.header("👥 Manage Users")
        
        # Load all users
        with get_db() as db:
            users_list = db.query(User).all()
        
        if not users_list:
            st.info("No users found. Create a user in the Calculator tab first.")
        else:
            # User selection
            user_options = [f"{u.name} (Age: {u.age}, {u.sex})" for u in users_list]
            selected_user_display = st.selectbox("Select user to edit/delete:", user_options)
            
            if selected_user_display:
                # Find the selected user
                selected_idx = user_options.index(selected_user_display)
                selected_user = users_list[selected_idx]
                
                st.subheader(f"Editing: {selected_user.name}")
                
                # Edit form
                with st.form(key="edit_user_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_name = st.text_input("Name", value=selected_user.name)
                        edit_age = st.number_input("Age", value=int(selected_user.age), min_value=0, max_value=120)
                        edit_sex = st.selectbox("Sex", ("Male", "Female"), index=0 if selected_user.sex == "Male" else 1)
                        edit_weight = st.number_input("Weight (kg)", value=float(selected_user.weight_kg), min_value=0.0, step=0.1)
                        edit_height = st.number_input("Height (cm)", value=float(selected_user.height_cm), min_value=0.0, step=0.1)
                    
                    with col2:
                        # Activity levels (same as calculator)
                        activity_levels = {
                            "Completely Paralyzed, Comatose, Unable to Move Without the Aid of Others (1.0)": 1.0,
                            "Immobile, Stationary with Some Arm Movement, Bedridden or Partially Paralyzed (1.05)": 1.05,
                            "Constricted Lifestyle, Movement is Limited to a Confined Space, Almost Always Sitting or Laying (1.1)": 1.1,
                            "Working From Home with Little to No Travel, No Exercise, Some Walking, Mostly Sitting or Laying (1.16)": 1.16,
                            "Sedentary Lifestyle, Little or No Exercise, Moderate Walking, Desk Job (Away from Home) (1.2)": 1.2,
                            "Slightly Active, Exercise or Light Sports 1 to 3 Days a Week, Light Jogging or Walking 3 to 4 Days a Week (1.375)": 1.375,
                            "Lightly Active, Exercise or Moderate Sports 2 to 3 Days a Week, Light Jogging or Walking 5 to 7 Days a Week (1.425)": 1.425,
                            "Moderately Active, Physical Work, Exercise, or Sports 4 to 5 Days a Week, Construction Laborer (1.55)": 1.55,
                            "Very Active, Heavy Physical Work, Exercise, or Sports 6 to 7 Days a Week, Hard Laborer (1.75)": 1.75,
                            "Extremely Active, Very Heavy Physical Work or Exercise Every Day, Professional/Olympic Athlete (1.9)": 1.9
                        }
                        
                        current_activity = next((k for k, v in activity_levels.items() if k == selected_user.activity_level), list(activity_levels.keys())[0])
                        edit_activity = st.selectbox("Activity Level", list(activity_levels.keys()), index=list(activity_levels.keys()).index(current_activity))
                        
                        edit_goal = st.selectbox("Goal", ("Lose weight", "Gain weight"), index=0 if selected_user.goal_type == "Lose weight" else 1)
                        edit_weight_change = st.number_input("Weight change (kg)", value=float(selected_user.weight_change_amount) if selected_user.weight_change_amount else 0.0, min_value=0.0, step=0.1)
                        edit_period = st.selectbox("Period", ("Per week", "Per month", "Per year"), index=0 if selected_user.goal_period == "Per week" else (1 if selected_user.goal_period == "Per month" else 2))
                    
                    # Action buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        update_user = st.form_submit_button("Update User", type="primary")
                    with col2:
                        delete_user = st.form_submit_button("Delete User", type="secondary")
                
                # Handle update
                if update_user:
                    try:
                        # Recalculate BMR and TDEE
                        if edit_sex == "Male":
                            bmr_hb = 88.362 + (13.397 * edit_weight) + (4.799 * edit_height) - (5.677 * edit_age)
                            bmr_ms = (10 * edit_weight) + (6.25 * edit_height) - (5 * edit_age) + 5
                        else:
                            bmr_hb = 447.593 + (9.247 * edit_weight) + (3.098 * edit_height) - (4.330 * edit_age)
                            bmr_ms = (10 * edit_weight) + (6.25 * edit_height) - (5 * edit_age) - 161
                        
                        factor = activity_levels[edit_activity]
                        tdee_hb = bmr_hb * factor
                        tdee_ms = bmr_ms * factor
                        
                        # Calculate target calories
                        days_map = {"Per week": 7, "Per month": 30, "Per year": 365}
                        days = days_map[edit_period]
                        cal_adjust = (edit_weight_change * 7700) / days
                        
                        if edit_goal == "Lose weight":
                            target_calories = ((tdee_hb + tdee_ms) / 2) - cal_adjust
                        else:
                            target_calories = ((tdee_hb + tdee_ms) / 2) + cal_adjust
                        
                        # Update user in database
                        with get_db() as db:
                            user_to_update = db.query(User).filter(User.id == selected_user.id).first()
                            if user_to_update:
                                user_to_update.name = edit_name
                                user_to_update.age = int(edit_age)
                                user_to_update.sex = edit_sex
                                user_to_update.weight_kg = float(edit_weight)
                                user_to_update.height_cm = float(edit_height)
                                user_to_update.activity_level = edit_activity
                                user_to_update.bmr_hb = bmr_hb
                                user_to_update.bmr_msj = bmr_ms
                                user_to_update.tdee_hb = tdee_hb
                                user_to_update.tdee_msj = tdee_ms
                                user_to_update.goal_type = edit_goal
                                user_to_update.goal_period = edit_period
                                user_to_update.weight_change_amount = float(edit_weight_change)
                                user_to_update.target_calories = float(target_calories)
                                db.commit()
                        
                        st.success(f"User '{edit_name}' updated successfully!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error updating user: {e}")
                
                # Handle delete
                if delete_user:
                    try:
                        with get_db() as db:
                            user_to_delete = db.query(User).filter(User.id == selected_user.id).first()
                            if user_to_delete:
                                db.delete(user_to_delete)
                                db.commit()
                        
                        st.success(f"User '{selected_user.name}' deleted successfully!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error deleting user: {e}")

        # ─── Tab 3: Log / Edit / Delete Food ────────────────────────────────────
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

        if st.button("Export Foods to foods_log.xlsx", key="export_foods"):
            export_foods_to_excel()
            st.success("All foods exported to foods_log.xlsx")

    # ─── Tab 4: Create Meal ────────────────────────────────────────────
    with tab_create:
        st.header("🥗 Create Meal")
        df_foods  = load_logged_foods()
        meal_name = st.text_input("Meal Name", key='meal_name')
        
        # Create food options showing both name and label to distinguish between items
        food_options = [f"{row['Name']} ({row['Label']})" for _, row in df_foods.iterrows()]
        selected = st.multiselect("Select Foods", food_options, key="create_meal_foods")

        meal_data = []
        for food_display in selected:
            # Extract name and label from the display string
            # Handle nested parentheses properly
            if ' (' in food_display:
                food_name = food_display.split(' (')[0]
                # Get everything after the first ' (' and remove only the last ')'
                food_label = food_display.split(' (', 1)[1][:-1]
            else:
                food_name = food_display
                food_label = ""
            
            # Find the matching food info with error handling
            food_matches = df_foods[(df_foods['Name'] == food_name) & (df_foods['Label'] == food_label)]
            if not food_matches.empty:
                info = food_matches.iloc[0]
                display_text = f"{info['Label']} {food_name} multiplier ({info['Measurement']})"
            else:
                st.warning(f"⚠️ Food '{food_name} ({food_label})' not found in current foods list.")
                display_text = f"{food_label} {food_name} multiplier (measurement unknown)"
            
            mult = st.number_input(
                display_text,
                min_value=0.1, step=0.1,
                key=f"mult_{food_display}"
            )
            meal_data.append((food_name, food_label, mult))

        # Calculate and display meal macros
        if meal_data:
            st.subheader("📊 Meal Macro Preview")
            
            # Calculate totals
            total_calories = 0
            total_protein = 0
            total_carbs = 0
            total_fat_regular = 0
            total_fat_saturated = 0
            total_sodium = 0
            
            # Create a detailed breakdown table
            breakdown_data = []
            
            for food_name, food_label, mult in meal_data:
                # Get food info
                food_matches = df_foods[(df_foods['Name'] == food_name) & (df_foods['Label'] == food_label)]
                if not food_matches.empty:
                    food_info = food_matches.iloc[0]
                    
                    # Calculate macros for this food item
                    item_calories = food_info['Calories'] * mult
                    item_protein = food_info['Protein'] * mult
                    item_carbs = food_info['Carbs'] * mult
                    item_fat_regular = food_info['Fat_Regular'] * mult
                    item_fat_saturated = food_info['Fat_Saturated'] * mult
                    item_sodium = food_info['Sodium'] * mult
                    
                    # Add to totals
                    total_calories += item_calories
                    total_protein += item_protein
                    total_carbs += item_carbs
                    total_fat_regular += item_fat_regular
                    total_fat_saturated += item_fat_saturated
                    total_sodium += item_sodium
                    
                    # Add to breakdown
                    breakdown_data.append({
                        'Food': f"{mult}x {food_name} ({food_label})",
                        'Calories': f"{item_calories:.1f}",
                        'Protein': f"{item_protein:.1f}g",
                        'Carbs': f"{item_carbs:.1f}g",
                        'Fat (Regular)': f"{item_fat_regular:.1f}g",
                        'Fat (Saturated)': f"{item_fat_saturated:.1f}g",
                        'Sodium': f"{item_sodium:.1f}mg"
                    })
            
            # Display breakdown table
            if breakdown_data:
                st.write("**Individual Food Breakdown:**")
                breakdown_df = pd.DataFrame(breakdown_data)
                st.dataframe(breakdown_df, use_container_width=True)
                
                # Display totals in columns
                st.write("**Meal Totals:**")
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                
                with col1:
                    st.metric("Calories", f"{total_calories:.0f}")
                with col2:
                    st.metric("Protein", f"{total_protein:.1f}g")
                with col3:
                    st.metric("Carbs", f"{total_carbs:.1f}g")
                with col4:
                    st.metric("Fat (Regular)", f"{total_fat_regular:.1f}g")
                with col5:
                    st.metric("Fat (Saturated)", f"{total_fat_saturated:.1f}g")
                with col6:
                    st.metric("Sodium", f"{total_sodium:.1f}mg")
                
                # Macro ratios
                st.write("**Macro Distribution:**")
                if total_calories > 0:
                    protein_cals = total_protein * 4
                    carb_cals = total_carbs * 4
                    fat_cals = (total_fat_regular + total_fat_saturated) * 9
                    
                    protein_pct = (protein_cals / total_calories) * 100
                    carb_pct = (carb_cals / total_calories) * 100
                    fat_pct = (fat_cals / total_calories) * 100
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Protein %", f"{protein_pct:.1f}%")
                    with col2:
                        st.metric("Carbs %", f"{carb_pct:.1f}%")
                    with col3:
                        st.metric("Fat %", f"{fat_pct:.1f}%")

        if st.button("Create Meal"):
            if not meal_name.strip():
                st.error("Meal name cannot be empty.")
            else:
                err = MealService(meal_name).create_meal(meal_data)
                st.success(f"Meal '{meal_name}' created!") if err is None else st.error(err)
                time.sleep(2)
                st.rerun()

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
        food_options = [f"{row['Name']} ({row['Label']})" for _, row in df_foods.iterrows()]
        
        # Set defaults based on existing foods in the meal
        default_selections = []
        for food_name, food_label, mult in foods0:
            default_selections.append(f"{food_name} ({food_label})")
        
        selected = st.multiselect("Select Foods", food_options, default=default_selections, key="manage_meal_foods")
        meal_data = []
        for food_display in selected:
            # Extract name and label from the display string
            # Handle nested parentheses properly
            if ' (' in food_display:
                food_name = food_display.split(' (')[0]
                # Get everything after the first ' (' and remove only the last ')'
                food_label = food_display.split(' (', 1)[1][:-1]
            else:
                food_name = food_display
                food_label = ""
            
            # Find default multiplier for this specific food (name + label combination)
            default_mult = next((mult for (n,l,mult) in foods0 if n==food_name and l==food_label), 1.0)
            
            # Get measurement info for display with error handling
            food_matches = df_foods[(df_foods['Name'] == food_name) & (df_foods['Label'] == food_label)]
            if not food_matches.empty:
                food_info = food_matches.iloc[0]
                measurement = food_info['Measurement']
                display_text = f"{food_label} {food_name} multiplier ({measurement})"
            else:
                # Food not found in current foods list - show warning and use basic display
                st.warning(f"⚠️ Food '{food_name} ({food_label})' not found in current foods list. It may have been deleted.")
                measurement = "unknown"
                display_text = f"{food_label} {food_name} multiplier (measurement unknown)"
            
            mult = st.number_input(
                display_text,
                min_value=0.1, step=0.1,
                value=float(default_mult),
                key=f"manage_mult_{food_display}"
            )
            meal_data.append((food_name, food_label, mult))

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
                time.sleep(2)
                st.rerun()

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
                        if f_db:
                            db.add(MealFoodModel(
                                meal_id    = m_db.id,
                                food_id    = f_db.id,
                                multiplier = mult
                            ))
                        else:
                            st.error(f"Food '{fname} ({lbl})' not found in database. Skipping this item.")
                    # rename if changed
                    m_db.name = new_name
                    db.commit()
                    st.success(f"Meal '{m0}' updated to '{new_name}'.")
                    time.sleep(2)
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
                    time.sleep(2)
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

        if st.button("Export Meals to meals_log.xlsx", key="export_meals"):
            export_meals_to_excel()
            st.success("All meals exported to meals_log.xlsx")

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
            
            # Calculate goal-based TDEE (target calories)
            goal_based_tdee = user.target_calories if user.target_calories else avg_tdee
            
            goal_info = ""
            if user.goal_type and user.goal_period and user.weight_change_amount:
                goal_info = f"**Goal:** {user.goal_type} {user.weight_change_amount}kg {user.goal_period.lower()}  "
            
            st.markdown(f"**BMR avg:** {avg_bmr:.0f}  **TDEE avg:** {avg_tdee:.0f}  **Goal-based TDEE:** {goal_based_tdee:.0f}  {goal_info}")
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
                    plan_items.append(("food", sel, mult))
            else:
                if df_meals.empty:
                    st.warning("No meals logged yet. Please create meals first.")
                    break
                sel = st.selectbox("Select meal", df_meals['Meal Name'].unique(), key=f"meal_{i}")
                
                if sel:
                    # Get meal details with ingredients
                    with get_db() as db:
                        meal_obj = (
                            db.query(MealModel)
                            .options(
                                joinedload(MealModel.meal_food_items)
                                    .joinedload(MealFoodModel.food)
                            )
                            .filter(MealModel.name == sel)
                            .first()
                        )
                    
                    if meal_obj:
                        # Option to customize ingredients or use default
                        customize_option = st.radio(
                            "Meal customization:",
                            ("Use default meal", "Customize ingredients"),
                            key=f"customize_{i}"
                        )
                        
                        if customize_option == "Use default meal":
                            # Simple meal multiplier (original behavior)
                            mult_meal = st.number_input("Meal multiplier", min_value=0.1, step=0.1, key=f"mmult_{i}", value=1.0)
                            
                            # Calculate macros using default meal composition
                            macros = MealService(sel).get_meal_macros(sel)
                            totals['Calories']     += macros['calories']     * mult_meal
                            totals['Protein']      += macros['protein']      * mult_meal
                            totals['Carbs']        += macros['carbs']        * mult_meal
                            totals['Fat_Regular']  += macros['fat_regular']  * mult_meal
                            totals['Fat_Saturated']+= macros['fat_saturated']* mult_meal
                            totals['Sodium']       += macros['sodium']       * mult_meal
                            plan_items.append(("meal", sel, mult_meal))
                            
                        else:
                            # Customize individual ingredients
                            st.write(f"**Customize ingredients for {sel}:**")
                            
                            # Store individual ingredient data
                            ingredient_data = []
                            ingredient_totals = {
                                'calories': 0, 'protein': 0, 'carbs': 0,
                                'fat_regular': 0, 'fat_saturated': 0, 'sodium': 0
                            }
                            
                            for j, mf in enumerate(meal_obj.meal_food_items):
                                food = mf.food
                                default_mult = mf.multiplier
                                
                                # Show ingredient with measurement info
                                ingredient_mult = st.number_input(
                                    f"{food.label} {food.name} multiplier ({food.measurement})",
                                    min_value=0.0, step=0.1,
                                    value=float(default_mult),
                                    key=f"ingredient_{i}_{j}_{food.id}"
                                )
                                
                                # Calculate macros for this ingredient
                                ingredient_calories = food.calories * ingredient_mult
                                ingredient_protein = food.protein * ingredient_mult
                                ingredient_carbs = food.carbs * ingredient_mult
                                ingredient_fat_regular = food.fat_regular * ingredient_mult
                                ingredient_fat_saturated = food.fat_saturated * ingredient_mult
                                ingredient_sodium = food.sodium * ingredient_mult
                                
                                # Add to totals
                                ingredient_totals['calories'] += ingredient_calories
                                ingredient_totals['protein'] += ingredient_protein
                                ingredient_totals['carbs'] += ingredient_carbs
                                ingredient_totals['fat_regular'] += ingredient_fat_regular
                                ingredient_totals['fat_saturated'] += ingredient_fat_saturated
                                ingredient_totals['sodium'] += ingredient_sodium
                                
                                # Store for plan_items
                                ingredient_data.append((food.name, food.label, ingredient_mult))
                            
                            # Add ingredient totals to overall totals
                            totals['Calories'] += ingredient_totals['calories']
                            totals['Protein'] += ingredient_totals['protein']
                            totals['Carbs'] += ingredient_totals['carbs']
                            totals['Fat_Regular'] += ingredient_totals['fat_regular']
                            totals['Fat_Saturated'] += ingredient_totals['fat_saturated']
                            totals['Sodium'] += ingredient_totals['sodium']
                            
                            # Store as customized meal for plan_items
                            plan_items.append(("customized_meal", sel, ingredient_data))
                            
                            # Show preview of customized meal
                            st.write("**Customized meal preview:**")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Calories", f"{ingredient_totals['calories']:.0f}")
                            with col2:
                                st.metric("Protein", f"{ingredient_totals['protein']:.1f}g")
                            with col3:
                                st.metric("Carbs", f"{ingredient_totals['carbs']:.1f}g")

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

        if st.button("Save This Day's Plan to DB", key="planner_save_plan"):
            if not plan_items:
                st.warning("No meals or foods selected.")
                return
            totals = {k: float(v) for k,v in totals.items()}
            
            # Format plan items with detailed information
            with get_db() as db:
                formatted_items = []
                for item_type, item_name, multiplier in plan_items:
                    formatted_item = format_detailed_plan_item(item_type, item_name, multiplier, db)
                    formatted_items.append(formatted_item)
                
                plan_str = "\n".join(formatted_items)
                
                new_plan = DailyPlan(
                    date=date.today(),
                    user_id=user.id if user else None,
                    meals=plan_str,
                    calories=totals['Calories'],
                    protein=totals['Protein'],
                    carbs=totals['Carbs'],
                    fat_regular=totals['Fat_Regular'],
                    fat_saturated=totals['Fat_Saturated'],
                    sodium=totals['Sodium']
                )
                db.add(new_plan)
                db.commit()
            st.success("Saved today's meal plan!")
            st.balloons()   

    # ─── Tab 7: Saved Day Plans ───────────────────────────────────────
    with tab_daily:
        st.header("👤 User Daily Plans")
        
        # User selection
        with get_db() as db:
            users = db.query(User).all()
        
        if not users:
            st.info("No users found. Create a user in the Calculator tab first.")
        else:
            user_opts = ["All Users"] + [u.name for u in users]
            selected_user = st.selectbox("Select User to view plans:", user_opts)
            
            # Load plans based on user selection
            with get_db() as db:
                if selected_user == "All Users":
                    plans = (
                        db.query(DailyPlan)
                        .options(joinedload(DailyPlan.user))
                        .order_by(DailyPlan.date.desc())
                        .all()
                    )
                else:
                    user = next(u for u in users if u.name == selected_user)
                    plans = (
                        db.query(DailyPlan)
                        .options(joinedload(DailyPlan.user))
                        .filter(DailyPlan.user_id == user.id)
                        .order_by(DailyPlan.date.desc())
                        .all()
                    )

            if not plans:
                st.write(f"No saved plans found for {selected_user}.")
            else:
                # Group plans by user for better organization
                if selected_user == "All Users":
                    # Group by user
                    user_plans = {}
                    for plan in plans:
                        user_name = plan.user.name if plan.user else "No User"
                        if user_name not in user_plans:
                            user_plans[user_name] = []
                        user_plans[user_name].append(plan)
                    
                    for user_name, user_plan_list in user_plans.items():
                        st.subheader(f"📋 {user_name}")
                        
                        # Add delete functionality for "No User" plans
                        if user_name == "No User" and user_plan_list:
                            st.write("**Delete Unassigned Plans:**")
                            plan_options = [f"{p.date} - {p.calories:.0f} cal - {p.protein:.0f}g protein" for p in user_plan_list]
                            selected_plan_display = st.selectbox("Select unassigned plan to delete:", ["-- Select Plan --"] + plan_options, key=f"delete_unassigned")
                            
                            if selected_plan_display != "-- Select Plan --":
                                plan_index = plan_options.index(selected_plan_display)
                                selected_plan = user_plan_list[plan_index]
                                
                                # Show preview of selected plan
                                st.info(f"**Preview:** {selected_plan.date} - {selected_plan.calories:.0f} cal")
                                st.text_area("Meals:", selected_plan.meals, height=100, disabled=True, key=f"preview_unassigned_{selected_plan.id}")
                                
                                col1, col2 = st.columns([1, 3])
                                with col1:
                                    if st.button("🗑️ Delete Plan", type="secondary", key=f"delete_unassigned_btn"):
                                        try:
                                            with get_db() as db:
                                                plan_to_delete = db.query(DailyPlan).filter(DailyPlan.id == selected_plan.id).first()
                                                if plan_to_delete:
                                                    db.delete(plan_to_delete)
                                                    db.commit()
                                            st.success(f"Unassigned plan for {selected_plan.date} deleted successfully!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error deleting plan: {e}")
                            st.markdown("---")
                        
                        # Debug section (temporary) - remove this later
                        if st.checkbox("🔍 Debug Food Lookup Issues", key=f"debug_foods_{user_name}"):
                            st.subheader("Debug: Food Lookup")
                            
                            # Show all foods with their exact names and labels
                            st.write("**All foods in database:**")
                            debug_df = load_logged_foods()
                            debug_df_display = debug_df[['Name', 'Label']].copy()
                            debug_df_display['Full_Display'] = debug_df_display['Name'] + ' (' + debug_df_display['Label'] + ')'
                            st.dataframe(debug_df_display)
                            
                            # Test specific food lookup
                            test_food = st.text_input("Test food lookup (enter 'Name (Label)' format):", 
                                                    value="Ground beef (Cooked(80-20))",
                                                    key=f"debug_test_food_{user_name}")
                            
                            if test_food and ' (' in test_food:
                                test_name = test_food.split(' (')[0]
                                # Get everything after the first ' (' and remove only the last ')'
                                test_label = test_food.split(' (', 1)[1][:-1]
                                
                                st.write(f"**Parsed:** Name='{test_name}', Label='{test_label}'")
                                
                                # Test the exact lookup that's failing
                                food_matches = debug_df[(debug_df['Name'] == test_name) & (debug_df['Label'] == test_label)]
                                st.write(f"**Matches found:** {len(food_matches)}")
                                
                                if not food_matches.empty:
                                    st.success("✅ Food found!")
                                    st.dataframe(food_matches)
                                else:
                                    st.error("❌ Food not found with exact match")
                                    
                                    # Try case-insensitive search
                                    case_matches = debug_df[
                                        (debug_df['Name'].str.lower() == test_name.lower()) & 
                                        (debug_df['Label'].str.lower() == test_label.lower())
                                    ]
                                    st.write(f"**Case-insensitive matches:** {len(case_matches)}")
                                    
                                    # Try partial matches
                                    name_matches = debug_df[debug_df['Name'].str.contains(test_name, case=False, na=False)]
                                    st.write(f"**Name partial matches:** {len(name_matches)}")
                                    if not name_matches.empty:
                                        st.write("**Found these similar foods:**")
                                        st.dataframe(name_matches[['Name', 'Label']])
                                        
                                        # Show the exact format for copying
                                        st.write("**Exact formats to try:**")
                                        for _, row in name_matches.iterrows():
                                            exact_format = f"{row['Name']} ({row['Label']})"
                                            st.code(exact_format)
                                            
                                        # Character-by-character comparison for the first match
                                        if len(name_matches) == 1:
                                            actual_name = name_matches.iloc[0]['Name']
                                            actual_label = name_matches.iloc[0]['Label']
                                            
                                            st.write("**Character-by-character comparison:**")
                                            st.write(f"Expected Name: '{test_name}' (length: {len(test_name)})")
                                            st.write(f"Actual Name: '{actual_name}' (length: {len(actual_name)})")
                                            st.write(f"Expected Label: '{test_label}' (length: {len(test_label)})")
                                            st.write(f"Actual Label: '{actual_label}' (length: {len(actual_label)})")
                                            
                                            if test_name != actual_name:
                                                st.error(f"Name mismatch: '{test_name}' != '{actual_name}'")
                                            if test_label != actual_label:
                                                st.error(f"Label mismatch: '{test_label}' != '{actual_label}'")
                        
                        # Show the plans table
                        df_plans = pd.DataFrame([{
                            'Date': p.date,
                            'Meals': p.meals.replace('\n', '<br>').replace('&nbsp;', ' '),
                            'Calories': round(p.calories),
                            'Protein': round(p.protein, 1),
                            'Carbs': round(p.carbs, 1),
                            'Fat_Regular': round(p.fat_regular, 1),
                            'Fat_Saturated': round(p.fat_saturated, 1),
                            'Sodium': round(p.sodium)
                        } for p in user_plan_list])
                        st.markdown(df_plans.to_html(escape=False, index=False), unsafe_allow_html=True)
                        st.markdown("---")
                else:
                    # Show plans for selected user with delete functionality
                    if plans:
                        st.subheader(f"Delete Plans for {selected_user}")
                        
                        # Plan selection for deletion
                        plan_options = [f"{p.date} - {p.calories:.0f} cal - {p.protein:.0f}g protein" for p in plans]
                        selected_plan_display = st.selectbox("Select plan to delete:", ["-- Select Plan --"] + plan_options)
                        
                        if selected_plan_display != "-- Select Plan --":
                            plan_index = plan_options.index(selected_plan_display)
                            selected_plan = plans[plan_index]
                            
                            # Show preview of selected plan
                            st.info(f"**Preview:** {selected_plan.date} - {selected_plan.calories:.0f} cal")
                            st.text_area("Meals:", selected_plan.meals, height=100, disabled=True)
                            
                            col1, col2 = st.columns([1, 3])
                            with col1:
                                if st.button("🗑️ Delete Plan", type="secondary"):
                                    try:
                                        with get_db() as db:
                                            plan_to_delete = db.query(DailyPlan).filter(DailyPlan.id == selected_plan.id).first()
                                            if plan_to_delete:
                                                db.delete(plan_to_delete)
                                                db.commit()
                                        st.success(f"Plan for {selected_plan.date} deleted successfully!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error deleting plan: {e}")
                        
                        st.markdown("---")
                    
                    # Show all plans table
                    df_plans = pd.DataFrame([{
                        'Date': p.date,
                        'Meals': p.meals.replace('\n', '<br>').replace('&nbsp;', ' '),
                        'Calories': round(p.calories),
                        'Protein': round(p.protein, 1),
                        'Carbs': round(p.carbs, 1),
                        'Fat_Regular': round(p.fat_regular, 1),
                        'Fat_Saturated': round(p.fat_saturated, 1),
                        'Sodium': round(p.sodium)
                    } for p in plans])
                    st.markdown(df_plans.to_html(escape=False, index=False), unsafe_allow_html=True)
            st.markdown(
                """
                <style>
                    div[data-testid="stHorizontalBlock"] > div:first-child {
                        width: 100%;
                    }
                </style>
                """, unsafe_allow_html=True
            )

    with tab_weekly:
        st.header("📅 Weekly Meal Plan Builder")

        # 1) User selection
        with get_db() as db:
            users = db.query(User).all()
        
        if not users:
            st.info("No users found. Create a user in the Calculator tab first.")
        else:
            selected_user_name = st.selectbox("Select User for Weekly Plan:", [u.name for u in users])
            selected_user = next(u for u in users if u.name == selected_user_name)
            
            # Display user info
            target_info = f"{selected_user.target_calories:.0f} cal/day" if selected_user.target_calories else "Not set"
            st.info(f"👤 **{selected_user.name}** | Age: {selected_user.age} | Goal: {selected_user.goal_type or 'Not set'} | Target: {target_info}")
            
            # 2) Load available daily plans for this user
            with get_db() as db:
                available_plans = (
                    db.query(DailyPlan)
                    .filter(DailyPlan.user_id == selected_user.id)
                    .order_by(DailyPlan.date.desc())
                    .all()
                )
            
            if not available_plans:
                st.warning(f"No saved daily plans found for {selected_user.name}. Create some daily plans first.")
            else:
                st.subheader("🗓️ Build Your Weekly Plan")
                
                # Days of the week
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                weekly_plan = {}
                
                # Plan options for selectbox with meal details
                plan_options = ["-- No Plan --"]
                for p in available_plans:
                    # Create a summary of meals/foods for this plan
                    meals_summary = []
                    meal_items = p.meals.split('\n')
                    
                    for item in meal_items:
                        if item.strip():
                            # Clean up HTML entities and bullet points
                            clean_item = item.replace('&nbsp;', ' ').replace('•', '').strip()
                            
                            # Skip ingredient lines (those that start with spaces or dashes)
                            if clean_item.startswith('- '):
                                continue
                                
                            # Extract the main part before any detailed info
                            if ':' in clean_item and not clean_item.startswith('Custom'):
                                # It's a meal header (e.g., "classic_yogurt:")
                                meal_name = clean_item.split(':')[0].strip()
                                if meal_name:
                                    meals_summary.append(meal_name)
                            elif clean_item.startswith('Custom'):
                                # Custom meal (e.g., "Custom breakfast_bowl:")
                                meal_name = clean_item.replace('Custom', '').split(':')[0].strip()
                                if meal_name:
                                    meals_summary.append(f"Custom_{meal_name}")
                            elif '{' in clean_item:
                                # Old format meal with ingredients - shouldn't happen with new format
                                meal_name = clean_item.split('{')[0].strip()
                                if meal_name:
                                    meals_summary.append(meal_name)
                            else:
                                # It's a simple food - extract just the food name
                                parts = clean_item.split(' ', 1)
                                if len(parts) > 1:
                                    # Remove measurement (e.g., "200g") and get food name
                                    food_part = parts[1]
                                    food_name = food_part.split('(')[0].strip()
                                    if food_name:
                                        meals_summary.append(food_name)
                    
                    # Create summary text
                    summary_text = ", ".join(meals_summary)
                    if len(summary_text) > 60:
                        summary_text = summary_text[:57] + "..."
                    
                    plan_display = f"{summary_text} | {p.calories:.0f}cal, {p.protein:.0f}g protein"
                    plan_options.append(plan_display)
                
                # Create weekly plan selector
                col1, col2 = st.columns(2)
                
                for i, day in enumerate(days):
                    with col1 if i % 2 == 0 else col2:
                        selected_plan_display = st.selectbox(
                            f"**{day}**:",
                            plan_options,
                            key=f"day_{i}"
                        )
                        
                        if selected_plan_display != "-- No Plan --":
                            # Find the selected plan (account for the "-- No Plan --" option)
                            plan_index = plan_options.index(selected_plan_display) - 1
                            weekly_plan[day] = available_plans[plan_index]
                
                # Display selected weekly plan
                if weekly_plan:
                    st.subheader("📋 Your Weekly Plan")
                    
                    # Create summary table
                    weekly_data = []
                    total_calories = 0
                    total_protein = 0
                    total_carbs = 0
                    total_fat_regular = 0
                    total_fat_saturated = 0
                    total_sodium = 0
                    
                    for day in days:
                        if day in weekly_plan:
                            plan = weekly_plan[day]
                            weekly_data.append({
                                'Day': day,
                                'Date': plan.date,
                                'Calories': round(plan.calories),
                                'Protein': round(plan.protein, 1),
                                'Carbs': round(plan.carbs, 1),
                                'Fat_Regular': round(plan.fat_regular, 1),
                                'Fat_Saturated': round(plan.fat_saturated, 1),
                                'Sodium': round(plan.sodium),
                                'Meals': plan.meals.replace('\n', '<br>').replace('&nbsp;', ' ')
                            })
                            total_calories += plan.calories
                            total_protein += plan.protein
                            total_carbs += plan.carbs
                            total_fat_regular += plan.fat_regular
                            total_fat_saturated += plan.fat_saturated
                            total_sodium += plan.sodium
                        else:
                            weekly_data.append({
                                'Day': day,
                                'Date': 'Rest Day',
                                'Calories': 0,
                                'Protein': 0,
                                'Carbs': 0,
                                'Fat_Regular': 0,
                                'Fat_Saturated': 0,
                                'Sodium': 0,
                                'Meals': 'No meals planned'
                            })
                    
                    # Add weekly totals
                    num_planned_days = len(weekly_plan)
                    if num_planned_days > 0:
                        weekly_data.append({
                            'Day': '**WEEKLY TOTAL**',
                            'Date': f'{num_planned_days} days',
                            'Calories': round(total_calories),
                            'Protein': round(total_protein, 1),
                            'Carbs': round(total_carbs, 1),
                            'Fat_Regular': round(total_fat_regular, 1),
                            'Fat_Saturated': round(total_fat_saturated, 1),
                            'Sodium': round(total_sodium),
                            'Meals': f'{num_planned_days} days planned'
                        })
                        
                        weekly_data.append({
                            'Day': '**DAILY AVERAGE**',
                            'Date': 'avg/day',
                            'Calories': round(total_calories / num_planned_days),
                            'Protein': round(total_protein / num_planned_days, 1),
                            'Carbs': round(total_carbs / num_planned_days, 1),
                            'Fat_Regular': round(total_fat_regular / num_planned_days, 1),
                            'Fat_Saturated': round(total_fat_saturated / num_planned_days, 1),
                            'Sodium': round(total_sodium / num_planned_days),
                            'Meals': 'Average per day'
                        })
                    
                    df_weekly = pd.DataFrame(weekly_data)
                    st.markdown(df_weekly.to_html(escape=False, index=False), unsafe_allow_html=True)
                    
                    # Charts with smaller size
                    if num_planned_days > 0:
                        st.subheader("📈 Weekly Macros Trends")
                        
                        import matplotlib.pyplot as plt
                        
                        # Filter out rest days for charts
                        chart_data = [item for item in weekly_data if item['Day'] not in ['**WEEKLY TOTAL**', '**DAILY AVERAGE**'] and item['Calories'] > 0]
                        
                        if len(chart_data) > 1:
                            days_with_plans = [item['Day'] for item in chart_data]
                            calories_data = [item['Calories'] for item in chart_data]
                            fat_data = [item['Fat_Regular'] for item in chart_data]
                            protein_data = [item['Protein'] for item in chart_data]
                            
                            # Smaller charts (reduced figsize)
                            fig1, ax1 = plt.subplots(figsize=(8, 4))
                            ax1.plot(days_with_plans, calories_data, marker='o', linewidth=2, markersize=4)
                            ax1.set_title('Calories per Day', fontsize=12, fontweight='bold')
                            ax1.set_ylabel('Calories', fontsize=10)
                            ax1.grid(True, alpha=0.3)
                            plt.xticks(rotation=45, fontsize=8)
                            plt.tight_layout()
                            st.pyplot(fig1)

                            fig2, ax2 = plt.subplots(figsize=(8, 4))
                            ax2.plot(days_with_plans, fat_data, marker='o', linewidth=2, markersize=4, color='orange')
                            ax2.set_title('Fat per Day', fontsize=12, fontweight='bold')
                            ax2.set_ylabel('Fat (g)', fontsize=10)
                            ax2.grid(True, alpha=0.3)
                            plt.xticks(rotation=45, fontsize=8)
                            plt.tight_layout()
                            st.pyplot(fig2)

                            fig3, ax3 = plt.subplots(figsize=(8, 4))
                            ax3.plot(days_with_plans, protein_data, marker='o', linewidth=2, markersize=4, color='green')
                            ax3.set_title('Protein per Day', fontsize=12, fontweight='bold')
                            ax3.set_ylabel('Protein (g)', fontsize=10)
                            ax3.grid(True, alpha=0.3)
                            plt.xticks(rotation=45, fontsize=8)
                            plt.tight_layout()
                            st.pyplot(fig3)
                            
                            # Store figures for PDF export
                            chart_figures = [fig1, fig2, fig3]
                        
                        # Export buttons
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Excel export
                            towrite = BytesIO()
                            df_weekly.to_excel(towrite, index=False, engine='openpyxl')
                            towrite.seek(0)
                            st.download_button(
                                "📥 Download Excel",
                                data=towrite,
                                file_name=f"weekly_plan_{selected_user.name}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        
                        with col2:
                            # PDF export
                            if st.button("📄 Generate PDF Report"):
                                with st.spinner("Generating PDF report..."):
                                    chart_figs = chart_figures if 'chart_figures' in locals() else None
                                    pdf_buffer = generate_weekly_pdf_report(selected_user, weekly_data, chart_figs)
                                    
                                    if pdf_buffer:
                                        st.download_button(
                                            "📥 Download PDF Report",
                                            data=pdf_buffer,
                                            file_name=f"weekly_plan_{selected_user.name}.pdf",
                                            mime="application/pdf"
                                        )
                                        st.success("PDF report generated successfully!")
                                    else:
                                        st.error("Failed to generate PDF. Make sure reportlab is installed: pip install reportlab")
                
                else:
                    st.info("Select daily plans for the days you want to include in your weekly plan.")

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
