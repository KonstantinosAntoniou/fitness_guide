from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import init_db
from app.api.profile import router as profile_router
from app.api.users import router as users_router
from app.api.foods import router as foods_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Fitness Coach API", lifespan=lifespan)
app.include_router(profile_router)
app.include_router(users_router)
app.include_router(foods_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
