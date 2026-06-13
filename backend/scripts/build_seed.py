"""One-off: fetch curated canonical staples from USDA -> app/seed/staples.json.
Run with USDA_API_KEY available: `uv run python scripts/build_seed.py`.

For each staple we give a search query and the REQUIRED tokens (whole words that
must all appear in the result name). USDA names are "Noun, modifier, modifier",
so token matching beats substring/first-word matching. Processed derivatives are
penalised, and anything without a clean match is skipped.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on sys.path

from app.config import load_project_env
from app.integrations.usda import USDAProvider

# (search query, required tokens)
STAPLES = [
    ("chicken breast raw", "chicken breast"), ("egg whole raw", "egg whole"),
    ("salmon raw", "salmon"), ("ground beef raw", "beef ground"),
    ("tuna canned water", "tuna"), ("yogurt greek plain nonfat", "yogurt greek"),
    ("milk reduced fat 2%", "milk"), ("cheddar cheese", "cheddar"),
    ("tofu raw firm", "tofu"), ("lentils cooked", "lentils"),
    ("black beans cooked", "beans black"), ("chickpeas cooked", "chickpeas"),
    ("white rice cooked", "rice white"), ("brown rice cooked", "rice brown"),
    ("oats raw", "oats"), ("bread whole wheat", "bread wheat"),
    ("pasta cooked", "pasta"), ("potato baked", "potato"),
    ("sweet potato cooked", "sweet potato"), ("quinoa cooked", "quinoa"),
    ("broccoli raw", "broccoli"), ("spinach raw", "spinach"),
    ("carrots raw", "carrots"), ("tomatoes raw", "tomatoes"),
    ("peppers sweet red raw", "peppers red"), ("cucumber raw", "cucumber"),
    ("squash zucchini raw", "zucchini"), ("beans snap green raw", "beans green"),
    ("mushrooms white raw", "mushrooms"), ("onions raw", "onions"),
    ("banana raw", "bananas"), ("apples raw", "apples"),
    ("oranges raw", "oranges"), ("strawberries raw", "strawberries"),
    ("blueberries raw", "blueberries"), ("grapes raw", "grapes"),
    ("avocado raw", "avocados"), ("almonds raw", "almonds"),
    ("peanut butter", "peanut butter"), ("walnuts raw", "walnuts"),
    ("olive oil", "oil olive"), ("butter salted", "butter"),
    ("honey", "honey"), ("chocolate dark", "chocolate"),
    ("cottage cheese lowfat", "cottage"), ("shrimp raw", "shrimp"),
    ("pork loin raw", "pork loin"), ("turkey breast raw", "turkey breast"),
    ("cod raw", "cod"), ("edamame", "edamame"),
]

_BAD = ("lunchmeat", "sliced", "condensed", "sweetened", "oil", "flour", "dried",
        "dehydrated", "powder", "juice", "marmalade", "custard", "croissant",
        "leaves", "chips", "cake", "candies", "almond", "cream", "sauce", "soup",
        "bread", "babyfood", "rose", "buttermilk", "restaurant", "infant")


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z]+", s.lower()))


def _best(query: str, key: str, results: list):
    need = key.split()
    cands = [r for r in results if all(w in _tokens(r.name) for w in need)]
    if not cands:
        return None
    qtokens = _tokens(query)

    def score(r):
        toks = _tokens(r.name)
        s = len(r.name) / 40.0
        for bad in _BAD:
            if bad in toks and bad not in qtokens:
                s += 5
        if "raw" in qtokens and "raw" in toks:
            s -= 2
        return s

    return min(cands, key=score)


def main():
    load_project_env()
    provider = USDAProvider()
    out = []
    for query, key in STAPLES:
        try:
            hits = provider.search(query, limit=20, data_types=("Foundation", "SR Legacy"))
        except Exception as e:  # noqa: BLE001
            print(f"err  {query!r}: {e}")
            hits = []
        best = _best(query, key, hits)
        if best:
            out.append(best.model_dump())
            print(f"ok   {key:16} -> {best.name}")
        else:
            print(f"SKIP {key!r} (no clean match)")
    dest = Path(__file__).resolve().parents[1] / "app" / "seed" / "staples.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {len(out)} foods to {dest}")


if __name__ == "__main__":
    main()
