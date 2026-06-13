"""Coach agent tools — closures bound to a DB session + user."""
import datetime
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.models import Food
from app.repositories import FoodRepository, UserRepository, PlanRepository, LogRepository
from app.core.profile import compute_metrics
from app.core.planner import build_day_plan
from app.core.macros import scale_food, sum_macros
from app.integrations.openfoodfacts import OpenFoodFactsProvider


def build_tools(session: Session, user_id: int, nutrition_provider=None):
    provider = nutrition_provider or OpenFoodFactsProvider()
    foods = FoodRepository(session)
    users = UserRepository(session)
    plans = PlanRepository(session)
    logs = LogRepository(session)

    @tool
    def get_profile() -> str:
        """Get the user's profile and daily macro + key-micro targets. Ground all advice in this."""
        u = users.get(user_id)
        if not u:
            return "No profile found for this user."
        from app.core.targets import compute_targets
        t = compute_targets(sex=u.sex, weight_kg=u.weight_kg, height_cm=u.height_cm, age=u.age,
                            activity_level=u.activity_level, goal_type=u.goal_type,
                            goal_period=u.goal_period, amount_kg=u.amount_kg)
        return (f"{u.name}: {round(t.calories)} kcal/day | protein {round(t.protein_g)}g, "
                f"carbs {round(t.carb_g)}g, fat {round(t.fat_g)}g, fiber {round(t.fiber_g)}g. "
                f"Micro goals: iron {t.iron_mg}mg, calcium {t.calcium_mg}mg, potassium {t.potassium_mg}mg, "
                f"vit C {t.vitamin_c_mg}mg, vit D {t.vitamin_d_ug}ug. Sodium cap {round(t.sodium_mg_max)}mg.")

    @tool
    def search_my_foods(query: str) -> str:
        """Search the user's saved food library by name. Returns matches with per-serving calories."""
        results = foods.search(query)
        if not results:
            return f"No saved foods match '{query}'."
        return "\n".join(f"#{f.id} {f.name} ({f.brand}) — {f.calories} kcal / {f.serving_description}"
                         for f in results[:10])

    @tool
    def search_nutrition_database(query: str) -> str:
        """Look up a food's macros from Open Food Facts when it's not in the user's library (values per 100g)."""
        results = provider.search(query, limit=5)
        if not results:
            return f"No nutrition data found for '{query}'."
        return "\n".join(
            f"{r.name} ({r.brand}) — {r.calories} kcal, P{r.protein}/C{r.carbs}/"
            f"F{round(r.fat_saturated + r.fat_unsaturated, 1)} per 100g" for r in results)

    @tool
    def add_food_to_library(name: str, calories: float, protein: float = 0.0,
                            carbs: float = 0.0, fat: float = 0.0,
                            serving_description: str = "100g", brand: str = "") -> str:
        """Add a new food to the user's library (macros per serving) so it can be planned or logged."""
        if foods.find_by_name_brand(name, brand):
            return f"'{name}' is already in the library."
        f = foods.add(Food(name=name, brand=brand, serving_description=serving_description,
                           calories=calories, protein=protein, carbs=carbs,
                           fat_unsaturated=fat, source="agent"))
        session.commit()
        return f"Added '{name}' (#{f.id})."

    @tool
    def generate_plan(target_calories: float, meals: int = 3) -> str:
        """Generate and save a day meal plan from the user's food library hitting the calorie target."""
        candidates = foods.list_all()
        try:
            draft = build_day_plan(target_calories, candidates, meals=meals)
        except ValueError as e:
            return f"Could not build a plan: {e}"
        plan = plans.save_draft(user_id=user_id, name="Coach plan", draft=draft)
        session.commit()
        lines = [f"Saved plan #{plan.id} (~{round(target_calories)} kcal):"]
        for entry in plan.entries:
            items = ", ".join(f"{round(it.servings, 1)}x {it.food.name}" for it in entry.items)
            lines.append(f"- {entry.name}: {items}")
        return "\n".join(lines)

    @tool
    def log_food(name: str, servings: float = 1.0) -> str:
        """Log that the user ate a food from their library, by name. `servings` = how many servings."""
        matches = foods.search(name)
        if not matches:
            return f"'{name}' is not in the library — add it first with add_food_to_library."
        food = matches[0]
        logs.add(user_id=user_id, food_id=food.id, servings=servings, source="agent")
        session.commit()
        return f"Logged {servings}x {food.name} ({round(food.calories * servings)} kcal)."

    @tool
    def todays_intake() -> str:
        """Summarize what the user has logged today (calories + macros)."""
        entries = logs.for_day(user_id, datetime.date.today())
        if not entries:
            return "Nothing logged today yet."
        total = sum_macros([scale_food(e.food, e.servings) for e in entries])
        return (f"Today: {round(total.calories)} kcal, P{round(total.protein)} "
                f"C{round(total.carbs)} F{round(total.fat_total)} across {len(entries)} items.")

    return [get_profile, search_my_foods, search_nutrition_database,
            add_food_to_library, generate_plan, log_food, todays_intake]
