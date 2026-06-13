import httpx
from app.integrations.openfoodfacts import OpenFoodFactsProvider

OFF_RESPONSE = {
    "count": 1,
    "products": [{
        "code": "111",
        "product_name": "Greek Yogurt",
        "brands": "Total",
        "nutriments": {
            "energy-kcal_100g": 59, "proteins_100g": 10, "carbohydrates_100g": 3.6,
            "fat_100g": 0.4, "saturated-fat_100g": 0.3, "sodium_100g": 0.05,
        },
    }],
}


def _provider_with(response: dict) -> OpenFoodFactsProvider:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=response)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=OpenFoodFactsProvider.BASE)
    p = OpenFoodFactsProvider(client=client)
    p._captured = captured  # for assertions
    return p


def test_search_parses_results():
    p = _provider_with(OFF_RESPONSE)
    results = p.search("yogurt", limit=3)
    assert len(results) == 1
    assert results[0].name == "Greek Yogurt"
    assert results[0].calories == 59
    assert results[0].source == "openfoodfacts"
    # the query reached the search endpoint with our term
    assert "search_terms=yogurt" in p._captured["url"]


def test_search_skips_products_without_calories():
    resp = {"products": [{"product_name": "No Macros", "nutriments": {}}]}
    p = _provider_with(resp)
    assert p.search("x") == []
