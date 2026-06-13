from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import load_project_env
from app.db import init_db
from app.api.profile import router as profile_router
from app.api.users import router as users_router
from app.api.foods import router as foods_router
from app.api.nutrition import router as nutrition_router
from app.api.plans import router as plans_router
from app.api.logs import router as logs_router
from app.api.coach import router as coach_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_project_env()
    init_db()
    from app.db import engine, SessionLocal
    from app.migration.schema_upgrade import ensure_food_micro_columns
    from app.seed.seeder import seed_staples
    ensure_food_micro_columns(engine)
    with SessionLocal() as s:
        seed_staples(s)
        s.commit()
    yield


app = FastAPI(title="Fitness Coach API", lifespan=lifespan)
app.include_router(profile_router)
app.include_router(users_router)
app.include_router(foods_router)
app.include_router(nutrition_router)
app.include_router(plans_router)
app.include_router(logs_router)
app.include_router(coach_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
