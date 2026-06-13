from typing import Literal, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.core.profile import compute_metrics

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileInput(BaseModel):
    sex: Literal["male", "female"]
    weight_kg: float
    height_cm: float
    age: int
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"]
    goal_type: Optional[Literal["lose", "gain"]] = None
    goal_period: Optional[Literal["week", "month", "year"]] = None
    amount_kg: Optional[float] = None


class MetricsOutput(BaseModel):
    bmr_msj: float
    bmr_hb: float
    tdee_msj: float
    tdee_hb: float
    bmi: float
    bmi_category: str
    target_calories: float


@router.post("/metrics", response_model=MetricsOutput)
def profile_metrics(payload: ProfileInput) -> MetricsOutput:
    return MetricsOutput(**compute_metrics(**payload.model_dump()))
