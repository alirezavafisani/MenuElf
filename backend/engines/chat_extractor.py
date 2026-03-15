"""LLM-based chat preference extractor.

Uses OpenAI GPT-4o-mini to extract taste-profile signals from chat
conversations, then applies them to the user's profile.
"""

from __future__ import annotations

import json
import os
from typing import Any

_SYSTEM_PROMPT = """\
You are a preference extraction engine for a restaurant app. \
Analyze the following chat conversation between a user and a menu AI assistant. \
Extract any food preference signals.

Return ONLY a JSON array of signals. Each signal has:
- "dimension": the taste profile field to update (e.g., "spice_tolerance", \
"cuisine_preferences.thai", "protein_preference.beef", "dietary_restrictions")
- "action": either "set" (for absolute values like dietary restrictions), \
"nudge_up" (+0.05), or "nudge_down" (-0.05)
- "value": for "set" actions, the value to set. For nudge actions, omit this field.
- "confidence": float 0.0 to 1.0 indicating how confident you are
- "evidence": the exact quote from the conversation that led to this signal

Only extract signals with confidence >= 0.7. \
If no clear signals, return an empty array [].

Examples of what to extract:
- "I don't eat pork" → {{"dimension": "protein_preference.pork", "action": "set", \
"value": 0.0, "confidence": 0.95, "evidence": "I don't eat pork"}}
- "This is too spicy for me" → {{"dimension": "spice_tolerance", "action": "nudge_down", \
"confidence": 0.8, "evidence": "This is too spicy for me"}}
- "I love trying new things" → {{"dimension": "adventurousness", "action": "nudge_up", \
"confidence": 0.75, "evidence": "I love trying new things"}}
- "We're on a budget tonight" → DO NOT extract (temporary, not a lasting preference)
- "What's vegetarian?" → DO NOT extract (asking doesn't mean they are vegetarian)\
"""

_MIN_USER_MESSAGES = 3
_CONFIDENCE_THRESHOLD = 0.7


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_preferences_from_chat(
    messages: list[dict[str, str]],
    *,
    openai_client: Any | None = None,
) -> list[dict]:
    """Call GPT-4o-mini to extract preference signals from a conversation.

    Returns a list of signal dicts.  Returns [] on any error or if there
    are fewer than _MIN_USER_MESSAGES user messages.
    """
    user_msgs = [m for m in messages if m.get("role") == "user"]
    if len(user_msgs) < _MIN_USER_MESSAGES:
        return []

    # Build the client
    if openai_client is None:
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        except Exception:
            return []

    # Format conversation for the LLM
    conversation_text = "\n".join(
        f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
        for m in messages
    )

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": conversation_text},
            ],
            temperature=0.2,
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines)

        signals = json.loads(raw)
        if not isinstance(signals, list):
            return []
        return signals

    except (json.JSONDecodeError, Exception):
        return []


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

def apply_extracted_signals(profile: dict, signals: list[dict]) -> dict:
    """Apply extracted LLM signals to a taste profile.

    Only applies signals with confidence >= _CONFIDENCE_THRESHOLD.
    All float values are clamped to [0.0, 1.0].
    """
    for sig in signals:
        confidence = sig.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)) or confidence < _CONFIDENCE_THRESHOLD:
            continue

        dimension = sig.get("dimension", "")
        action = sig.get("action", "")

        if not dimension or not action:
            continue

        if action == "set":
            value = sig.get("value")
            if value is None:
                continue
            _set_dimension(profile, dimension, value)
        elif action == "nudge_up":
            _nudge_dimension(profile, dimension, +0.05)
        elif action == "nudge_down":
            _nudge_dimension(profile, dimension, -0.05)

    return profile


def _set_dimension(profile: dict, dimension: str, value: Any) -> None:
    """Set a dimension to an absolute value."""
    if "." in dimension:
        parent, child = dimension.split(".", 1)
        container = profile.get(parent)
        if not isinstance(container, dict):
            container = {}
            profile[parent] = container
        if isinstance(value, (int, float)):
            container[child] = _clamp(float(value))
        else:
            container[child] = value
    elif dimension == "dietary_restrictions":
        # "set" on dietary_restrictions means add to the list
        restrictions = profile.get("dietary_restrictions", [])
        if not isinstance(restrictions, list):
            restrictions = []
            profile["dietary_restrictions"] = restrictions
        if isinstance(value, str) and value not in restrictions:
            restrictions.append(value)
        elif isinstance(value, list):
            for v in value:
                if v not in restrictions:
                    restrictions.append(v)
    else:
        if isinstance(value, (int, float)):
            profile[dimension] = _clamp(float(value))
        else:
            profile[dimension] = value


def _nudge_dimension(profile: dict, dimension: str, delta: float) -> None:
    if "." in dimension:
        parent, child = dimension.split(".", 1)
        container = profile.get(parent)
        if not isinstance(container, dict):
            container = {}
            profile[parent] = container
        current = container.get(child, 0.5)
        if not isinstance(current, (int, float)):
            current = 0.5
        container[child] = _clamp(current + delta)
    else:
        current = profile.get(dimension, 0.5)
        if not isinstance(current, (int, float)):
            current = 0.5
        profile[dimension] = _clamp(current + delta)
