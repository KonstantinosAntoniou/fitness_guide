from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.repositories import UserRepository
from app.core.profile import compute_metrics
from app.core.targets import compute_targets

router = APIRouter(prefix="/users", tags=["users"])


class UserInput(BaseModel):
    name: str
    age: int
    sex: Literal["male", "female"]
    height_cm: float
    weight_kg: float
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"]
    goal_type: Optional[Literal["lose", "gain"]] = None
    goal_period: Optional[Literal["week", "month", "year"]] = None
    amount_kg: Optional[float] = None


class UserOut(BaseModel):
    id: int
    name: str
    metrics: dict
    targets: dict


def _to_out(user) -> "UserOut":
    kw = dict(sex=user.sex, weight_kg=user.weight_kg, height_cm=user.height_cm,
              age=user.age, activity_level=user.activity_level, goal_type=user.goal_type,
              goal_period=user.goal_period, amount_kg=user.amount_kg)
    return UserOut(id=user.id, name=user.name,
                   metrics=compute_metrics(**kw), targets=compute_targets(**kw).__dict__)


@router.post("", status_code=201, response_model=UserOut)
def create_user(payload: UserInput, db: Session = Depends(get_session)) -> UserOut:
    repo = UserRepository(db)
    if repo.find_by_name(payload.name):
        raise HTTPException(status_code=409, detail="user with that name exists")
    user = repo.create(**payload.model_dump())
    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_session)) -> list[UserOut]:
    return [_to_out(u) for u in UserRepository(db).list_all()]


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_session)) -> UserOut:
    user = UserRepository(db).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="not found")
    return _to_out(user)
