"""Convert raw taste profile data into natural language.

Used by the smart chat system to build personalized system prompts
without exposing raw numbers or technical jargon to the user.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_HIGH = 0.7
_LOW = 0.3


# ---------------------------------------------------------------------------
# narrate_profile
# ---------------------------------------------------------------------------

def narrate_profile(profile: dict) -> str:
    """Convert a taste profile dict into a natural-language paragraph.

    Only mentions dimensions that are notably high (> 0.7) or low (< 0.3).
    Neutral values (0.4–0.6) are omitted.
    """
    parts: list[str] = []

    # --- Scalar dimensions ---
    spice = profile.get("spice_tolerance", 0.5)
    if spice > _HIGH:
        parts.append("loves spicy food")
    elif spice < _LOW:
        parts.append("prefers mild flavors")

    sweet = profile.get("sweetness_preference", 0.5)
    if sweet > _HIGH:
        parts.append("has a sweet tooth")
    elif sweet < _LOW:
        parts.append("not big on sweets")

    adventure = profile.get("adventurousness", 0.5)
    if adventure > _HIGH:
        parts.append("adventurous eater who loves trying new things")
    elif adventure < _LOW:
        parts.append("prefers familiar comfort food")

    price = profile.get("price_comfort", 0.5)
    if price > _HIGH:
        parts.append("happy to splurge on premium dishes")
    elif price < _LOW:
        parts.append("budget-conscious, prefers affordable options")

    size = profile.get("meal_size_preference", 0.5)
    if size > _HIGH:
        parts.append("goes for hearty, generous portions")
    elif size < _LOW:
        parts.append("prefers lighter meals")

    # --- Cuisine preferences ---
    cuisines = profile.get("cuisine_preferences", {})
    if isinstance(cuisines, dict):
        loved = [c.replace("_", " ").title() for c, v in cuisines.items()
                 if isinstance(v, (int, float)) and v > _HIGH]
        if loved:
            if len(loved) == 1:
                parts.append(f"big fan of {loved[0]} cuisine")
            else:
                parts.append(f"big fan of {', '.join(loved[:-1])} and {loved[-1]} cuisine")

    # --- Protein preferences ---
    proteins = profile.get("protein_preference", {})
    if isinstance(proteins, dict):
        liked = [p for p, v in proteins.items()
                 if isinstance(v, (int, float)) and v > _HIGH]
        avoided = [p for p, v in proteins.items()
                   if isinstance(v, (int, float)) and v < _LOW]
        if liked:
            # Special wording for vegetarian/vegan
            veg_terms = {"vegetarian", "vegan"}
            veg_liked = [p for p in liked if p in veg_terms]
            meat_liked = [p for p in liked if p not in veg_terms]
            if veg_liked and not meat_liked:
                parts.append(f"leans {' and '.join(veg_liked)}")
            elif meat_liked and not veg_liked:
                parts.append(f"prefers {', '.join(meat_liked)}")
            else:
                parts.append(f"prefers {', '.join(meat_liked)} and leans {', '.join(veg_liked)}")
        if avoided:
            parts.append(f"rarely chooses {', '.join(avoided)}")

    # --- Texture preferences ---
    textures = profile.get("texture_preferences", {})
    if isinstance(textures, dict):
        fav_textures = [t for t, v in textures.items()
                        if isinstance(v, (int, float)) and v > _HIGH]
        if fav_textures:
            parts.append(f"enjoys {', '.join(fav_textures)} textures")

    # --- Dietary restrictions ---
    restrictions = profile.get("dietary_restrictions", [])
    if isinstance(restrictions, list) and restrictions:
        formatted = [r.replace("_", " ") for r in restrictions]
        if len(formatted) == 1:
            parts.append(f"follows a {formatted[0]} diet")
        else:
            parts.append(f"follows a {', '.join(formatted[:-1])} and {formatted[-1]} diet")

    if not parts:
        return "No strong preferences noted yet."

    sentence = "This person " + ", ".join(parts) + "."
    return sentence


# ---------------------------------------------------------------------------
# format_recommendations
# ---------------------------------------------------------------------------

def format_recommendations(top_dishes: list[dict], profile: dict) -> str:
    """Format top dish recommendations as a numbered list."""
    if not top_dishes:
        return "No specific recommendations available."

    lines: list[str] = []
    for i, dish in enumerate(top_dishes, 1):
        name = dish.get("dish_name", "Unknown")
        price = dish.get("price")
        reason = dish.get("match_reason", "")

        price_str = f" (${price:.0f})" if price is not None else ""
        reason_str = f" — {reason}" if reason else ""
        lines.append(f"{i}. {name}{price_str}{reason_str}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# format_avoid_list
# ---------------------------------------------------------------------------

def format_avoid_list(avoid_dishes: list[dict]) -> str:
    """Format avoid dishes with reasons."""
    if not avoid_dishes:
        return ""

    lines: list[str] = []
    for dish in avoid_dishes:
        name = dish.get("dish_name", "Unknown")
        reason = dish.get("reason", "")
        if reason:
            lines.append(f"- {name} — {reason}")
        else:
            lines.append(f"- {name}")

    return "\n".join(lines)
