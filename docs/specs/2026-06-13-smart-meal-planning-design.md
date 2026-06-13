# Smart Meal Planning — Design

**Date:** 2026-06-13
**Status:** Draft for review
**Supersedes:** the naive `core/planner.build_day_plan` (calorie-only, rotating foods → degenerate portions like "15× almond milk")

## 1. Summary

Replace the naive day-plan builder with a planner that produces **realistic, nutritionally-appropriate** plans: it hits proper **macro** targets (not just calories) within **realistic per-food serving limits**, draws from a **rich, growing food database** (full macros + key micronutrients), can build from **saved custom meals** as well as individual foods, and reports a **micronutrient scorecard** the agent uses to improve its food choices.

Division of labour (decided): **the LLM selects meal-appropriate, varied foods/meals; a deterministic core fits the servings to the macro targets and enforces realism.**

## 2. Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Nutrition depth | Macros + fiber/sodium **+ 5 key micros** (iron, calcium, potassium, vit C, vit D) as **soft** targets |
| Planner engine | **LLM selects, core enforces** (bounded optimisation) |
| Rich data source | **USDA FoodData Central** (key provided) + seed ~150 staples; keep Open Food Facts |
| Library growth | Big seed → every USDA/OFF lookup saves a **fully-characterised** food → backfill/enrich path |
| Custom meals | Saved `Meal`s are **first-class plan building blocks**; ingredients flex ±30% to fit macros |
| Optimiser | **scipy** bounded least-squares (new dep) |

## 3. Targets (`core/targets.py`)

Turn a profile into concrete daily targets (pure functions, unit-tested against known values):

- **Protein (g):** goal-based g/kg bodyweight — `lose` 2.0, `maintain` 1.6, `gain` 1.8.
- **Fat (g):** 25% of target calories (`0.25 * kcal / 9`), with a floor of `0.8 g/kg`.
- **Carbs (g):** remainder — `(kcal − protein*4 − fat*9) / 4`, clamped ≥ 0.
- **Fiber (g):** `14 g per 1000 kcal`.
- **Sodium:** cap `≤ 2300 mg`. **Saturated fat:** cap `≤ 10%` kcal. **Sugar:** cap `≤ 10%` kcal.
- **Micros vs RDA (sex-aware, adult):** iron (M 8 / F 18 mg), calcium 1000 mg, potassium (M 3400 / F 2600 mg), vitamin C (M 90 / F 75 mg), vitamin D 15 µg.

Output: a `NutritionTargets` dataclass (calories, protein_g, carb_g, fat_g, fiber_g, sodium_mg cap, sat_fat_g cap, sugar_g cap, and the 5 micro targets). Surfaced via the profile API and the agent's `get_profile` tool.

## 4. Data model

Extend **`Food`** with per-serving micros (all nullable; existing foods keep working): `sugar_g, iron_mg, calcium_mg, potassium_mg, vitamin_c_mg, vitamin_d_ug`. `serving_grams` already exists; the seed + USDA populate it. A **lightweight additive migration** (`ALTER TABLE ADD COLUMN` if missing) upgrades the existing dev DB; tests use a fresh schema.

`Meal` / `MealItem` already exist (a meal = foods × servings) — no schema change; they become planner inputs.

## 5. Rich, growing food data

- **USDA provider (`integrations/usda.py`)** — same `NutritionProvider` shape as Open Food Facts, returning an **expanded `NutritionResult`** that now carries the micros. Maps USDA nutrient numbers (1003 protein, 1004 fat, 1005 carbs, 1008 kcal, 1079 fiber, 1093 sodium, 2000 sugar, 1258 sat-fat, 1087 calcium, 1089 iron, 1092 potassium, 1162 vit C, 1110/1114 vit D). Uses `USDA_API_KEY` from the root `.env`.
- **Seed (~150 staples)** — a committed `app/seed/staples.json` generated once from USDA (a `scripts/build_seed.py` fetch-and-dump). Shipped in the repo so runtime + tests need **no key**. An idempotent **seeder** loads it (dedup on name+brand).
- **Growth engine** — `add_food` / nutrition-search tools persist the **full** nutrient profile on every save, so the library compounds with use. A small **`enrich`** path backfills micros onto existing foods by USDA match.
- Open Food Facts stays for branded/barcode items (its sparse micros map where present).

## 6. The planner (`core/planner.py`, rewritten)

**`fit_servings(items, targets, *, weights)`** — the deterministic core:
- Decision variables: servings per item. Builds matrix `A` of [protein, carb, fat] per item; solves **bounded least-squares** (`scipy.optimize.lsq_linear`) to minimise weighted distance to `[protein_g, carb_g, fat_g]` subject to per-item bounds.
- **Bounds enforce realism:** a standalone food is `0 … cap` (cap from a sane max, e.g. 4 servings); a **meal's ingredients** are anchored to the recipe and flex within **±30%** (so the meal stays recognisable but its proportions adjust — "fix the analogies a bit").
- Returns servings + a **`PlanScore`**: % of each macro hit, total calories, and each micro vs its target (with fiber/sodium/sat-fat/sugar flagged against caps).

**Building blocks:** the planner accepts a mix of **foods and meals** per meal slot. A meal expands to its ingredient foods with the anchored ±30% bounds; foods get `0…cap`.

This is pure, deterministic, and fully unit-testable (hits macros within tolerance; never exceeds caps; meal ingredients stay within flex).

## 7. LLM + core loop (agent)

Replace the `generate_plan` tool with **`plan_day(meals)`** where `meals = [{name, items:[{food_or_meal, ...}]}]`:
- The **agent composes** balanced, varied meals (protein + carb + veg/fruit; breakfast vs dinner sense; uses saved meals when apt), picking from the library (and adding via USDA/OFF when needed).
- The tool runs **`fit_servings`** against the user's `NutritionTargets`, saves the `Plan`, and returns the **scorecard**.
- **Prompt update:** instruct the agent to review the scorecard and **swap/add a food if a macro or key micro is low** (e.g. low iron → add legumes/spinach), then re-plan. Macros are guaranteed by the core; micros improve through selection.

## 8. API

- Profile endpoint returns full `NutritionTargets` (not just calories).
- `POST /users/{id}/plans/generate` evolves to accept agent-composed selections (or stays callable directly for testing); `GET /plans/{id}` returns the plan + scorecard.
- Nutrition search can query USDA (rich) and OFF.

## 9. Testing

- `core/targets.py` — known-value unit tests (protein/fat/carb/fiber/micros for sample profiles).
- `core/planner.fit_servings` — hits macro targets within tolerance; respects `0…cap`; meal ingredients stay within ±30%; degenerate input handled.
- `integrations/usda.py` — parse fixtures (no live network); a live test gated on `RUN_LIVE_AGENT`/key.
- Seeder — loads ~150 foods, idempotent.
- Agent `plan_day` — tested with a fake/seeded DB (tool logic), LLM mocked.

## 10. Decomposition — two plans

- **Plan A — Targets + rich data foundation:** `core/targets.py`; `Food` micro columns + migration; USDA provider + expanded `NutritionResult`; `staples.json` seed + seeder; profile/`get_profile` expose targets. Ships working + tested.
- **Plan B — The planner + agent:** `fit_servings` + `PlanScore`; foods+meals building blocks with meal flex; `plan_day` tool + prompt; plan API + scorecard. Builds on A.

## 11. Out of scope (later)

- Full RDA optimisation across all vitamins/minerals (this does **soft** key-micro guidance).
- Ingredient-level meal editing UI; multi-day/weekly optimisation.
- Allergy/dislike exclusions (easy to add to bounds later).
