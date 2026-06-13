from fastapi import FastAPI
from app.api.profile import router as profile_router

app = FastAPI(title="Fitness Coach API")
app.include_router(profile_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
