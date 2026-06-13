"""Provider-agnostic nutrition lookup types + Open Food Facts normalization."""
from typing import Optional, Protocol
from pydantic import BaseModel


class NutritionResult(BaseModel):
    name: str
    brand: str = ""
    serving_description: str = "100g"
    serving_grams: Optional[float] = 100
    source: str = "openfoodfacts"
    source_id: Optional[str] = None
    calories: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat_saturated: float = 0.0
    fat_unsaturated: float = 0.0
    fiber: Optional[float] = None
    sodium: float = 0.0
    sugar_g: Optional[float] = None
    iron_mg: Optional[float] = None
    calcium_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    vitamin_c_mg: Optional[float] = None
    vitamin_d_ug: Optional[float] = None


class NutritionProvider(Protocol):
    def search(self, query: str, limit: int = 5) -> list[NutritionResult]:
        ...


def _num(d: dict, key: str, default: float = 0.0) -> float:
    v = d.get(key)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_off_product(product: dict) -> NutritionResult:
    """Open Food Facts product JSON -> NutritionResult (values are per 100g)."""
    n = product.get("nutriments", {}) or {}
    fat_total = _num(n, "fat_100g")
    saturated = _num(n, "saturated-fat_100g")
    fiber = n.get("fiber_100g")
    sugars = n.get("sugars_100g")
    return NutritionResult(
        name=str(product.get("product_name") or "Unknown").strip(),
        brand=str((product.get("brands") or "").split(",")[0]).strip(),
        serving_description="100g",
        serving_grams=100,
        source="openfoodfacts",
        source_id=str(product["code"]) if product.get("code") else None,
        calories=_num(n, "energy-kcal_100g"),
        protein=_num(n, "proteins_100g"),
        carbs=_num(n, "carbohydrates_100g"),
        fat_saturated=saturated,
        fat_unsaturated=max(0.0, fat_total - saturated),
        fiber=float(fiber) if fiber is not None else None,
        sodium=_num(n, "sodium_100g") * 1000,  # OFF sodium is grams -> store mg
        sugar_g=float(sugars) if sugars is not None else None,
    )
