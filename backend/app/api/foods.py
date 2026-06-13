from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.models import Food
from app.repositories import FoodRepository

router = APIRouter(prefix="/foods", tags=["foods"])


class FoodOut(BaseModel):
    id: int
    name: str
    brand: str
    serving_description: str
    calories: float
    protein: float
    carbs: float
    fat_total: float
    sodium: float


class FoodCreate(BaseModel):
    name: str
    brand: str = ""
    serving_description: str = "100g"
    serving_grams: float | None = None
    source: str = "manual"
    source_id: str | None = None
    calories: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat_saturated: float = 0.0
    fat_unsaturated: float = 0.0
    fiber: float | None = None
    sodium: float = 0.0


def _to_out(f: Food) -> FoodOut:
    return FoodOut(
        id=f.id, name=f.name, brand=f.brand, serving_description=f.serving_description,
        calories=f.calories, protein=f.protein, carbs=f.carbs,
        fat_total=f.fat_total, sodium=f.sodium,
    )


@router.get("", response_model=list[FoodOut])
def list_foods(db: Session = Depends(get_session)) -> list[FoodOut]:
    return [_to_out(f) for f in FoodRepository(db).list_all()]


@router.post("", status_code=201, response_model=FoodOut)
def create_food(payload: FoodCreate, db: Session = Depends(get_session)) -> FoodOut:
    repo = FoodRepository(db)
    if repo.find_by_name_brand(payload.name, payload.brand):
        raise HTTPException(status_code=409, detail="food with that name+brand exists")
    food = repo.add(Food(**payload.model_dump()))
    db.commit()
    db.refresh(food)
    return _to_out(food)
