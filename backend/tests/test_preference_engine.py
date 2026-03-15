"""Comprehensive tests for the preference engine.

Run with:
    python -m pytest backend/tests/test_preference_engine.py -v
"""

import copy
import json
import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engines.preference_rules import process_interaction
from engines.chat_extractor import (
    extract_preferences_from_chat,
    apply_extracted_signals,
)
from engines.preference_engine import (
    process_and_update_profile,
    should_run_chat_extraction,
)


# ---------------------------------------------------------------------------
# Helper: baseline profile
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


# ===================================================================
# RULE-BASED TESTS (1-10)
# ===================================================================

# 1. Save a spicy Thai dish → thai cuisine up AND spice_tolerance up
def test_save_spicy_thai_dish():
    profile = _base_profile()
    process_interaction(profile, "dish_save", {
        "dish_name": "Spicy Pad Thai",
        "restaurant_slug": "thai-house",
        "price": 18.0,
        "dietary_info": ["spicy"],
    })
    assert profile["cuisine_preferences"]["thai"] > 0.5
    assert profile["spice_tolerance"] > 0.5


# 2. Save a cheap dish ($8) → price_comfort decreases
def test_save_cheap_dish():
    profile = _base_profile()
    process_interaction(profile, "dish_save", {
        "dish_name": "Cheese Slice",
        "price": 8.0,
    })
    assert profile["price_comfort"] < 0.5


# 3. Save an expensive dish ($45) → price_comfort increases
def test_save_expensive_dish():
    profile = _base_profile()
    process_interaction(profile, "dish_save", {
        "dish_name": "Wagyu Steak",
        "price": 45.0,
    })
    assert profile["price_comfort"] > 0.5


# 4. Unsave a dish → cuisine nudge reversed (smaller magnitude)
def test_unsave_dish():
    profile = _base_profile()
    original_thai = profile["cuisine_preferences"]["thai"]
    # First save (boost +0.05)
    process_interaction(profile, "dish_save", {
        "dish_name": "Pad Thai",
        "restaurant_slug": "thai-kitchen",
    })
    after_save = profile["cuisine_preferences"]["thai"]
    assert after_save > original_thai

    # Then unsave (reduce -0.03, smaller magnitude)
    process_interaction(profile, "dish_unsave", {
        "dish_name": "Pad Thai",
        "restaurant_slug": "thai-kitchen",
    })
    after_unsave = profile["cuisine_preferences"]["thai"]
    assert after_unsave < after_save
    # Net effect should still be positive (0.05 - 0.03 = 0.02)
    assert after_unsave > original_thai


# 5. Apply vegetarian filter → protein_preference.vegetarian increases
def test_filter_vegetarian():
    profile = _base_profile()
    process_interaction(profile, "filter_apply", {
        "filter_type": "dietary",
        "value": "vegetarian",
    })
    assert profile["protein_preference"]["vegetarian"] > 0.5


# 6. Apply halal filter → "halal" in dietary_restrictions
def test_filter_halal():
    profile = _base_profile()
    process_interaction(profile, "filter_apply", {
        "filter_type": "dietary",
        "value": "halal",
    })
    assert "halal" in profile["dietary_restrictions"]


# 7. Apply halal filter twice → not duplicated
def test_filter_halal_no_duplicate():
    profile = _base_profile()
    process_interaction(profile, "filter_apply", {
        "filter_type": "dietary",
        "value": "halal",
    })
    process_interaction(profile, "filter_apply", {
        "filter_type": "dietary",
        "value": "halal",
    })
    assert profile["dietary_restrictions"].count("halal") == 1


# 8. Search for "spicy ramen" → spice_tolerance nudged up slightly
def test_search_spicy():
    profile = _base_profile()
    process_interaction(profile, "search_query", {
        "query": "spicy ramen",
    })
    assert profile["spice_tolerance"] > 0.5
    # Weak signal: should be small nudge (+0.02)
    assert profile["spice_tolerance"] <= 0.55


# 9. 20 dish_save for Italian food → italian significantly above 0.5
def test_many_italian_saves():
    profile = _base_profile()
    for _ in range(20):
        process_interaction(profile, "dish_save", {
            "dish_name": "Margherita Pizza",
            "restaurant_slug": "italian-place",
            "price": 20.0,
        })
    # 20 * 0.05 = 1.0 added to 0.5 = 1.5, clamped to 1.0
    assert profile["cuisine_preferences"]["italian"] >= 0.75


# 10. Clamping: start at 0.98, save spicy dish, must not exceed 1.0
def test_clamping_upper_bound():
    profile = _base_profile()
    profile["spice_tolerance"] = 0.98
    process_interaction(profile, "dish_save", {
        "dish_name": "Extra Hot Wings",
        "dietary_info": ["spicy"],
    })
    assert profile["spice_tolerance"] <= 1.0


# ===================================================================
# LLM EXTRACTOR TESTS (11-15) — OpenAI is always mocked
# ===================================================================

def _mock_openai_response(content: str):
    """Create a mock OpenAI client that returns *content* as the completion."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[mock_choice]
    )
    return mock_client


def _chat_messages(user_texts: list[str]) -> list[dict]:
    """Build alternating user/assistant messages with at least *n* user msgs."""
    msgs = []
    for i, text in enumerate(user_texts):
        msgs.append({"role": "user", "content": text})
        msgs.append({"role": "assistant", "content": f"Response to: {text}"})
    return msgs


# 11. User says "I don't eat pork" → pork set to 0.0
def test_llm_pork_restriction():
    signals_json = json.dumps([{
        "dimension": "protein_preference.pork",
        "action": "set",
        "value": 0.0,
        "confidence": 0.95,
        "evidence": "I don't eat pork",
    }])
    mock_client = _mock_openai_response(signals_json)

    signals = extract_preferences_from_chat(
        _chat_messages(["What's good here?", "I don't eat pork", "Show me chicken dishes"]),
        openai_client=mock_client,
    )
    assert len(signals) == 1
    assert signals[0]["dimension"] == "protein_preference.pork"

    profile = _base_profile()
    apply_extracted_signals(profile, signals)
    assert profile["protein_preference"]["pork"] == 0.0


# 12. User says "too spicy" → spice_tolerance nudged down
def test_llm_too_spicy():
    signals_json = json.dumps([{
        "dimension": "spice_tolerance",
        "action": "nudge_down",
        "confidence": 0.8,
        "evidence": "This is too spicy for me",
    }])
    mock_client = _mock_openai_response(signals_json)

    signals = extract_preferences_from_chat(
        _chat_messages(["What's popular?", "This is too spicy for me", "Something milder?"]),
        openai_client=mock_client,
    )
    assert len(signals) == 1

    profile = _base_profile()
    apply_extracted_signals(profile, signals)
    assert profile["spice_tolerance"] < 0.5


# 13. Only 2 user messages → LLM NOT called
def test_llm_too_few_messages():
    mock_client = _mock_openai_response("[]")
    signals = extract_preferences_from_chat(
        _chat_messages(["Hello", "What's good?"]),
        openai_client=mock_client,
    )
    assert signals == []
    mock_client.chat.completions.create.assert_not_called()


# 14. Malformed JSON from OpenAI → graceful handling, empty list
def test_llm_malformed_json():
    mock_client = _mock_openai_response("This is not JSON at all {broken")
    signals = extract_preferences_from_chat(
        _chat_messages(["Hi", "What about chicken?", "Any spicy options?"]),
        openai_client=mock_client,
    )
    assert signals == []


# 15. Signal with confidence 0.5 → NOT applied
def test_llm_low_confidence_not_applied():
    signals = [{
        "dimension": "spice_tolerance",
        "action": "nudge_up",
        "confidence": 0.5,
        "evidence": "Maybe something spicy",
    }]
    profile = _base_profile()
    original = profile["spice_tolerance"]
    apply_extracted_signals(profile, signals)
    assert profile["spice_tolerance"] == original  # unchanged


# ===================================================================
# INTEGRATION TEST (16)
# ===================================================================

def test_full_flow_onboarding_then_interactions():
    """Create a profile via onboarding, then apply 5 interactions via rule engine."""
    # Build an initial profile as if onboarding completed (all-A = spicy/adventurous)
    from routers.user_intelligence import _compute_taste_profile
    from models.user_intelligence import OnboardingAnswer, UserTasteProfile

    user_id = str(uuid.uuid4())
    answers = [OnboardingAnswer(question_index=i, chosen_option="a") for i in range(1, 6)]
    computed = _compute_taste_profile(answers)

    # Build full profile from computed + defaults
    profile = _base_profile()
    profile["id"] = user_id
    for key in ("spice_tolerance", "sweetness_preference", "adventurousness",
                "price_comfort", "meal_size_preference"):
        profile[key] = computed.get(key, profile[key])
    for key in ("cuisine_preferences", "protein_preference", "texture_preferences"):
        if key in computed and isinstance(computed[key], dict):
            defaults = UserTasteProfile(id=user_id).__dict__[key]
            profile[key] = {**defaults, **computed[key]}
    profile["onboarding_completed"] = True

    initial_spice = profile["spice_tolerance"]
    assert initial_spice >= 0.75  # Sanity: all-A yields high spice

    # Apply 5 interactions through the rule engine
    # 1. Save a spicy Thai dish
    process_interaction(profile, "dish_save", {
        "dish_name": "Green Curry",
        "restaurant_slug": "thai-palace",
        "price": 16.0,
        "dietary_info": ["spicy"],
    })

    # 2. Filter: vegetarian
    process_interaction(profile, "filter_apply", {
        "filter_type": "dietary",
        "value": "vegetarian",
    })

    # 3. Search "spicy noodles"
    process_interaction(profile, "search_query", {
        "query": "spicy noodles",
    })

    # 4. Save expensive sushi
    process_interaction(profile, "dish_save", {
        "dish_name": "Omakase Sushi",
        "restaurant_slug": "japanese-fine-dining",
        "price": 50.0,
    })

    # 5. Restaurant tap on Korean spot
    process_interaction(profile, "restaurant_tap", {
        "restaurant_slug": "korean-bbq-house",
    })

    # Verify profile evolved
    assert profile["cuisine_preferences"]["thai"] > 0.5
    assert profile["protein_preference"]["vegetarian"] > 0.5
    assert profile["spice_tolerance"] > initial_spice
    assert profile["cuisine_preferences"]["japanese"] > 0.5
    assert profile["cuisine_preferences"]["korean"] > 0.5
    assert profile["price_comfort"] > 0.5  # expensive sushi pushed it up
