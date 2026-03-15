"""Preference engine orchestrator.

Main entry point that coordinates rule-based processing and LLM extraction,
then persists the updated profile to Supabase.
"""

from __future__ import annotations

from engines.preference_rules import process_interaction
from engines.chat_extractor import extract_preferences_from_chat, apply_extracted_signals

# Interaction types handled by the rule-based processor
_RULE_BASED_TYPES = {
    "dish_save",
    "dish_unsave",
    "filter_apply",
    "search_query",
    "restaurant_tap",
}


def should_run_chat_extraction(interaction_type: str, payload: dict) -> bool:
    """Return True if this interaction warrants LLM chat extraction.

    Triggers when a chat_message interaction signals end-of-session
    (payload has ``session_ended: true``) or when the message count
    in the payload indicates enough history to analyse.
    """
    if interaction_type != "chat_message":
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("session_ended"):
        return True
    # Also trigger if the payload carries a full messages list with 3+ user msgs
    messages = payload.get("messages", [])
    if isinstance(messages, list):
        user_count = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "user")
        if user_count >= 3:
            return True
    return False


def process_and_update_profile(
    user_id: str,
    interaction_type: str,
    payload: dict,
    supabase_client,
) -> dict:
    """Fetch profile → apply rules / LLM extraction → save back.

    Returns the updated profile dict.
    """
    # 1. Fetch current taste profile
    result = (
        supabase_client
        .table("user_taste_profiles")
        .select("*")
        .eq("id", user_id)
        .execute()
    )
    if not result.data:
        # No profile yet (user skipped onboarding); nothing to update
        return {}

    profile = dict(result.data[0])

    # 2. Rule-based processing
    if interaction_type in _RULE_BASED_TYPES:
        profile = process_interaction(profile, interaction_type, payload)

    # 3. LLM chat extraction
    if should_run_chat_extraction(interaction_type, payload):
        messages = payload.get("messages", [])
        if isinstance(messages, list) and messages:
            signals = extract_preferences_from_chat(messages)
            if signals:
                profile = apply_extracted_signals(profile, signals)

    # 4. Increment version and save
    profile["profile_version"] = profile.get("profile_version", 1) + 1

    supabase_client.table("user_taste_profiles").upsert(profile).execute()

    # 5. Return updated profile
    return profile
