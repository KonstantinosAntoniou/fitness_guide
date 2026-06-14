"""USDA FoodData Central provider — rich macros + micros (per 100 g)."""
import os
import httpx
from app.integrations.nutrition import NutritionResult

# nutrient numbers (consistent across SR Legacy + Foundation)
_N = {"protein": "203", "carbs": "205", "fat": "204", "sat": "606",
      "sugar": "269", "fiber": "291", "sodium": "307", "calcium": "301", "iron": "303",
      "potassium": "306", "vit_c": "401", "vit_d": "328"}
# energy lives under different codes by dataset: 208 (SR Legacy kcal),
# 2048/2047 (Foundation Atwater general/specific), 957/958 (older). Try in order.
_ENERGY = ("208", "2048", "2047", "957", "958")


def parse_usda_food(food: dict) -> NutritionResult:
    vals = {str(n.get("nutrientNumber")): n.get("value") for n in food.get("foodNutrients", [])}

    def num(key):
        v = vals.get(_N[key])
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def energy():
        for code in _ENERGY:
            v = vals.get(code)
            if v not in (None, ""):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return 0.0

    fat_total = num("fat") or 0.0
    sat = num("sat") or 0.0
    return NutritionResult(
        name=str(food.get("description") or "Unknown").strip().title(),
        brand=str(food.get("brandOwner") or "").strip(),
        serving_description="100g", serving_grams=100,
        source="usda", source_id=str(food.get("fdcId")) if food.get("fdcId") else None,
        calories=energy(), protein=num("protein") or 0.0, carbs=num("carbs") or 0.0,
        fat_saturated=sat, fat_unsaturated=max(0.0, fat_total - sat),
        fiber=num("fiber"), sodium=num("sodium") or 0.0,
        sugar_g=num("sugar"), iron_mg=num("iron"), calcium_mg=num("calcium"),
        potassium_mg=num("potassium"), vitamin_c_mg=num("vit_c"), vitamin_d_ug=num("vit_d"),
    )


class USDAProvider:
    BASE = "https://api.nal.usda.gov"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.environ.get("USDA_API_KEY", "DEMO_KEY")
        self._client = client or httpx.Client(base_url=self.BASE, timeout=15.0)

    def search(self, query: str, limit: int = 5,
               data_types: tuple[str, ...] = ("Foundation", "SR Legacy")) -> list[NutritionResult]:
        resp = self._client.get("/fdc/v1/foods/search", params={
            "query": query, "pageSize": limit, "api_key": self.api_key,
            "dataType": ",".join(data_types),
        })
        resp.raise_for_status()
        foods = resp.json().get("foods", [])
        return [parse_usda_food(f) for f in foods][:limit]
