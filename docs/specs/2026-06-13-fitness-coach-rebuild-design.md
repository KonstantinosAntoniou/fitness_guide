# Fitness Coach — Rebuild Design

**Date:** 2026-06-13
**Status:** Draft for review
**Repo:** `KonstantinosAntoniou/fitness_guide` (to be moved to `~/Projects/fitness`)

## 1. Summary

Rebuild the existing Streamlit fitness tracker as a clean, modern, AI-first
application. Keep the good domain ideas (profiles, BMR/TDEE/target-calorie math,
food/meal/plan modelling, weekly analytics, PDF export) and rebuild around:

- a **Python / FastAPI** backend that owns all logic and the AI agent, and
- a **Next.js (React + TypeScript)** frontend.

The headline upgrade is the AI: instead of a generic ChatGPT tab, a single
**LangGraph agent** (powered by **Google Gemini**) that can generate meal plans,
log meals from natural language, and answer coaching questions grounded in the
user's own data.

## 2. Goals

1. Generate daily/weekly meal plans that hit the user's calorie + macro targets.
2. Conversational logging — "I had 2 eggs and toast" becomes accurate, structured entries.
3. Coaching Q&A grounded in the user's real foods, plans, and history.
4. A clean, layered, tested architecture that is enjoyable to extend.
5. Built so "local now" becomes "deployed later" with no rewrite.

This is also explicitly a **learning + portfolio** project — the modern stack is
part of the point.

## 3. Non-goals (deferred / out of scope)

- **Adaptive planning** (auto-adjusting plans from adherence) — the data model
  leaves room for it via the log, but it is not built now.
- **Multi-user / authentication** — single user (the owner) for now.
- **Native mobile app** — a responsive/PWA web UI is the bridge.
- **Vector RAG** — structured DB context is sufficient for grounded coaching; no
  embeddings store until proven necessary (YAGNI).

## 4. Decisions log

| Decision | Choice | Rationale |
|---|---|---|
| Platform | Full web rebuild | Learning/portfolio + deployable later |
| Backend | Python · FastAPI | Hosts domain logic + LangGraph agent |
| Frontend | Next.js (React + TS) | Portfolio-grade, easy Vercel deploy, room to grow |
| Audience | Single user, local now | Drops auth + heavy infra; deploy later via env swap |
| Database | SQLite now → Postgres-ready | Zero-setup locally; one env var to swap |
| AI framework | LangGraph | Stateful, tool-using agent |
| LLM provider | Google Gemini | User has the most credits there |
| Nutrition data | Open Food Facts (USDA seam later) | Free, no key, global/EU coverage, barcodes |
| Existing data | Migrate foods + meals; plans fresh | Keep curated library; data model is changing |
| Repo | Move to `~/Projects/fitness`, same remote | Off the Desktop, keep history |

## 5. Architecture

Monorepo:

```
fitness/
├── backend/                # Python · FastAPI · the brain
│   └── app/
│       ├── api/            # FastAPI routes — thin HTTP layer only
│       ├── core/           # domain logic: BMR/TDEE/targets, macro math,
│       │                   #   plan builder. Pure, framework-free, unit-tested.
│       ├── agent/          # LangGraph agent + tool definitions
│       ├── integrations/   # nutrition API client (Open Food Facts; USDA seam)
│       ├── db/             # SQLAlchemy models + session/engine
│       ├── repositories/   # data access — keeps SQL out of routes & agent
│       └── config.py       # pydantic-settings, env-driven
│   └── tests/
├── frontend/               # Next.js · React · TypeScript
└── docs/
```

**Layering rule:** dependencies point inward. `core/` depends on nothing in the
app. `repositories/` depend on `db/`. `agent/` tools call `core/` +
`repositories/` + `integrations/` — never raw SQL. `api/` is a thin adapter over
all of it. This is what makes the logic testable and reusable by the API, the
agent, and any future client.

## 6. Data model

Replaces the current denormalized `DailyPlan.meals` string with structured rows.
**Nutrient values are stored per serving** (legacy data is per-serving with no
gram weight). `Food` carries a `serving_description` and an optional
`serving_grams`; quantities are **servings** (float). Macros are always computed
from structured items, never frozen.

- **User** — profile inputs only: `name, age, sex, height_cm, weight_kg,
  activity_level`, plus goal (`goal_type, goal_period, weight_change_amount`).
  BMR/TDEE/target-calories are **computed in `core/` on demand** (single source of
  truth) rather than stored as stale columns.
- **Food** — `name, brand, serving_description, serving_grams (optional), source
  (manual|legacy|openfoodfacts|usda), source_id`, and per-serving nutrients:
  `calories, protein, carbs, fat_saturated, fat_unsaturated, fiber, sodium`
  (`fat_total` = saturated + unsaturated, computed).
- **Meal** (reusable recipe) — `name`; has many **MealItem** (`food_id, servings`).
- **Plan** — `user_id, name/date, type (template|dated)`; has many **PlanEntry**
  (a meal slot: `name, order`); each entry has many **PlanItem** (`food_id` or
  `meal_id`, `grams`).
- **LogEntry** — what was actually eaten: `user_id, eaten_at, food_id, grams,
  source (manual|conversational)`. Conversational logging writes here; enables
  future adaptive planning.
- **Agent persistence** — LangGraph checkpointer (SQLite) for conversation state;
  a lightweight messages table backs the coaching chat UI.

## 7. The AI agent

A single **LangGraph** tool-calling agent (ReAct-style). Provider: **Google
Gemini** via `langchain-google-genai` (AI Studio key) or `langchain-google-vertexai`
(Vertex + GCP credits) — provider is swappable through LangChain.

**Tools** (each delegates to `core` / `repositories` / `integrations`; the agent
touches no SQL):

- `search_nutrition(query)` → resolve a food via Open Food Facts; return per-100g macros.
- `find_food(query)` / `add_food(...)` → read/write the user's food DB.
- `generate_meal_plan(targets, preferences)` → assemble a plan hitting targets.
- `log_meal(text)` → parse natural language into `LogEntry` rows.
- `get_profile_and_history()` → ground coaching answers in real data.

**Critical design principle — LLM judges, `core` computes.** The LLM never does
macro arithmetic. `core/` owns a deterministic plan-builder (given target macros,
a candidate food set, and constraints like meals/day and preferences, it assigns
portions to hit targets within tolerance). The LLM chooses *which* foods and
handles variety/preferences, then calls the builder. This keeps numbers correct.

**Logging UX:** parse → show the user the structured interpretation → confirm
before writing. No silent bad logs.

## 8. Nutrition integration

Start with **Open Food Facts**: free, no API key, global + European coverage,
barcode lookup (useful for future phone use). The `integrations/` layer exposes a
provider-agnostic interface so **USDA FoodData Central** can be added later for
generic whole-food accuracy without touching callers. API responses are
normalized to the per-100g `Food` shape on the way in.

## 9. Migration

A one-time script seeds the new SQLite DB from existing data. Source of truth is
the portable Excel exports (`foods_log.xlsx`, `meals_log.xlsx`) — the live
Postgres DB may not be running. Migrate **foods + meals**; map the old fat
split (`fat_saturated` / `fat_regular`) and normalize old per-measurement values
to per-100g. Plans start fresh because the model changed.

## 10. Deploy-later (no rewrite)

- Config via `pydantic-settings` + `.env`; `DATABASE_URL` swaps SQLite↔Postgres untouched.
- Dockerfile per service + `docker-compose` for full local stack.
- Path to hosting: frontend → Vercel, backend → Railway/Fly/Render, DB → managed Postgres. Secrets via env.

## 11. Testing

- `core/` — real unit tests: BMR/TDEE vs known values, macro aggregation,
  plan-builder hits targets within tolerance. This is the must-be-correct code.
- `integrations/` — recorded fixtures (no live network in tests).
- `agent/` — tools tested against fakes; a few live-model integration tests gated behind a flag.
- `api/` — FastAPI `TestClient`.

## 12. Repo move & git strategy

1. Handle uncommitted WIP: the in-progress `app.py` macro fix and `mini_app.py`
   debug scratch are throwaway given the rebuild (confirm before discarding).
2. Rebuild happens on a **`rebuild/ai-fitness-coach` branch**; `main` keeps the
   current working app as a fallback until the rebuild is ready to take over.
3. Move `~/Desktop/projects/fitness` → `~/Projects/fitness` (git history + remote
   travel with it). Done as an early implementation step.
4. Remove leftover cruft: `mini_app.py`, `echo=True` and stray prints in `db.py`.

## 13. Open questions (resolve during planning)

1. **Google access path:** Vertex AI (GCP project + credits — likely, given
   "credits") or Gemini Developer API (AI Studio key)?
2. **Gemini model:** 2.5 Flash (fast/cheap) vs 2.5 Pro (stronger reasoning) — pick
   at build time; likely Flash for tools, Pro for coaching.
3. **Keep old app on `main`** as fallback during the rebuild — assumed yes.
4. **Discard the uncommitted WIP** `app.py` changes — assumed yes (rebuilding).
