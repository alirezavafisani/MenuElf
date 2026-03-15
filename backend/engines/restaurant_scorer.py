"""Restaurant scoring engine.

Pure Python, no LLM calls.  Builds restaurant taste signatures from menu
data and scores them against user profiles.
"""

from __future__ import annotations

import time
from typing import Any

# ===================================================================
# Keyword dictionaries (shared with preference_rules but self-contained
# here so the scorer has zero cross-engine dependencies)
# ===================================================================

_SPICY_KW = frozenset({
    "spicy", "hot", "chili", "chilli", "jalapeño", "jalapeno", "habanero",
    "sriracha", "szechuan", "sichuan", "buffalo", "cayenne", "chipotle",
    "ghost pepper", "extra hot", "fiery", "inferno", "fire", "tabasco",
    "gochujang", "sambal", "wasabi", "horseradish",
})

_SWEET_KW = frozenset({
    "sweet", "honey", "caramel", "maple", "sugar", "chocolate", "dessert",
    "cake", "pie", "brownie", "cookie", "ice cream", "gelato", "pastry",
    "mousse", "crème brûlée", "tiramisu", "cheesecake",
})

_CUISINE_KW: dict[str, str] = {
    "thai": "thai", "pad thai": "thai", "tom yum": "thai", "green curry": "thai",
    "massaman": "thai", "panang": "thai",
    "italian": "italian", "pasta": "italian", "pizza": "italian", "risotto": "italian",
    "lasagna": "italian", "gnocchi": "italian", "ravioli": "italian",
    "japanese": "japanese", "sushi": "japanese", "ramen": "japanese",
    "tempura": "japanese", "teriyaki": "japanese", "udon": "japanese",
    "sashimi": "japanese", "miso": "japanese",
    "chinese": "chinese", "szechuan": "chinese", "sichuan": "chinese",
    "dim sum": "chinese", "kung pao": "chinese", "chow mein": "chinese",
    "wonton": "chinese", "fried rice": "chinese",
    "indian": "indian", "tikka": "indian", "masala": "indian",
    "biryani": "indian", "curry": "indian", "naan": "indian",
    "tandoori": "indian", "vindaloo": "indian", "paneer": "indian",
    "korean": "korean", "bibimbap": "korean", "kimchi": "korean",
    "bulgogi": "korean", "japchae": "korean",
    "mexican": "mexican", "taco": "mexican", "burrito": "mexican",
    "enchilada": "mexican", "quesadilla": "mexican", "guacamole": "mexican",
    "nacho": "mexican", "salsa": "mexican", "fajita": "mexican",
    "mediterranean": "mediterranean", "hummus": "mediterranean",
    "falafel": "mediterranean", "pita": "mediterranean",
    "american": "american", "burger": "american", "bbq": "american",
    "brisket": "american", "wings": "american", "hot dog": "american",
    "french": "french", "croissant": "french", "thermidor": "french",
    "béarnaise": "french", "crêpe": "french", "escargot": "french",
    "soufflé": "french",
    "vietnamese": "vietnamese", "pho": "vietnamese", "banh mi": "vietnamese",
    "spring roll": "vietnamese",
    "middle_eastern": "middle_eastern", "shawarma": "middle_eastern",
    "kebab": "middle_eastern", "hummus": "middle_eastern",
    "greek": "mediterranean", "gyro": "mediterranean",
}

_PROTEIN_KW: dict[str, str] = {
    "beef": "beef", "steak": "beef", "brisket": "beef", "wagyu": "beef",
    "rib eye": "beef", "ribeye": "beef", "sirloin": "beef", "filet": "beef",
    "prime rib": "beef", "short rib": "beef",
    "chicken": "chicken", "poultry": "chicken", "wing": "chicken",
    "pork": "pork", "bacon": "pork", "ham": "pork", "pulled pork": "pork",
    "ribs": "pork", "sausage": "pork", "chorizo": "pork",
    "fish": "fish", "salmon": "fish", "tuna": "fish", "cod": "fish",
    "lobster": "fish", "shrimp": "fish", "prawn": "fish", "crab": "fish",
    "scallop": "fish", "seafood": "fish", "mussels": "fish", "calamari": "fish",
    "halibut": "fish", "trout": "fish", "oyster": "fish",
    "vegetarian": "vegetarian", "veggie": "vegetarian", "tofu": "vegetarian",
    "mushroom": "vegetarian",
    "vegan": "vegan", "plant-based": "vegan", "plant based": "vegan",
}

_TEXTURE_KW: dict[str, str] = {
    "crispy": "crispy", "fried": "crispy", "deep fried": "crispy",
    "crunchy": "crunchy", "tempura": "crispy", "crusted": "crispy",
    "creamy": "creamy", "cream": "creamy", "alfredo": "creamy",
    "risotto": "creamy", "chowder": "creamy", "bisque": "creamy",
    "soup": "soupy", "broth": "soupy", "stew": "soupy", "pho": "soupy",
    "ramen": "soupy",
    "chewy": "chewy", "gummy": "chewy", "mochi": "chewy",
}

_ADVENTUROUS_KW = frozenset({
    "truffle", "wagyu", "tartare", "bone marrow", "uni", "octopus",
    "foie gras", "escargot", "duck confit", "ceviche", "ahi",
    "carpaccio", "osso buco", "sous vide", "kimchi", "miso",
    "yuzu", "edamame", "tempeh", "jackfruit", "dragon fruit",
    "lychee", "passion fruit", "gochujang", "harissa",
})


def _text_of(item: dict) -> str:
    """Combine all searchable text from a menu item."""
    parts = [
        item.get("name", ""),
        item.get("description", ""),
        item.get("category", ""),
    ]
    for tag in item.get("dietary_info", []):
        parts.append(str(tag))
    return " ".join(parts).lower()


def _parse_price(item: dict) -> float | None:
    raw = item.get("price")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if raw > 0 else None
    try:
        s = str(raw).replace("$", "").replace(",", "").strip()
        if "-" in s:
            s = s.split("-")[0].strip()
        v = float(s)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def _count_keyword_hits(text: str, keywords) -> int:
    count = 0
    for kw in keywords:
        if kw in text:
            count += 1
    return count


def _detect_map(text: str, kw_map: dict[str, str]) -> dict[str, int]:
    """Return {category: hit_count} for a keyword→category map."""
    hits: dict[str, int] = {}
    for kw, cat in kw_map.items():
        if kw in text:
            hits[cat] = hits.get(cat, 0) + 1
    return hits


# ===================================================================
# Part A – build_restaurant_signature
# ===================================================================

def build_restaurant_signature(menu_items: list[dict]) -> dict:
    """Build a taste-profile-shaped signature for a restaurant's menu."""
    if not menu_items:
        return _default_signature()

    n = len(menu_items)
    spicy_count = 0
    sweet_count = 0
    adventurous_count = 0
    prices: list[float] = []
    cuisine_hits: dict[str, int] = {}
    protein_hits: dict[str, int] = {}
    texture_hits: dict[str, int] = {}

    for item in menu_items:
        text = _text_of(item)

        if _count_keyword_hits(text, _SPICY_KW):
            spicy_count += 1
        if _count_keyword_hits(text, _SWEET_KW):
            sweet_count += 1
        if _count_keyword_hits(text, _ADVENTUROUS_KW):
            adventurous_count += 1

        p = _parse_price(item)
        if p is not None:
            prices.append(p)

        for cat, cnt in _detect_map(text, _CUISINE_KW).items():
            cuisine_hits[cat] = cuisine_hits.get(cat, 0) + cnt
        for cat, cnt in _detect_map(text, _PROTEIN_KW).items():
            protein_hits[cat] = protein_hits.get(cat, 0) + cnt
        for cat, cnt in _detect_map(text, _TEXTURE_KW).items():
            texture_hits[cat] = texture_hits.get(cat, 0) + cnt

    # --- spice / sweet / adventurous ratios ---
    spice_ratio = min(spicy_count / n, 1.0)
    sweet_ratio = min(sweet_count / n, 1.0)
    adventurous_ratio = min(adventurous_count / n, 1.0)

    # --- price comfort ---
    if prices:
        avg_price = sum(prices) / len(prices)
        if avg_price < 12:
            price_comfort = max(0.0, avg_price / 12 * 0.5)
        elif avg_price <= 25:
            price_comfort = 0.5 + (avg_price - 12) / (25 - 12) * 0.5
        else:
            price_comfort = min(1.0, 0.5 + (avg_price - 12) / (50 - 12) * 0.5)
    else:
        price_comfort = 0.5

    # --- meal size (price proxy) ---
    meal_size = price_comfort  # same proxy

    # --- normalize hit dicts to 0..1 ratios ---
    def _normalize_hits(hits: dict[str, int]) -> dict[str, float]:
        if not hits:
            return {}
        total = sum(hits.values())
        if total == 0:
            return {}
        return {k: min(v / total * 2.0, 1.0) for k, v in hits.items()}
        # *2.0 so a dominant cuisine gets close to 1.0

    cuisine_prefs = _normalize_hits(cuisine_hits)
    protein_prefs = _normalize_hits(protein_hits)
    texture_prefs = _normalize_hits(texture_hits)

    # Check dietary coverage
    all_tags: set[str] = set()
    for item in menu_items:
        for tag in item.get("dietary_info", []):
            all_tags.add(str(tag).lower())

    return {
        "spice_tolerance": spice_ratio,
        "sweetness_preference": sweet_ratio,
        "adventurousness": adventurous_ratio,
        "price_comfort": price_comfort,
        "meal_size_preference": meal_size,
        "cuisine_preferences": cuisine_prefs,
        "protein_preference": protein_prefs,
        "texture_preferences": texture_prefs,
        "dietary_tags": list(all_tags),
    }


def _default_signature() -> dict:
    return {
        "spice_tolerance": 0.5,
        "sweetness_preference": 0.5,
        "adventurousness": 0.5,
        "price_comfort": 0.5,
        "meal_size_preference": 0.5,
        "cuisine_preferences": {},
        "protein_preference": {},
        "texture_preferences": {},
        "dietary_tags": [],
    }


# ===================================================================
# Part A – score_restaurant_for_user
# ===================================================================

def _dim_similarity(user_val: float, rest_val: float) -> float:
    """1.0 for perfect match, 0.0 for maximum difference."""
    return 1.0 - abs(user_val - rest_val)


def _dict_similarity(user_dict: dict, rest_dict: dict) -> float:
    """Dot-product-style similarity between two {key: float} dicts.

    For each key in the restaurant dict, multiply by the user pref and
    average over all restaurant keys.  If restaurant dict is empty, return 0.5.
    """
    if not rest_dict:
        return 0.5
    total = 0.0
    count = 0
    for key, rest_val in rest_dict.items():
        user_val = user_dict.get(key, 0.5)
        total += user_val * rest_val
        count += 1
    if count == 0:
        return 0.5
    # Normalize: max possible per pair is 1.0*1.0 = 1.0
    return total / count


def score_restaurant_for_user(
    user_profile: dict,
    restaurant_signature: dict,
) -> float:
    """Return a match score 0..100."""
    # Numeric dimension similarities
    spice_sim = _dim_similarity(
        user_profile.get("spice_tolerance", 0.5),
        restaurant_signature.get("spice_tolerance", 0.5),
    )
    price_sim = _dim_similarity(
        user_profile.get("price_comfort", 0.5),
        restaurant_signature.get("price_comfort", 0.5),
    )
    adventure_sim = _dim_similarity(
        user_profile.get("adventurousness", 0.5),
        restaurant_signature.get("adventurousness", 0.5),
    )
    sweet_sim = _dim_similarity(
        user_profile.get("sweetness_preference", 0.5),
        restaurant_signature.get("sweetness_preference", 0.5),
    )
    size_sim = _dim_similarity(
        user_profile.get("meal_size_preference", 0.5),
        restaurant_signature.get("meal_size_preference", 0.5),
    )

    # Dict similarities
    cuisine_sim = _dict_similarity(
        user_profile.get("cuisine_preferences", {}),
        restaurant_signature.get("cuisine_preferences", {}),
    )
    protein_sim = _dict_similarity(
        user_profile.get("protein_preference", {}),
        restaurant_signature.get("protein_preference", {}),
    )
    texture_sim = _dict_similarity(
        user_profile.get("texture_preferences", {}),
        restaurant_signature.get("texture_preferences", {}),
    )

    # Weighted average
    raw = (
        cuisine_sim * 0.25
        + protein_sim * 0.15
        + spice_sim * 0.15
        + price_sim * 0.15
        + texture_sim * 0.10
        + adventure_sim * 0.10
        + sweet_sim * 0.05
        + size_sim * 0.05
    )

    # Dietary penalty
    user_restrictions = user_profile.get("dietary_restrictions", [])
    if isinstance(user_restrictions, list) and user_restrictions:
        rest_tags = set(restaurant_signature.get("dietary_tags", []))
        matched = any(r.lower() in rest_tags for r in user_restrictions)
        if not matched:
            raw *= 0.7

    score = max(0, min(100, round(raw * 100)))
    return score


# ===================================================================
# Part A – find_top_dish_for_user
# ===================================================================

_REASON_TEMPLATES = {
    "spice": "spicy food",
    "cuisine": "{cuisine} cuisine",
    "protein": "{protein} dishes",
    "price": "your budget",
    "texture": "{texture} textures",
    "adventure": "adventurous flavors",
    "dietary": "your dietary preferences",
}


def _score_single_item(user_profile: dict, item: dict) -> tuple[float, list[tuple[str, float, str]]]:
    """Score a single menu item.  Returns (score, [(reason_key, score, detail)])."""
    text = _text_of(item)
    signals: list[tuple[str, float, str]] = []

    # Spice match
    user_spice = user_profile.get("spice_tolerance", 0.5)
    is_spicy = bool(_count_keyword_hits(text, _SPICY_KW))
    if is_spicy and user_spice > 0.6:
        signals.append(("spice", user_spice, "spicy"))
    elif not is_spicy and user_spice < 0.4:
        signals.append(("spice", 1.0 - user_spice, "mild"))

    # Cuisine match
    detected_cuisines = _detect_map(text, _CUISINE_KW)
    user_cuisines = user_profile.get("cuisine_preferences", {})
    for c in detected_cuisines:
        pref = user_cuisines.get(c, 0.5)
        if pref > 0.5:
            signals.append(("cuisine", pref, c))

    # Protein match
    detected_proteins = _detect_map(text, _PROTEIN_KW)
    user_proteins = user_profile.get("protein_preference", {})
    for p in detected_proteins:
        pref = user_proteins.get(p, 0.5)
        if pref > 0.5:
            signals.append(("protein", pref, p))

    # Price match
    price = _parse_price(item)
    user_price = user_profile.get("price_comfort", 0.5)
    if price is not None:
        if price < 15 and user_price < 0.4:
            signals.append(("price", 0.7, "budget"))
        elif price > 30 and user_price > 0.7:
            signals.append(("price", 0.7, "premium"))
        elif 15 <= price <= 30:
            signals.append(("price", 0.5, "mid-range"))

    # Texture match
    detected_textures = _detect_map(text, _TEXTURE_KW)
    user_textures = user_profile.get("texture_preferences", {})
    for t in detected_textures:
        pref = user_textures.get(t, 0.5)
        if pref > 0.5:
            signals.append(("texture", pref, t))

    # Dietary match
    user_restrictions = user_profile.get("dietary_restrictions", [])
    if isinstance(user_restrictions, list) and user_restrictions:
        item_tags = {str(t).lower() for t in item.get("dietary_info", [])}
        if any(r.lower() in item_tags for r in user_restrictions):
            signals.append(("dietary", 0.8, "compatible"))

    # Vegetarian boost if user prefers it
    veg_pref = user_proteins.get("vegetarian", 0.5)
    item_tags_set = {str(t).lower() for t in item.get("dietary_info", [])}
    if veg_pref > 0.7 and "vegetarian" in item_tags_set:
        signals.append(("protein", veg_pref, "vegetarian"))

    total = sum(s[1] for s in signals)
    return total, signals


def _build_reason(signals: list[tuple[str, float, str]]) -> str:
    """Build a human-readable match_reason from the top 2 signals."""
    if not signals:
        return "A solid menu pick"

    # Sort by strength descending, take top 2 unique reason keys
    signals.sort(key=lambda s: s[1], reverse=True)
    seen_keys: set[str] = set()
    top: list[tuple[str, float, str]] = []
    for key, score, detail in signals:
        if key not in seen_keys:
            seen_keys.add(key)
            top.append((key, score, detail))
        if len(top) == 2:
            break

    parts: list[str] = []
    for key, _, detail in top:
        if key == "spice":
            parts.append(f"{detail} food")
        elif key == "cuisine":
            parts.append(f"{detail.replace('_', ' ')} cuisine")
        elif key == "protein":
            parts.append(f"{detail} dishes")
        elif key == "price":
            parts.append(f"your {detail} preference")
        elif key == "texture":
            parts.append(f"{detail} textures")
        elif key == "adventure":
            parts.append("adventurous flavors")
        elif key == "dietary":
            parts.append("your dietary needs")
        else:
            parts.append(detail)

    if len(parts) == 2:
        return f"Matches your love for {parts[0]} and {parts[1]}"
    elif len(parts) == 1:
        return f"Great fit for your {parts[0]} preference"
    return "A solid menu pick"


def find_top_dish_for_user(
    user_profile: dict,
    menu_items: list[dict],
    restaurant_signature: dict | None = None,
) -> dict | None:
    """Return the single best-matching dish for the user."""
    if not menu_items:
        return None

    best_score = -1.0
    best_item = None
    best_signals: list = []

    for item in menu_items:
        score, signals = _score_single_item(user_profile, item)
        if score > best_score:
            best_score = score
            best_item = item
            best_signals = signals

    if best_item is None:
        return None

    return {
        "dish_name": best_item.get("name", ""),
        "price": _parse_price(best_item),
        "match_reason": _build_reason(best_signals),
    }


def find_top_n_dishes_for_user(
    user_profile: dict,
    menu_items: list[dict],
    n: int = 3,
) -> list[dict]:
    """Return the top N best-matching dishes."""
    if not menu_items:
        return []

    scored: list[tuple[float, dict, list]] = []
    for item in menu_items:
        score, signals = _score_single_item(user_profile, item)
        scored.append((score, item, signals))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, item, signals in scored[:n]:
        results.append({
            "dish_name": item.get("name", ""),
            "price": _parse_price(item),
            "match_reason": _build_reason(signals),
        })
    return results


def find_avoid_dishes(
    user_profile: dict,
    menu_items: list[dict],
) -> list[dict]:
    """Find dishes that conflict with user's dietary restrictions or strong dislikes."""
    restrictions = user_profile.get("dietary_restrictions", [])
    if not isinstance(restrictions, list):
        restrictions = []

    proteins = user_profile.get("protein_preference", {})
    disliked_proteins: set[str] = set()
    for prot, val in proteins.items():
        if isinstance(val, (int, float)) and val < 0.2:
            disliked_proteins.add(prot)

    avoid = []
    for item in menu_items:
        text = _text_of(item)
        reasons: list[str] = []

        # Check protein dislikes
        detected = _detect_map(text, _PROTEIN_KW)
        for prot in detected:
            if prot in disliked_proteins:
                reasons.append(f"contains {prot}")

        if reasons:
            avoid.append({
                "dish_name": item.get("name", ""),
                "price": _parse_price(item),
                "reason": "; ".join(reasons),
            })

    return avoid[:10]  # limit


# ===================================================================
# Signature cache (1-hour TTL)
# ===================================================================

_signature_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1 hour


def get_cached_signature(slug: str, menu_items: list[dict]) -> dict:
    """Return a cached signature or compute and cache a new one."""
    now = time.time()
    cached = _signature_cache.get(slug)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]
    sig = build_restaurant_signature(menu_items)
    _signature_cache[slug] = (now, sig)
    return sig


def clear_signature_cache():
    """For testing."""
    _signature_cache.clear()
