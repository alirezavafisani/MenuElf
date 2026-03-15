"""Comprehensive tests for the restaurant scoring engine.

Run with:
    python -m pytest backend/tests/test_restaurant_scorer.py -v
"""

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engines.restaurant_scorer import (
    build_restaurant_signature,
    score_restaurant_for_user,
    find_top_dish_for_user,
    find_top_n_dishes_for_user,
    find_avoid_dishes,
    get_cached_signature,
    clear_signature_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_profile() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "spice_tolerance": 0.5,
        "sweetness_preference": 0.5,
        "adventurousness": 0.5,
        "price_comfort": 0.5,
        "meal_size_preference": 0.5,
        "protein_preference": {
            "beef": 0.5, "chicken": 0.5, "pork": 0.5,
            "fish": 0.5, "vegetarian": 0.5, "vegan": 0.3,
        },
        "cuisine_preferences": {
            "italian": 0.5, "mexican": 0.5, "japanese": 0.5,
            "chinese": 0.5, "indian": 0.5, "thai": 0.5,
            "korean": 0.5, "mediterranean": 0.5, "american": 0.5,
            "french": 0.5, "vietnamese": 0.5, "middle_eastern": 0.5,
        },
        "texture_preferences": {
            "crispy": 0.5, "creamy": 0.5, "crunchy": 0.5,
            "soupy": 0.5, "chewy": 0.5,
        },
        "dietary_restrictions": [],
        "onboarding_completed": True,
        "profile_version": 1,
    }


def _thai_menu() -> list[dict]:
    return [
        {"name": "Pad Thai", "description": "Classic Thai stir-fried noodles", "price": 16.0, "category": "Food", "dietary_info": [], "restaurant_slug": "thai-palace"},
        {"name": "Green Curry", "description": "Spicy Thai green curry with chicken", "price": 18.0, "category": "Food", "dietary_info": ["spicy"], "restaurant_slug": "thai-palace"},
        {"name": "Tom Yum Soup", "description": "Hot and sour Thai soup with shrimp", "price": 14.0, "category": "Food", "dietary_info": ["spicy"], "restaurant_slug": "thai-palace"},
        {"name": "Mango Sticky Rice", "description": "Sweet dessert with coconut cream", "price": 10.0, "category": "Dessert", "dietary_info": ["vegetarian"], "restaurant_slug": "thai-palace"},
        {"name": "Massaman Curry", "description": "Mild Thai curry with beef and peanuts", "price": 19.0, "category": "Food", "dietary_info": [], "restaurant_slug": "thai-palace"},
    ]


def _italian_menu() -> list[dict]:
    return [
        {"name": "Margherita Pizza", "description": "Classic Italian pizza with mozzarella", "price": 14.0, "category": "Pizza", "dietary_info": ["vegetarian"], "restaurant_slug": "italian-place"},
        {"name": "Fettuccine Alfredo", "description": "Creamy pasta with parmesan", "price": 18.0, "category": "Pasta", "dietary_info": ["vegetarian"], "restaurant_slug": "italian-place"},
        {"name": "Chicken Parmigiana", "description": "Breaded chicken with marinara", "price": 22.0, "category": "Food", "dietary_info": [], "restaurant_slug": "italian-place"},
        {"name": "Tiramisu", "description": "Classic Italian dessert with espresso and cream", "price": 12.0, "category": "Dessert", "dietary_info": ["vegetarian"], "restaurant_slug": "italian-place"},
        {"name": "Risotto ai Funghi", "description": "Creamy mushroom risotto", "price": 20.0, "category": "Food", "dietary_info": ["vegetarian"], "restaurant_slug": "italian-place"},
    ]


def _steak_menu() -> list[dict]:
    return [
        {"name": "Wagyu Ribeye", "description": "Premium wagyu beef steak", "price": 65.0, "category": "Food", "dietary_info": [], "restaurant_slug": "steak-house"},
        {"name": "Filet Mignon", "description": "Tender beef filet with truffle butter", "price": 55.0, "category": "Food", "dietary_info": [], "restaurant_slug": "steak-house"},
        {"name": "Bone Marrow Appetizer", "description": "Roasted bone marrow with herbs", "price": 18.0, "category": "Appetizer", "dietary_info": [], "restaurant_slug": "steak-house"},
        {"name": "Lobster Tail", "description": "Grilled lobster with butter", "price": 45.0, "category": "Food", "dietary_info": [], "restaurant_slug": "steak-house"},
        {"name": "Caesar Salad", "description": "Classic crispy romaine salad", "price": 14.0, "category": "Salad", "dietary_info": [], "restaurant_slug": "steak-house"},
    ]


@pytest.fixture(autouse=True)
def clear_cache():
    clear_signature_cache()
    yield
    clear_signature_cache()


# ===================================================================
# SIGNATURE TESTS (1-5)
# ===================================================================

# 1. Thai menu → high spice ratio, detects thai cuisine
def test_signature_thai_menu():
    sig = build_restaurant_signature(_thai_menu())
    assert sig["spice_tolerance"] > 0.0  # 2/5 items are spicy
    assert "thai" in sig["cuisine_preferences"]
    assert sig["cuisine_preferences"]["thai"] > 0


# 2. Italian menu → low spice, detects italian cuisine, creamy texture
def test_signature_italian_menu():
    sig = build_restaurant_signature(_italian_menu())
    assert sig["spice_tolerance"] == 0.0  # No spicy items
    assert "italian" in sig["cuisine_preferences"]
    assert "creamy" in sig["texture_preferences"]
    assert sig["sweetness_preference"] > 0.0  # tiramisu


# 3. Steak house → high price comfort, detects beef protein, adventurous items
def test_signature_steak_house():
    sig = build_restaurant_signature(_steak_menu())
    assert sig["price_comfort"] > 0.7  # Average price is very high
    assert "beef" in sig["protein_preference"]
    assert sig["adventurousness"] > 0.0  # truffle, wagyu, bone marrow


# 4. Empty menu → returns default signature (all 0.5)
def test_signature_empty_menu():
    sig = build_restaurant_signature([])
    assert sig["spice_tolerance"] == 0.5
    assert sig["sweetness_preference"] == 0.5
    assert sig["price_comfort"] == 0.5
    assert sig["cuisine_preferences"] == {}
    assert sig["protein_preference"] == {}


# 5. Signature includes dietary tags from menu items
def test_signature_dietary_tags():
    menu = [
        {"name": "Veggie Bowl", "description": "Healthy vegan bowl", "price": 14.0, "dietary_info": ["vegan", "gluten-free"]},
        {"name": "Tofu Stir Fry", "description": "Crispy tofu", "price": 13.0, "dietary_info": ["vegetarian"]},
    ]
    sig = build_restaurant_signature(menu)
    assert "vegan" in sig["dietary_tags"]
    assert "gluten-free" in sig["dietary_tags"]
    assert "vegetarian" in sig["dietary_tags"]


# ===================================================================
# SCORING TESTS (6-10)
# ===================================================================

# 6. Spicy user + Thai restaurant → high score
def test_score_spicy_user_thai_restaurant():
    profile = _base_profile()
    profile["spice_tolerance"] = 0.9
    profile["cuisine_preferences"]["thai"] = 0.9

    sig = build_restaurant_signature(_thai_menu())
    score = score_restaurant_for_user(profile, sig)
    assert score >= 50  # Should be a good match


# 7. Identical profile and signature → near-perfect score
def test_score_perfect_match():
    sig = build_restaurant_signature(_italian_menu())
    # Build a user profile that mirrors the signature
    profile = _base_profile()
    profile["spice_tolerance"] = sig["spice_tolerance"]
    profile["sweetness_preference"] = sig["sweetness_preference"]
    profile["adventurousness"] = sig["adventurousness"]
    profile["price_comfort"] = sig["price_comfort"]
    profile["meal_size_preference"] = sig["meal_size_preference"]
    for k, v in sig["cuisine_preferences"].items():
        profile["cuisine_preferences"][k] = v
    for k, v in sig["protein_preference"].items():
        profile["protein_preference"][k] = v
    for k, v in sig["texture_preferences"].items():
        profile["texture_preferences"][k] = v

    score = score_restaurant_for_user(profile, sig)
    assert score >= 50  # High similarity


# 8. Dietary restriction mismatch → penalty applied (score * 0.7)
def test_score_dietary_penalty():
    profile = _base_profile()
    profile["dietary_restrictions"] = ["halal"]
    sig = build_restaurant_signature(_steak_menu())  # No halal tag
    score_with_restriction = score_restaurant_for_user(profile, sig)

    profile_no_restriction = _base_profile()
    score_without = score_restaurant_for_user(profile_no_restriction, sig)

    assert score_with_restriction < score_without


# 9. Score is always between 0 and 100
def test_score_bounds():
    profile = _base_profile()
    for menu in [_thai_menu(), _italian_menu(), _steak_menu(), []]:
        sig = build_restaurant_signature(menu)
        score = score_restaurant_for_user(profile, sig)
        assert 0 <= score <= 100


# 10. Budget user vs expensive restaurant → lower score than mid-range user
def test_score_price_mismatch():
    budget_profile = _base_profile()
    budget_profile["price_comfort"] = 0.1  # Very budget-conscious

    mid_profile = _base_profile()
    mid_profile["price_comfort"] = 0.5

    sig = build_restaurant_signature(_steak_menu())  # Expensive

    budget_score = score_restaurant_for_user(budget_profile, sig)
    mid_score = score_restaurant_for_user(mid_profile, sig)
    assert budget_score < mid_score


# ===================================================================
# TOP DISH TESTS (11-13)
# ===================================================================

# 11. Spicy-loving user → top dish is a spicy item
def test_top_dish_spicy_user():
    profile = _base_profile()
    profile["spice_tolerance"] = 0.9
    profile["cuisine_preferences"]["thai"] = 0.9

    result = find_top_dish_for_user(profile, _thai_menu())
    assert result is not None
    assert "dish_name" in result
    assert "match_reason" in result
    # The top dish should be one of the spicy items
    assert result["dish_name"] in ["Green Curry", "Tom Yum Soup"]


# 12. Top N dishes returns correct count
def test_top_n_dishes():
    profile = _base_profile()
    profile["cuisine_preferences"]["italian"] = 0.9

    results = find_top_n_dishes_for_user(profile, _italian_menu(), n=3)
    assert len(results) == 3
    for dish in results:
        assert "dish_name" in dish
        assert "price" in dish
        assert "match_reason" in dish


# 13. Avoid dishes for user who dislikes pork
def test_avoid_dishes_pork():
    profile = _base_profile()
    profile["protein_preference"]["pork"] = 0.1  # Strongly dislikes pork

    menu = [
        {"name": "Pulled Pork Sandwich", "description": "Slow-cooked pulled pork", "price": 16.0, "dietary_info": []},
        {"name": "Grilled Chicken", "description": "Simple grilled chicken breast", "price": 18.0, "dietary_info": []},
        {"name": "Bacon Burger", "description": "Burger topped with crispy bacon", "price": 20.0, "dietary_info": []},
    ]
    avoided = find_avoid_dishes(profile, menu)
    avoided_names = [d["dish_name"] for d in avoided]
    # Both pork items should be flagged
    assert "Pulled Pork Sandwich" in avoided_names
    assert "Bacon Burger" in avoided_names
    # Chicken should not be avoided
    assert "Grilled Chicken" not in avoided_names


# ===================================================================
# ENDPOINT / CACHE / INTEGRATION TESTS (14-16)
# ===================================================================

# 14. Signature caching works — same slug returns cached result
def test_signature_caching():
    menu = _thai_menu()
    sig1 = get_cached_signature("test-slug", menu)
    sig2 = get_cached_signature("test-slug", menu)
    assert sig1 is sig2  # Same object from cache


# 15. Empty menu → find_top_dish returns None
def test_top_dish_empty_menu():
    profile = _base_profile()
    result = find_top_dish_for_user(profile, [])
    assert result is None


# 16. Full integration: onboard user, build signature, score, find top dish
def test_full_scoring_integration():
    """End-to-end: build a user profile from onboarding, score against a restaurant, get recommendations."""
    from routers.user_intelligence import _compute_taste_profile
    from models.user_intelligence import OnboardingAnswer

    # Create spicy/adventurous user via onboarding (all A answers)
    answers = [OnboardingAnswer(question_index=i, chosen_option="a") for i in range(1, 6)]
    computed = _compute_taste_profile(answers)

    profile = _base_profile()
    for key in ("spice_tolerance", "sweetness_preference", "adventurousness",
                "price_comfort", "meal_size_preference"):
        profile[key] = computed.get(key, profile[key])
    for key in ("cuisine_preferences", "protein_preference", "texture_preferences"):
        if key in computed and isinstance(computed[key], dict):
            profile[key] = {**profile[key], **computed[key]}

    # Score against Thai restaurant (should be a good match for spicy user)
    thai_sig = build_restaurant_signature(_thai_menu())
    thai_score = score_restaurant_for_user(profile, thai_sig)

    # Score against Italian restaurant (lower spice match)
    italian_sig = build_restaurant_signature(_italian_menu())
    italian_score = score_restaurant_for_user(profile, italian_sig)

    # Spicy user should prefer Thai over Italian
    assert thai_score > italian_score

    # Top dish for Thai should be a spicy item
    top = find_top_dish_for_user(profile, _thai_menu(), thai_sig)
    assert top is not None
    assert top["dish_name"] in ["Green Curry", "Tom Yum Soup"]

    # Top 3 dishes should return 3 results
    top_3 = find_top_n_dishes_for_user(profile, _thai_menu(), n=3)
    assert len(top_3) == 3
