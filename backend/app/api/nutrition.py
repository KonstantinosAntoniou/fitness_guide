from fastapi import APIRouter, Depends, Query
from app.integrations.nutrition import NutritionResult, NutritionProvider
from app.integrations.openfoodfacts import OpenFoodFactsProvider

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


def get_nutrition_provider() -> NutritionProvider:
    return OpenFoodFactsProvider()


@router.get("/search", response_model=list[NutritionResult])
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=25),
    provider: NutritionProvider = Depends(get_nutrition_provider),
) -> list[NutritionResult]:
    return provider.search(q, limit=limit)
