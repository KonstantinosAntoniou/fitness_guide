# 🥗 Fitness Tracker & Meal Planner

A full-featured nutrition and training assistant built with **Python**, **Streamlit**, and **PostgreSQL**, designed to help users:

- Log custom foods and their macros
- Create reusable meals
- Build flexible daily meal plans
- Track macro goals (calories, protein, carbs, fats, sodium)
- Calculate BMR, TDEE, and caloric targets for weight gain/loss
- Ask ChatGPT nutrition/training questions inside the app

---

## 🚀 Features

### 🧾 Food & Meal Logging
- Add foods with macro details (calories, protein, carbs, fats, sodium)
- Delete foods (automatically removes affected meals)
- Group foods into reusable meals with total macro summaries

### 📆 Daily Meal Planning
- Choose how many meals you eat per day
- Add foods or full meals to each meal slot
- Instantly view total macros for the day
- Save your day plan to the database

### 🧠 Integrated ChatGPT Tab
- Ask nutrition and fitness questions directly inside the app
- Responses powered by OpenAI's GPT model (limited to training/diet topics)

### 📊 Calculators
- Calculate BMR (Harris-Benedict & Mifflin-St Jeor)
- Estimate TDEE based on activity level
- Set calorie goals to gain/lose weight over different timeframes
- Auto-calculates BMI from height and weight

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **Streamlit** for frontend
- **SQLAlchemy** for ORM
- **PostgreSQL** for persistent database storage
- **OpenAI API** for ChatGPT integration

---

## 🗃️ Project Structure

```
📁 project-root/
│
├── app.py                  # Main Streamlit interface
├── db.py                   # SQLAlchemy setup
├── models.py               # Database schema
├── foods.py                # Food logic
├── meals.py                # Meal logic
├── load_excel_to_db.py     # Excel -> DB migration script
├── reset_database.py       # Wipe all records for a fresh start
├── requirements.txt
├── .env                    # Holds DATABASE_URL and OPENAI_API_KEY
└── daily_meal_plans.xlsx   # (Deprecated) used before DB migration
```

---

## ⚙️ Getting Started

### 1. Clone the Repo
```bash
git clone https://github.com/KonstantinosAntoniou/fitness-planner.git
cd fitness-planner
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Requirements
```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables
Create a `.env` file in the root:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/fitness_db
OPENAI_API_KEY=sk-...
```

### 5. Initialize Database & Load Data
```bash
python load_excel_to_db.py
```

### 6. Run the App
```bash
streamlit run app.py
```

---

## 🧼 Reset the Database (Optional)

To clear all foods, meals, and day plans:

```bash
python reset_database.py
```

---

## 📌 Notes

- Meal deletion is automatically handled when foods are removed.
- The app saves all data in a PostgreSQL database — no Excel files needed.
- Daily plans are saved in the `daily_plans` table.
- Only nutrition and training questions are accepted in the ChatGPT tab.

---

