"""One-off: build micronutrient enrichment for the legacy foods -> app/seed/legacy_micros.json.
Run with USDA_API_KEY: `PYTHONPATH=$(pwd) uv run python scripts/build_enrichment.py`.

Macros stay as the user entered them; we only source the 5 micros (+ fiber/sugar) from a
category-appropriate USDA food and scale to each food's serving grams. Greek items map to
their category (Fakes=lentils, Tsipoura=sea bass, Kefalotiri=parmesan, Paksimadi=rusk).
Pure supplements / candy are skipped (micros not meaningful).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_project_env
from app.integrations.usda import USDAProvider

# legacy Food.name (lowercased) -> (USDA query [distinctive noun first], serving grams)
SOURCES = {
    "honey": ("honey", 21), "apple": ("apples raw", 182), "oats": ("oats rolled dry", 100),
    "peanutbutter": ("peanut butter", 100), "egg": ("egg whole raw", 50),
    "cucumber": ("cucumber raw", 150), "groundbeaf": ("beef ground raw", 100),
    "banana": ("bananas raw", 118), "egg_white": ("egg white raw", 33),
    "rasberries": ("raspberries raw", 100), "strawberries": ("strawberries raw", 100),
    "bread": ("bread whole wheat", 30), "chichen": ("chicken breast raw", 100),
    "tomato": ("tomatoes raw", 100), "spinach": ("spinach raw", 100),
    "babypotatos": ("potatoes raw", 100), "fakes": ("lentils cooked", 100),
    "almondmilk": ("almond milk unsweetened", 100), "rice": ("rice white cooked", 100),
    "mustard": ("mustard prepared", 5), "yogurt_sauce": ("yogurt plain whole", 100),
    "beef_stake": ("beef steak cooked", 100), "corn_boiled": ("corn sweet cooked", 100),
    "tsipoura": ("bass raw", 100), "feta_cheese": ("feta cheese", 100),
    "olives": ("olives ripe", 4), "penes": ("pasta cooked", 100), "pita": ("pita bread", 100),
    "cheese": ("gouda cheese", 100), "tuna(water)": ("tuna canned water", 100),
    "tortilla": ("tortilla flour", 62), "yogurt": ("yogurt greek plain", 100),
    "ground beef": ("beef ground raw", 100), "granola": ("granola", 100),
    "almond milk": ("almond milk unsweetened", 100), "egg whites": ("egg white raw", 100),
    "cashews": ("cashew nuts raw", 100), "walnuts": ("walnuts raw", 100),
    "forest fruits": ("blackberries raw", 100), "dates": ("dates medjool", 100),
    "straberry jam": ("jams preserves", 100), "pita kalampokiou": ("tortilla corn", 82),
    "turkey patties": ("turkey ground cooked", 85), "rice porridge": ("rice white cooked", 100),
    "oliveoil": ("oil olive", 14), "rice porridge - speculus": ("rice white cooked", 100),
    "chia": ("chia seeds", 100), "cacoa powder": ("cocoa powder", 100),
    "milk 1.7%": ("milk reduced fat", 100), "cottage": ("cottage cheese lowfat", 100),
    "ygeias almond": ("chocolate dark", 100), "kefalotiri": ("parmesan cheese", 100),
    "pennes_olikis": ("pasta whole wheat cooked", 100), "pesto": ("basil raw", 100),
    "striploin": ("beef steak cooked", 100),
}


def _tokens(s):
    return set(re.findall(r"[a-z]+", s.lower()))


_BAD = ("salami", "candy", "bar", "mix", "beverages", "snacks", "dried", "dehydrated",
        "powder", "sauce", "juice", "cake", "fried", "breaded", "cured", "smoked",
        "glazed", "oil", "soup", "infant", "babyfood")


def _pick(query, hits):
    need = query.split()[0]
    qt = _tokens(query)
    cands = [h for h in hits if need in _tokens(h.name)]
    if not cands:
        return None

    def score(h):
        t = _tokens(h.name)
        s = len(h.name) / 40.0
        for bad in _BAD:
            if bad in t and bad not in qt:
                s += 5
        if "raw" in qt and "raw" in t:
            s -= 2
        return s

    return min(cands, key=score)


def main():
    load_project_env()
    provider = USDAProvider()
    out = {}
    for name, (query, grams) in SOURCES.items():
        try:
            hits = provider.search(query, limit=10, data_types=("Foundation", "SR Legacy"))
        except Exception as e:  # noqa: BLE001
            print(f"err  {name!r}: {e}")
            continue
        r = _pick(query, hits)
        if not r:
            print(f"MISS {name!r} ({query!r})")
            continue
        f = grams / 100.0
        out[name] = {
            "serving_grams": grams,
            "fiber": round((r.fiber or 0) * f, 2),
            "sugar_g": round((r.sugar_g or 0) * f, 2),
            "iron_mg": round((r.iron_mg or 0) * f, 3),
            "calcium_mg": round((r.calcium_mg or 0) * f, 1),
            "potassium_mg": round((r.potassium_mg or 0) * f, 1),
            "vitamin_c_mg": round((r.vitamin_c_mg or 0) * f, 1),
            "vitamin_d_ug": round((r.vitamin_d_ug or 0) * f, 2),
        }
        print(f"ok   {name:24} <- {r.name}")
    dest = Path(__file__).resolve().parents[1] / "app" / "seed" / "legacy_micros.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {len(out)} enrichments to {dest}")


if __name__ == "__main__":
    main()
