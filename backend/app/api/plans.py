from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.repositories import FoodRepository, PlanRepository
from app.core.planner import build_day_plan
from app.core.macros import scale_food, sum_macros

router = APIRouter(tags=["plans"])


class GenerateRequest(BaseModel):
    target_calories: float
    meals: int = 3
    foods_per_meal: int = 2


class ItemOut(BaseModel):
    food_id: int
    name: str
    servings: float
    calories: float


class EntryOut(BaseModel):
    name: str
    items: list[ItemOut]


class PlanOut(BaseModel):
    id: int
    name: str
    entries: list[EntryOut]
    totals: dict


def _plan_out(plan) -> PlanOut:
    entries, all_macros = [], []
    for entry in plan.entries:
        items = []
        for it in entry.items:
            m = scale_food(it.food, it.servings)
            all_macros.append(m)
            items.append(ItemOut(food_id=it.food_id, name=it.food.name,
                                 servings=round(it.servings, 3), calories=round(m.calories, 1)))
        entries.append(EntryOut(name=entry.name, items=items))
    t = sum_macros(all_macros)
    totals = {"calories": round(t.calories, 1), "protein": round(t.protein, 1),
              "carbs": round(t.carbs, 1), "fat_total": round(t.fat_total, 1)}
    return PlanOut(id=plan.id, name=plan.name, entries=entries, totals=totals)


@router.post("/users/{user_id}/plans/generate", status_code=201, response_model=PlanOut)
def generate_plan(user_id: int, req: GenerateRequest, db: Session = Depends(get_session)) -> PlanOut:
    candidates = FoodRepository(db).list_all()
    try:
        draft = build_day_plan(req.target_calories, candidates, req.meals, req.foods_per_meal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    plan = PlanRepository(db).save_draft(user_id=user_id, name="Generated plan", draft=draft)
    db.commit()
    db.refresh(plan)
    return _plan_out(plan)


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: int, db: Session = Depends(get_session)) -> PlanOut:
    plan = PlanRepository(db).get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="not found")
    return _plan_out(plan)
