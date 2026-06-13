from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
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


@router.get("", response_model=list[FoodOut])
def list_foods(db: Session = Depends(get_session)) -> list[FoodOut]:
    out = []
    for f in FoodRepository(db).list_all():
        out.append(FoodOut(
            id=f.id, name=f.name, brand=f.brand, serving_description=f.serving_description,
            calories=f.calories, protein=f.protein, carbs=f.carbs,
            fat_total=f.fat_total, sodium=f.sodium,
        ))
    return out
