import streamlit as st
import pandas as pd
from foods import Food
from meals import Meal
import os
import matplotlib.pyplot as plt
from io import BytesIO

st.set_page_config(layout='wide')

def display_maximized_table_with_styles(df):
    
    # Replace NaN with a dash
    df = df.fillna('-')

    # Style for full-width table and row coloring
    table_style = """
        <style>
        thead th {text-align: center;}
        tbody th {display:none;}
        .full-width-table {width: 100%;}
        .header-row {background-color: #707070; color: Turquoise; font-weight: bold;}  /* General info row */
        </style>
        """

    # Convert the DataFrame to HTML (without index) and apply row-based styling
    df_html = df.to_html(index=False, classes="full-width-table", border=0)
    
    # Add style to the first row (general info)
    df_html = df_html.replace(
        '<tr style="text-align: right;">',
        '<tr style="text-align: center;" class="header-row">', 1
    )

    # Apply the custom CSS and render the styled table
    st.markdown(table_style, unsafe_allow_html=True)
    st.markdown(df_html, unsafe_allow_html=True)


# Load logged foods
def load_logged_foods():
    try:
        # Read foods from the food log Excel
        df_foods = pd.read_excel('foods_log.xlsx')
        return df_foods
    except FileNotFoundError:
        st.error("No foods logged yet.")
        return pd.DataFrame()

def load_logged_meals():
    try:
        df_meals = pd.read_excel('meals_log.xlsx')
        return df_meals
    except FileNotFoundError:
        return pd.DataFrame()

# Display all logged foods
def display_logged_foods():
    
    hide_table_row_index = """
        <style>
        thead th {text-align: center;}
        tbody th {display:none;}
        .full-width-table {width: 100%;}
        </style>
        """
        
    
    df_foods = load_logged_foods()
    if not df_foods.empty:
        display_maximized_table_with_styles(df_foods)

    else:
        st.write("No foods have been logged yet.")

def display_logged_meals():
    
    df_meals = load_logged_meals()
    
    if not df_meals.empty:
        #st.subheader("Logged Meals")

        # Group meals by 'Meal_Name'
        grouped_meals = df_meals.groupby('Meal_Name')

        # Prepare a list to store the final display data
        meal_display_data = []

        # Iterate through each meal group
        for meal_name, meal_df in grouped_meals:
            # Stack food names vertically (centered) with '\n' for new lines
            food_names = '\n'.join(meal_df[~meal_df['Food_Name'].str.contains('Total')]['Food_Name'].tolist())

            # Extract the 'Total' row for the current meal
            total_row = meal_df[meal_df['Food_Name'].str.contains('Total')].iloc[0]

            # Prepare the row for display (taking values from 'Total' row)
            meal_display_data.append({
                'Meal Name': meal_name,
                'Food Names': food_names,
                'Total Protein': total_row['Protein'],
                'Total Carbs': total_row['Carbs'],
                'Total Fat (Regular)': total_row['Fat_Regular'],
                'Total Fat (Saturated)': total_row['Fat_Saturated'],
                'Total Sodium': total_row['Sodium'],
                'Total Calories': total_row['Calories']  # Assuming the Calories column exists
            })

        df = pd.DataFrame(meal_display_data)

# Replace newlines in 'Food Names' column with '<br>' for HTML line breaks
        df['Food Names'] = df['Food Names'].apply(lambda x: x.replace('\n', '<br>'))

        # Convert the DataFrame to HTML
        table_html = df.to_html(index=False, escape= False, border = 0, classes="full-width-table")

        # Define custom CSS for the header row and font color
        table_style = """
        <style>
        thead th {text-align: center;}
        tbody th {display:none;}
        .full-width-table {width: 100%;}
        .header-row {background-color: #707070; color: Turquoise; font-weight: bold;}  /* General info row */
        </style>
        """
        
        table_html = table_html.replace(
        '<tr style="text-align: right;">',
        '<tr style="text-align: center;" class="header-row">', 1
    )

# Display the styled table with custom CSS
        st.markdown(table_style, unsafe_allow_html=True)
        st.markdown(table_html, unsafe_allow_html = True)

        
    else:
        st.write("No meals have been logged yet.")


# Meal creation function
def create_meal():

    df_foods = load_logged_foods()
    
    if not df_foods.empty:
        # Input for meal name
        meal_name = st.text_input("Enter a name for the meal")

        if meal_name:
            # Multi-select dropdown to choose foods for the meal
            selected_foods = st.multiselect("Select foods for the meal", df_foods['Name'].unique())
            
            meal_data = []
            if selected_foods:
                st.write("Enter the multiplier for each food (e.g., 2x Chicken Breast):")

                # For each selected food, ask for the multiplier
                for food in selected_foods:
                    food_info = df_foods[df_foods['Name'] == food].iloc[0]
                    multiplier = st.number_input(
                        f"Multiplier for {food} ({food_info['Measurement']})", 
                        min_value=0.1, 
                        step=0.1, 
                        key=food
                    )
                    meal_data.append((food, food_info['Label'], multiplier))
            
            # Log the meal when the button is clicked
            if st.button("Create Meal"):
                if meal_data:
                    # Create a Meal object and log it
                    try:
                        meal = Meal(meal_name)
                        answer = meal.create_meal(meal_data)  # Create and log the meal
                        if answer is not None:
                            st.error(answer)
                        else:
                            st.success(f"Meal '{meal_name}' created and logged successfully!")
                    except Exception as e:
                        st.error(f"Error logging meal: {e}")
                else:
                    st.error("Please select at least one food and provide multipliers.")
        else:
            st.error("Please enter a name for the meal.")
    else:
        st.write("No foods available to create a meal. Please log foods first.")


# Function to display the 5-meal day planner
def day_meal_planner():
    st.subheader("Create a 5-Meal Day Plan")
    
    # Load logged meals and foods
    df_meals = load_logged_meals()
    df_foods = load_logged_foods()

    if df_meals.empty and df_foods.empty:
        st.write("No meals or foods logged yet.")
        return

    # Create options for meal times
    meal_times = ["Morning", "Snack 1", "Lunch", "Snack 2", "Dinner"]

    # Create a dictionary to store the user selections for each meal time
    day_plan = {}
    
    total_protein = 0
    total_carbs = 0
    total_fat_regular = 0
    total_fat_saturated = 0
    total_sodium = 0
    total_calories = 0

    for time in meal_times:
        st.write(f"### {time}")

        # User can choose to add either a meal or a food
        option = st.radio(f"Do you want to add a meal or a food for {time}?", ['Meal', 'Food'], key=time)

        if option == 'Meal':
            meal_selected = st.selectbox(f"Select a meal for {time}", df_meals['Meal_Name'].unique(), key=f"meal_{time}")

            # Get the total macros for the selected meal
            if meal_selected:
                meal_data = df_meals[df_meals['Meal_Name'] == meal_selected]
                total_row = meal_data[meal_data['Food_Name'].str.contains('Total')].iloc[0]

                # Sum the macros
                total_protein += total_row['Protein']
                total_carbs += total_row['Carbs']
                total_fat_regular += total_row['Fat_Regular']
                total_fat_saturated += total_row['Fat_Saturated']
                total_sodium += total_row['Sodium']
                total_calories += total_row['Calories']

                day_plan[time] = f"Meal: {meal_selected}"

        elif option == 'Food':
            food_selected = st.selectbox(f"Select a food for {time}", df_foods['Name'].unique(), key=f"food_{time}")

            # Let the user enter the portion (multiplier) for the food
            portion = st.number_input(f"Enter portion multiplier for {food_selected} (measurement = {df_foods['Measurement']})", min_value=0.1, step=0.1, key=f"portion_{time}")

            # Get the macros for the selected food
            if food_selected and portion:
                food_data = df_foods[df_foods['Name'] == food_selected].iloc[0]

                # Multiply the macros by the portion
                total_protein += food_data['Protein'] * portion
                total_carbs += food_data['Carbs'] * portion
                total_fat_regular += food_data['Fat_Regular'] * portion
                total_fat_saturated += food_data['Fat_Saturated'] * portion
                total_sodium += food_data['Sodium'] * portion
                total_calories += food_data['Calories'] * portion

                day_plan[time] = f"Food: {food_selected}, Portion: {portion}x"

    # Display the total macros for the day
    if st.button("Calculate Total Macros for the Day"):
        st.write("## Total Macros for the Day:")
        st.write(f"Total Protein: {round(total_protein,2)}g")
        st.write(f"Total Carbs: {round(total_carbs,2)}g")
        st.write(f"Total Fat (Regular): {round(total_fat_regular,2)}g")
        st.write(f"Total Fat (Saturated): {round(total_fat_saturated,2)}g")
        st.write(f"Total Sodium: {round(total_sodium,2)}g")
        st.write(f"Total Calories: {round(total_calories,2)}")

    # Save the plan (in a new Excel file or existing file)
    if st.button("Save Day Plan"):
        save_day_plan(day_plan, total_protein, total_carbs, total_fat_regular, total_fat_saturated, total_sodium, total_calories)
        st.success("Day plan saved successfully!")


# Function to save the day plan
def save_day_plan(day_plan, total_protein, total_carbs, total_fat_regular, total_fat_saturated, total_sodium, total_calories):
    # Create a DataFrame for saving the day plan
    day_plan_df = pd.DataFrame(day_plan.items(), columns=["Meal Time", "Selection"])

    # Add the total macros as a new row
    total_macros_row = {
        "Meal Time": "Total",
        "Selection": (f"Total Macros: Protein: {round(total_protein,2)}g, Carbs: {round(total_carbs,2)}g, "
                      f"Fat (Regular): {round(total_fat_regular,2)}g, Fat (Saturated): {round(total_fat_saturated,2)}g, "
                      f"Sodium: {round(total_sodium,2)}g, Calories: {round(total_calories,2)}")
    }
    day_plan_df = day_plan_df._append(total_macros_row, ignore_index=True)

    # Define the path to the Excel file
    excel_file = 'daily_meal_plans.xlsx'

    if os.path.exists(excel_file):
        try:
            # Read existing data from the file
            df_existing = pd.read_excel(excel_file, engine='openpyxl')
            # Append the new data
            df_existing = df_existing._append(day_plan_df, ignore_index=True)
        except ValueError as e:
            # Handle case where file content is not a valid Excel format
            print(f"ValueError: {e}. Recreating the file.")
            df_existing = day_plan_df
    else:
        # If the file does not exist, start with the new data
        df_existing = day_plan_df

    # Save the DataFrame to the file
    with pd.ExcelWriter(excel_file, mode='w', engine='openpyxl') as writer:
        df_existing.to_excel(writer, index=False)

def display_logged_day_plans():
    try:
        # Read the data
        df = pd.read_excel('daily_meal_plans.xlsx', engine='openpyxl')

        if df.empty:
            st.write("No daily meal plans logged yet.")
            return

        # Apply custom CSS for maximum table width
        st.markdown("""
            <style>
            .dataframe {
                width: 100% !important;
            }
            table {
                width: 100% !important;
            }
            </style>
            """, unsafe_allow_html=True)

        # Find rows where 'Meal Time' is 'Total' to determine day boundaries
        total_rows = df[df['Meal Time'] == 'Total'].index
        start_index = 0

        for end_index in total_rows:
            # Extract the day's data
            day_df = df.iloc[start_index:end_index + 1]
            st.subheader(f"Day {start_index // 6 + 1}")  # Assuming 6 rows per day including total

            # Display the day's meal plan without index and with maximum width
            st.dataframe(day_df.style.hide(axis='index'), use_container_width=True)

            # Update the start_index to the next day's start
            start_index = end_index + 1

        # Display remaining rows after the last 'Total' if they exist
        if start_index < len(df):
            st.subheader(f"Day {start_index // 6 + 1}")
            st.dataframe(df.iloc[start_index:].style.hide(axis='index'), use_container_width=True)

    except FileNotFoundError:
        st.write("No daily meal plans logged yet.")
    except ValueError as e:
        st.error(f"Error reading the Excel file: {e}")

def delete_food(food_name, food_label):
    try:
        # --- Delete food from foods_log.xlsx ---
        df_foods = pd.read_excel('foods_log.xlsx', engine='openpyxl')

        # Check if the food exists
        food_exists = ((df_foods['Name'].str.lower() == food_name.lower()) & (df_foods['Label'].str.lower() == food_label.lower())).any()
        if not food_exists:
            st.error(f"Food '{food_name}' with label '{food_label}' not found.")
            return

        # Delete the food
        df_foods = df_foods[~((df_foods['Name'] == food_name) & (df_foods['Label'] == food_label))]

        # Save updated foods data
        with pd.ExcelWriter('foods_log.xlsx', engine='openpyxl', mode='w') as writer:
            df_foods.to_excel(writer, index=False)

        # --- Delete meals containing the food from meals.xlsx ---
        df_meals = pd.read_excel('meals_log.xlsx', engine='openpyxl')
        
        # Find meals containing the food
        df_meals_to_remove = df_meals[df_meals['Food_Name'].str.contains(food_name)]
        if not df_meals_to_remove.empty:
            # Get names of the meals to remove
            meal_names_to_remove = df_meals_to_remove['Meal_Name'].unique()

            # Remove these meals from the meal file
            df_meals = df_meals[~df_meals['Meal_Name'].isin(meal_names_to_remove)]
            
            # Save updated meals data
            with pd.ExcelWriter('meals_log.xlsx', engine='openpyxl', mode='w') as writer:
                df_meals.to_excel(writer, index=False)

        # --- Delete daily plans containing the deleted meals from daily_meal_plans.xlsx ---
        df_plans = pd.read_excel('daily_meal_plans.xlsx', engine='openpyxl')

        # Check if any plan contains the deleted meals
        if not df_meals_to_remove.empty:
            df_plans = df_plans[~df_plans['Selection'].isin(meal_names_to_remove)]
            
            # Save updated plans data
            with pd.ExcelWriter('daily_meal_plans.xlsx', engine='openpyxl', mode='w') as writer:
                df_plans.to_excel(writer, index=False)

        st.success(f"Food '{food_name}' with label '{food_label}', related meals, and day plans deleted successfully.")

    except FileNotFoundError as e:
        st.error(f"Error: {e}. File not found.")
    except Exception as e:
        st.error(f"An error occurred: {e}")


# Streamlit UI for deleting a food
def delete_food_ui():
    st.title("Delete a Food")
    
    # Input fields for food name and label
    food_name = st.text_input("Enter the name of the food to delete:")
    food_label = st.text_input("Enter the label of the food to delete:")
    
    if st.button("Delete Food"):
        if food_name and food_label:
            delete_food(food_name, food_label)
            st.success("Food successfully deleted")
        else:
            st.error("Please provide both the food name and label.")


def add_food_via_string(input_string):
    try:
        # Split the input string into a list using semicolons
        properties = [prop.strip() for prop in input_string.split(';')]

        # Check if we have exactly 9 properties
        if len(properties) != 9:
            st.error("Error: Please provide exactly 9 properties separated by semicolons.")
            return

        # Unpack properties
        name, label, measurement, calories, protein, carbs, total_fat, saturated_fat, sodium = properties

        # Validate mandatory fields (name, label, measurement)
        if not name or not label or not measurement:
            st.error("Error: Name, Label, and Measurement are required fields.")
            return

        # Validate numeric fields (calories, protein, carbs, total_fat, saturated_fat, sodium)
        try:
            calories = float(calories)
            protein = float(protein)
            carbs = float(carbs)
            total_fat = float(total_fat)
            saturated_fat = float(saturated_fat)
            sodium = float(sodium)
        except ValueError:
            st.error("Error: Calories, Protein, Carbs, Total Fat, Saturated Fat, and Sodium must be numeric values.")
            return

        # Check if the food is already logged (by name and label)
        food = Food(
                    name=name,
                    label=label,
                    measurement=measurement,
                    calories=calories,
                    protein=protein,
                    carbs=carbs,
                    fat_saturated=saturated_fat,
                    fat_regular=total_fat,
                    sodium=sodium
                )
        food.log_food()

    except Exception as e:
        st.error(f"An error occurred: {e}")

# UI for adding food using a semicolon-separated string
def add_food_string_ui():
    st.title("Add a New Food (via Semicolon-Separated Input)")

    # Input field for semicolon-separated string
    input_string = st.text_input(
        "Enter food details as a semicolon-separated string (e.g., Chicken Breast;Meat;100g;200;30;0;5;1;50)"
    )
    st.write("Format: Name;Label;Measurement;Calories;Protein;Carbs;Total Fat;Saturated Fat;Sodium")

    # Button to add the food
    if st.button("Add Food"):
        if input_string:
            add_food_via_string(input_string)
            st.success("Food added successfully")
        else:
            st.error("Please enter the food details.")


# Define the main app
def food_logger_app():
    st.title("Meal Planning and Food Logging Application")

    # Tabs for functionality
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Log a Food", "View Logged Foods", "Create a Meal", "View Logged Meals", "5-Meal Daily Planner", "View Logged Daily Plans"])

    # Log a new food
    with tab1:
        st.header("Add a New Food")
        with st.form(key='food_form'):
            # Input fields for food details
            food_name = st.text_input("Enter food name")
            food_label = st.text_input("Enter food label (e.g., Protein-Rich, Carb-Rich)")
            measurement = st.text_input("Enter measurement (e.g., 100g, 1 cup)")
            calories = st.number_input("Enter calories (e.g., 350)", min_value=0.0, step = 10.0)
            protein = st.number_input("Enter protein content (in grams)", min_value=0.0, step=0.1)
            carbs = st.number_input("Enter carbohydrates content (in grams)", min_value=0.0, step=0.1)
            fat_saturated = st.number_input("Enter saturated fat content (in grams)", min_value=0.0, step=0.1)
            fat_regular = st.number_input("Enter regular fat content (in grams)", min_value=0.0, step=0.1)
            sodium = st.number_input("Enter sodium content (in g)", min_value=0.0, step=1.0)

            # Submit button for the form
            submit_button = st.form_submit_button(label='Log Food')

        # When the user submits the form
        if submit_button:
            if food_name and food_label and measurement:
                # Log the food using the Food class
                food = Food(
                    name=food_name,
                    label=food_label,
                    measurement=measurement,
                    calories=calories,
                    protein=protein,
                    carbs=carbs,
                    fat_saturated=fat_saturated,
                    fat_regular=fat_regular,
                    sodium=sodium
                )
                # food.log_food()
                # st.success(f"Food '{food_name}' logged successfully!")
                st.success(food.log_food())
            else:
                st.error("Please fill out all required fields.")
        
        add_food_string_ui()
        
        delete_food_ui()


    # View all logged foods
    with tab2:
        st.header("Logged Foods")
        display_logged_foods()

    # Create a meal using logged foods
    with tab3:
        st.header("Create a Meal")
        create_meal()
        
    with tab4:
        st.header("Logged Meals")
        display_logged_meals()
        
    with tab5:
        st.header("5-Meal Day Planner")
        day_meal_planner()
        
    with tab6:
        st.header("View Daily Plans")
        display_logged_day_plans()

# Running the app
if __name__ == "__main__":
    food_logger_app()
