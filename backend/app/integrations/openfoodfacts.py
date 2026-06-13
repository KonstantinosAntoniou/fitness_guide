"""Open Food Facts nutrition provider."""
import httpx
from app.integrations.nutrition import NutritionResult, parse_off_product

_FIELDS = "code,product_name,brands,nutriments"


class OpenFoodFactsProvider:
    BASE = "https://world.openfoodfacts.org"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            base_url=self.BASE,
            timeout=10.0,
            headers={"User-Agent": "fitness-coach/0.1 (personal project)"},
        )

    def search(self, query: str, limit: int = 5) -> list[NutritionResult]:
        resp = self._client.get(
            "/cgi/search.pl",
            params={
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": limit,
                "fields": _FIELDS,
            },
        )
        resp.raise_for_status()
        products = resp.json().get("products", [])
        results = [parse_off_product(p) for p in products]
        # keep only usable results (real calorie data)
        return [r for r in results if r.calories > 0][:limit]
