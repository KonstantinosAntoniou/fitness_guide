import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.repositories import LogRepository
from app.core.macros import scale_food, sum_macros

router = APIRouter(tags=["logs"])


class LogRequest(BaseModel):
    food_id: int
    servings: float = 1.0
    source: str = "manual"


class LogItemOut(BaseModel):
    food_id: int
    name: str
    servings: float
    calories: float


class DaySummary(BaseModel):
    day: datetime.date
    entries: list[LogItemOut]
    totals: dict


@router.post("/users/{user_id}/log", status_code=201)
def log_food(user_id: int, req: LogRequest, db: Session = Depends(get_session)) -> dict:
    entry = LogRepository(db).add(user_id=user_id, food_id=req.food_id,
                                  servings=req.servings, source=req.source)
    db.commit()
    return {"id": entry.id}


@router.get("/users/{user_id}/log/today", response_model=DaySummary)
def day_summary(user_id: int, db: Session = Depends(get_session)) -> DaySummary:
    today = datetime.date.today()
    entries = LogRepository(db).for_day(user_id, today)
    items, macros = [], []
    for e in entries:
        m = scale_food(e.food, e.servings)
        macros.append(m)
        items.append(LogItemOut(food_id=e.food_id, name=e.food.name,
                                servings=e.servings, calories=round(m.calories, 1)))
    t = sum_macros(macros)
    totals = {"calories": round(t.calories, 1), "protein": round(t.protein, 1),
              "carbs": round(t.carbs, 1), "fat_total": round(t.fat_total, 1)}
    return DaySummary(day=today, entries=items, totals=totals)
