"""Coach agent tools — closures bound to a DB session + user."""
import datetime
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.models import Food, MealItem
from app.repositories import (
    FoodRepository, UserRepository, PlanRepository, LogRepository, MealRepository,
)
from app.core.targets import compute_targets
from app.core.planner import food_spec, meal_ingredient_specs, fit_servings, score_plan
from app.core.macros import scale_food, sum_macros
from app.integrations.openfoodfacts import OpenFoodFactsProvider


def build_tools(session: Session, user_id: int, nutrition_provider=None):
    provider = nutrition_provider or OpenFoodFactsProvider()
    foods = FoodRepository(session)
    users = UserRepository(session)
    plans = PlanRepository(session)
    logs = LogRepository(session)
    meals_repo = MealRepository(session)

    @tool
    def get_profile() -> str:
        """Get the user's profile and daily macro + key-micro targets. Ground all advice in this."""
        u = users.get(user_id)
        if not u:
            return "No profile found for this user."
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
    def plan_day(meals: list[dict]) -> str:
        """Build and save a balanced day plan that hits the user's macro targets.

        `meals` is a list of slots, each {"name": str, "foods": [food names], "meals": [saved meal names]}.
        Choose meal-appropriate, varied foods (a protein, a carb, veg/fruit). The tool sizes servings to
        hit the user's protein/carb/fat targets within realistic limits and returns a scorecard. If a
        macro or key micro is low, change your food selection and call again.
        """
        u = users.get(user_id)
        if not u:
            return "No profile found for this user."
        targets = compute_targets(sex=u.sex, weight_kg=u.weight_kg, height_cm=u.height_cm,
                                  age=u.age, activity_level=u.activity_level, goal_type=u.goal_type,
                                  goal_period=u.goal_period, amount_kg=u.amount_kg)
        slots = []
        for slot in meals or []:
            specs = []
            for fname in slot.get("foods", []):
                hits = foods.search(fname)
                if hits:
                    specs.append(food_spec(hits[0]))
            for mname in slot.get("meals", []):
                meal = meals_repo.find_by_name(mname)
                if meal:
                    specs.extend(meal_ingredient_specs(meal))
            if specs:
                slots.append((slot.get("name", "Meal"), specs))
        all_specs = [s for _, specs in slots for s in specs]
        if not all_specs:
            return ("None of those foods/meals are in the library — add them first "
                    "(search_nutrition_database / add_food_to_library).")

        servings = fit_servings(all_specs, targets.protein_g, targets.carb_g, targets.fat_g)
        draft, idx = [], 0
        for name, specs in slots:
            items = [(s.food, round(servings[idx + i], 2)) for i, s in enumerate(specs)]
            idx += len(specs)
            draft.append({"name": name, "items": items})
        plan = plans.save_draft(user_id=user_id, name="Coach plan", draft=draft)
        session.commit()

        score = score_plan(all_specs, servings, targets)
        pct = score.macro_pct()
        lines = [f"Saved plan #{plan.id}. Totals vs target:",
                 f"  {round(score.calories)} kcal ({pct['calories']:.0f}% of {round(targets.calories)}), "
                 f"protein {score.protein_g}g ({pct['protein']:.0f}%), carbs {score.carb_g}g ({pct['carbs']:.0f}%), "
                 f"fat {score.fat_g}g ({pct['fat']:.0f}%), fiber {score.fiber_g}g."]
        low = [m.replace('_mg', '').replace('_ug', '').replace('vitamin_', 'vit ')
               for m, (got, tgt) in score.micros.items() if tgt and got < 0.5 * tgt]
        lines.append("  Low micros: " + (", ".join(low) if low else "none — looks balanced."))
        for entry in draft:
            foods_txt = ", ".join(f"{q}x {food.name}" for food, q in entry["items"])
            lines.append(f"  {entry['name']}: {foods_txt}")
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

    @tool
    def save_meal(name: str, items: list[dict]) -> str:
        """Save a reusable meal from library foods. items = [{"food": name, "servings": number}]."""
        if meals_repo.find_by_name(name):
            return f"A meal named '{name}' already exists."
        meal = meals_repo.create(name)
        session.flush()
        added = 0
        for it in items:
            hits = foods.search(it.get("food", ""))
            if hits:
                session.add(MealItem(meal_id=meal.id, food_id=hits[0].id,
                                     servings=float(it.get("servings", 1))))
                added += 1
        session.commit()
        return f"Saved meal '{name}' with {added} item(s)."

    @tool
    def list_my_plans() -> str:
        """List the user's saved day plans (id, name, number of meals)."""
        ps = plans.list_for_user(user_id)
        if not ps:
            return "No saved plans yet."
        return "\n".join(f"#{p.id} {p.name} — {len(p.entries)} meals" for p in ps)

    return [get_profile, search_my_foods, search_nutrition_database,
            add_food_to_library, plan_day, log_food, todays_intake,
            save_meal, list_my_plans]
