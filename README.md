# 🥗 Fitness Tracker & Meal Planner

A comprehensive nutrition and training assistant built with **Python**, **Streamlit**, and **PostgreSQL**, designed to help users:

- Log custom foods with detailed macro information
- Create and manage reusable meals with ingredient customization
- Build flexible daily meal plans with real-time macro tracking
- Plan complete weekly meal schedules with visual analytics
- Calculate BMR, TDEE, and personalized caloric targets
- Export detailed meal plans and nutrition reports to PDF
- Track user profiles with personalized goals and progress
- Ask ChatGPT nutrition/training questions inside the app

---

## 🚀 Features

### 👤 User Profile Management
- Create and manage user profiles with personal information (age, sex, height, weight)
- Set personalized goals (weight loss, weight gain, maintenance)
- Track goal periods (per week, per month, per year) and target amounts
- Calculate and display BMR, TDEE, and goal-based target calories
- Edit or delete user profiles with automatic plan updates

### 🧾 Food & Meal Management
- **Food Database**: Add foods with detailed macro information (calories, protein, carbs, fats, sodium)
- **Smart Meal Creation**: Group foods into reusable meals with customizable ingredient ratios
- **Meal Customization**: Adjust individual ingredient quantities when adding meals to daily plans
- **Real-time Macro Calculation**: See macro breakdown and nutritional distribution as you build meals
- **Food Selection Enhancement**: Differentiate foods with same names but different labels/brands

### 📆 Advanced Daily Meal Planning
- **Flexible Meal Structure**: Choose how many meals you eat per day (1-10 meals)
- **Dual Food/Meal Options**: Add individual foods or complete meals to each meal slot
- **Customizable Ingredients**: When adding meals, choose to use default ratios or customize each ingredient
- **Real-time Macro Tracking**: Instantly view total macros with color-coded calorie targets
- **Smart Formatting**: Clean display with calculated measurements (200g instead of 2.0x 100g)
- **Plan Saving**: Save complete daily plans to database with detailed meal breakdowns

### 📅 Weekly Meal Planning & Analytics
- **User-Oriented Planning**: Build weekly schedules from saved daily plans for specific users
- **Comprehensive Plan Selection**: View all meals/foods in each plan with macro summaries
- **Weekly Analytics**: Detailed summary tables with daily totals, weekly totals, and daily averages
- **Visual Charts**: Individual macro trend charts (Calories, Fat, Protein) plus combined overview
- **Flexible Scheduling**: Mix and match different daily plans throughout the week
- **Rest Day Management**: Handle rest days and partial week planning

### 📄 PDF Export & Reporting
- **Comprehensive PDF Reports**: Export complete weekly plans with user info and detailed breakdowns
- **Visual Integration**: Include macro trend charts and nutritional analysis in PDFs
- **Professional Formatting**: Clean, well-structured reports suitable for nutritionists or personal use
- **Complete Data**: User profiles, daily meal details, macro summaries, and visual analytics

### 📊 Advanced Calculators
- **BMR Calculation**: Multiple formulas (Harris-Benedict & Mifflin-St Jeor)
- **TDEE Estimation**: Based on activity level with personalized adjustments
- **Goal-Based Targets**: Calculate calorie needs for specific weight goals and timeframes
- **BMI Tracking**: Automatic BMI calculation with health status indicators
- **Progress Monitoring**: Track changes over time with goal-oriented metrics

### 🗂️ Data Management
- **Saved Plan Management**: View, edit, and delete saved daily plans by user
- **Plan Organization**: Filter plans by user or view all plans with user identification
- **Data Export**: Export food and meal databases to Excel for backup or analysis
- **Database Migration**: Safe schema updates without data loss
- **Bulk Operations**: Manage multiple plans and users efficiently

### 🧠 Integrated AI Assistant
- **ChatGPT Integration**: Ask nutrition and fitness questions directly in the app
- **Context-Aware Responses**: AI responses focused on training and diet topics
- **Real-time Assistance**: Get immediate answers to nutrition and fitness questions

---

## 🛠️ Tech Stack

- **Python 3.10+** - Core programming language
- **Streamlit** - Interactive web frontend framework
- **SQLAlchemy** - Object-Relational Mapping (ORM) for database operations
- **PostgreSQL** - Robust relational database for persistent storage
- **Pandas** - Data manipulation and analysis for meal/food management
- **Matplotlib** - Data visualization for macro trend charts
- **ReportLab** - PDF generation for comprehensive meal plan reports
- **OpenAI API** - ChatGPT integration for nutrition and fitness assistance

---

## 🗃️ Project Structure

```
📁 fitness-tracker/
│
├── app.py                    # Main Streamlit application with all UI components
├── db.py                     # SQLAlchemy database connection setup
├── models.py                 # Database schema (User, Food, Meal, DailyPlan models)
├── foods.py                  # Food management logic and operations
├── meals.py                  # Meal creation and management logic
├── load_from_excel.py        # Excel to database migration utilities
├── reset_database.py         # Database reset functionality
├── migrate_database.py       # Safe database schema migration tools
├── add_user_columns.py       # User table schema updates
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (DATABASE_URL, OPENAI_API_KEY)
├── foods_log.xlsx           # Food database export/backup
├── meals_log.xlsx           # Meal database export/backup
└── README.md                # This documentation file
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
python load_from_excel.py
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

## 📌 Key Features & Usage Notes

### 🎯 Smart Meal Planning
- **Customizable Ingredients**: When adding meals to daily plans, choose between default ratios or customize individual ingredient quantities
- **Real-time Calculations**: All macro calculations update instantly as you modify ingredients or portions
- **Goal-Based Tracking**: Color-coded calorie targets help you stay within your personalized goals

### 📊 Data Management
- **Automatic Updates**: Meal deletion is automatically handled when foods are removed
- **Database-Driven**: All data is stored in PostgreSQL - no Excel files needed for operation
- **Export Options**: Food and meal databases can be exported to Excel for backup or external analysis
- **Safe Migrations**: Database schema updates preserve existing data

### 🔄 User Workflow
1. **Setup**: Create user profile with goals and calculate personalized targets
2. **Build Database**: Add foods and create reusable meals
3. **Daily Planning**: Create daily meal plans with customizable portions
4. **Weekly Scheduling**: Combine daily plans into weekly schedules
5. **Analysis**: View charts, summaries, and export PDF reports

### 💡 Pro Tips
- Use the meal customization feature to adjust portions without creating new meals
- Weekly plans show complete meal breakdowns to help with grocery shopping
- PDF exports include all nutritional data and are perfect for sharing with nutritionists
- The ChatGPT tab is limited to nutrition and training topics for focused assistance

---

