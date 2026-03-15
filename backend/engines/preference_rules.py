"""Rule-based preference processor.

Pure Python, no external dependencies, deterministic.
Applies small nudges to a user's taste profile based on interaction signals.
"""

from __future__ import annotations


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _nudge(profile: dict, key: str, delta: float) -> None:
    """Nudge a top-level float field by *delta*, clamping to [0, 1]."""
    current = profile.get(key, 0.5)
    if not isinstance(current, (int, float)):
        current = 0.5
    profile[key] = _clamp(current + delta)


def _nudge_nested(profile: dict, parent: str, child: str, delta: float) -> None:
    """Nudge a nested dict field (e.g. cuisine_preferences.thai)."""
    container = profile.get(parent)
    if not isinstance(container, dict):
        container = {}
        profile[parent] = container
    current = container.get(child, 0.5)
    if not isinstance(current, (int, float)):
        current = 0.5
    container[child] = _clamp(current + delta)


def _nudge_dimension(profile: dict, dimension: str, delta: float) -> None:
    """Nudge either a top-level or dotted nested dimension."""
    if "." in dimension:
        parent, child = dimension.split(".", 1)
        _nudge_nested(profile, parent, child, delta)
    else:
        _nudge(profile, dimension, delta)


# ---------------------------------------------------------------------------
# Cuisine / protein detection helpers
# ---------------------------------------------------------------------------

_CUISINE_KEYWORDS: dict[str, str] = {
    "thai": "thai", "pad thai": "thai", "tom yum": "thai", "green curry": "thai",
    "italian": "italian", "pasta": "italian", "pizza": "italian", "risotto": "italian",
    "japanese": "japanese", "sushi": "japanese", "ramen": "japanese", "tempura": "japanese",
    "chinese": "chinese", "szechuan": "chinese", "dim sum": "chinese", "kung pao": "chinese",
    "indian": "indian", "tikka": "indian", "masala": "indian", "biryani": "indian", "curry": "indian",
    "korean": "korean", "bibimbap": "korean", "kimchi": "korean",
    "mexican": "mexican", "taco": "mexican", "burrito": "mexican", "enchilada": "mexican",
    "mediterranean": "mediterranean", "hummus": "mediterranean", "falafel": "mediterranean",
    "american": "american", "burger": "american", "bbq": "american", "brisket": "american",
    "french": "french", "croissant": "french", "thermidor": "french",
    "vietnamese": "vietnamese", "pho": "vietnamese", "banh mi": "vietnamese",
    "middle_eastern": "middle_eastern", "shawarma": "middle_eastern", "kebab": "middle_eastern",
}

_PROTEIN_KEYWORDS: dict[str, str] = {
    "beef": "beef", "steak": "beef", "brisket": "beef", "wagyu": "beef",
    "chicken": "chicken", "poultry": "chicken",
    "pork": "pork", "bacon": "pork", "ham": "pork",
    "fish": "fish", "salmon": "fish", "tuna": "fish", "cod": "fish", "lobster": "fish", "shrimp": "fish",
    "vegetarian": "vegetarian", "veggie": "vegetarian",
    "vegan": "vegan",
}

_SPICY_KEYWORDS = {"spicy", "hot", "szechuan", "chili", "jalapeño", "habanero", "sriracha", "fiery", "extra hot"}


def _detect_cuisines(text: str) -> list[str]:
    text_lower = text.lower()
    found: set[str] = set()
    for kw, cuisine in _CUISINE_KEYWORDS.items():
        if kw in text_lower:
            found.add(cuisine)
    return list(found)


def _detect_proteins(text: str) -> list[str]:
    text_lower = text.lower()
    found: set[str] = set()
    for kw, protein in _PROTEIN_KEYWORDS.items():
        if kw in text_lower:
            found.add(protein)
    return list(found)


def _is_spicy(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in _SPICY_KEYWORDS)


def _price_to_comfort_direction(price: float) -> float:
    """Return a signed delta for price_comfort based on dish price.

    Cheap dishes (<15) nudge down, expensive (>30) nudge up, mid stays flat.
    """
    if price < 15:
        return -0.03
    elif price > 30:
        return +0.03
    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_interaction(profile: dict, interaction_type: str, payload: dict) -> dict:
    """Apply rule-based preference signals from one interaction.

    Returns the *mutated* profile dict (same reference, updated in place).
    All float values are clamped to [0.0, 1.0].
    """
    if not isinstance(payload, dict):
        payload = {}

    # ── dish_save ──
    if interaction_type == "dish_save":
        # Cuisine signal from dish metadata
        dish_text = " ".join(filter(None, [
            payload.get("dish_name", ""),
            payload.get("category", ""),
            payload.get("restaurant_slug", ""),
        ]))
        for cuisine in _detect_cuisines(dish_text):
            _nudge_nested(profile, "cuisine_preferences", cuisine, +0.05)
        for protein in _detect_proteins(dish_text):
            _nudge_nested(profile, "protein_preference", protein, +0.05)
        if _is_spicy(dish_text):
            _nudge(profile, "spice_tolerance", +0.05)
        # Dietary info from payload
        for tag in payload.get("dietary_info", []):
            tag_lower = str(tag).lower()
            if tag_lower in ("spicy", "hot"):
                _nudge(profile, "spice_tolerance", +0.03)
        # Price signal
        price = payload.get("price")
        if price is not None:
            try:
                price = float(price)
                delta = _price_to_comfort_direction(price)
                if delta != 0:
                    _nudge(profile, "price_comfort", delta)
            except (ValueError, TypeError):
                pass

    # ── dish_unsave ──
    elif interaction_type == "dish_unsave":
        dish_text = " ".join(filter(None, [
            payload.get("dish_name", ""),
            payload.get("category", ""),
            payload.get("restaurant_slug", ""),
        ]))
        for cuisine in _detect_cuisines(dish_text):
            _nudge_nested(profile, "cuisine_preferences", cuisine, -0.03)
        for protein in _detect_proteins(dish_text):
            _nudge_nested(profile, "protein_preference", protein, -0.03)
        if _is_spicy(dish_text):
            _nudge(profile, "spice_tolerance", -0.03)

    # ── filter_apply ──
    elif interaction_type == "filter_apply":
        filter_type = payload.get("filter_type", "")
        value = payload.get("value", "")
        value_str = str(value).lower()

        if filter_type == "price":
            if "under_15" in value_str or "under_10" in value_str or "budget" in value_str:
                _nudge(profile, "price_comfort", -0.03)
            elif "over_30" in value_str or "over_40" in value_str or "luxury" in value_str:
                _nudge(profile, "price_comfort", +0.03)

        elif filter_type == "dietary":
            if "vegetarian" in value_str:
                _nudge_nested(profile, "protein_preference", "vegetarian", +0.05)
            if "vegan" in value_str:
                _nudge_nested(profile, "protein_preference", "vegan", +0.05)
            if "halal" in value_str:
                restrictions = profile.get("dietary_restrictions", [])
                if not isinstance(restrictions, list):
                    restrictions = []
                    profile["dietary_restrictions"] = restrictions
                if "halal" not in restrictions:
                    restrictions.append("halal")
            if "kosher" in value_str:
                restrictions = profile.get("dietary_restrictions", [])
                if not isinstance(restrictions, list):
                    restrictions = []
                    profile["dietary_restrictions"] = restrictions
                if "kosher" not in restrictions:
                    restrictions.append("kosher")
            if "gluten_free" in value_str or "gluten-free" in value_str:
                restrictions = profile.get("dietary_restrictions", [])
                if not isinstance(restrictions, list):
                    restrictions = []
                    profile["dietary_restrictions"] = restrictions
                if "gluten_free" not in restrictions:
                    restrictions.append("gluten_free")

    # ── search_query ──
    elif interaction_type == "search_query":
        query = payload.get("query", "")
        if _is_spicy(query):
            _nudge(profile, "spice_tolerance", +0.02)
        # Also detect cuisine from search terms
        for cuisine in _detect_cuisines(query):
            _nudge_nested(profile, "cuisine_preferences", cuisine, +0.02)

    # ── restaurant_tap ──
    elif interaction_type == "restaurant_tap":
        slug = payload.get("restaurant_slug", "")
        for cuisine in _detect_cuisines(slug):
            _nudge_nested(profile, "cuisine_preferences", cuisine, +0.02)

    return profile
