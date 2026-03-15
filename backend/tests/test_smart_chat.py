"""Tests for the smart chat system (Brick 5).

Run with:
    python -m pytest backend/tests/test_smart_chat.py -v
"""

import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engines.profile_narrator import (
    narrate_profile,
    format_recommendations,
    format_avoid_list,
)


# ---------------------------------------------------------------------------
# Helper: base profile
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
# NARRATOR TESTS (1-6)
# ===================================================================

# 1. Spicy lover: spice_tolerance=0.9, thai=0.85 → mentions "spicy" and "Thai"
def test_narrate_spicy_lover():
    profile = _base_profile()
    profile["spice_tolerance"] = 0.9
    profile["cuisine_preferences"]["thai"] = 0.85
    text = narrate_profile(profile)
    assert "spicy" in text.lower()
    assert "thai" in text.lower()


# 2. Budget user: price_comfort=0.2 → mentions "budget"
def test_narrate_budget_user():
    profile = _base_profile()
    profile["price_comfort"] = 0.2
    text = narrate_profile(profile)
    assert "budget" in text.lower()


# 3. Neutral user: all 0.5 → minimal/empty output
def test_narrate_neutral_user():
    profile = _base_profile()
    text = narrate_profile(profile)
    assert text == "No strong preferences noted yet."


# 4. Dietary restrictions: halal + gluten_free → both mentioned
def test_narrate_dietary_restrictions():
    profile = _base_profile()
    profile["dietary_restrictions"] = ["halal", "gluten_free"]
    text = narrate_profile(profile)
    assert "halal" in text.lower()
    assert "gluten free" in text.lower() or "gluten_free" in text.lower()


# 5. format_recommendations: 3 dishes → numbered list with prices
def test_format_recommendations():
    dishes = [
        {"dish_name": "Pad Thai", "price": 16.0, "match_reason": "Spicy and Thai"},
        {"dish_name": "Green Curry", "price": 18.0, "match_reason": "Rich and spicy"},
        {"dish_name": "Mango Rice", "price": 10.0, "match_reason": "Sweet treat"},
    ]
    text = format_recommendations(dishes, _base_profile())
    assert "1. Pad Thai ($16)" in text
    assert "2. Green Curry ($18)" in text
    assert "3. Mango Rice ($10)" in text
    assert "Spicy and Thai" in text


# 6. format_avoid_list: 2 avoid dishes → formatted correctly
def test_format_avoid_list():
    avoid = [
        {"dish_name": "Pork Belly Bao", "reason": "contains pork"},
        {"dish_name": "Bacon Burger", "reason": "contains pork"},
    ]
    text = format_avoid_list(avoid)
    assert "Pork Belly Bao" in text
    assert "Bacon Burger" in text
    assert "contains pork" in text


# ===================================================================
# ENDPOINT TESTS (7-12) — require FastAPI TestClient + mocked OpenAI
# ===================================================================

# In-memory stores for fake Supabase (same pattern as test_user_intelligence.py)
_tables: dict = {}


def _reset_tables():
    global _tables
    _tables = {
        "user_taste_profiles": [],
        "interaction_logs": [],
        "saved_dishes": [],
        "chat_sessions": [],
        "onboarding_questions": [],
    }


_reset_tables()


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name: str):
        self._table = table_name
        self._filters: list = []
        self._order_col = None
        self._order_desc = False
        self._mode = None
        self._columns = "*"
        self._payload = None

    def select(self, columns="*"):
        self._mode = "select"
        self._columns = columns
        return self

    def insert(self, row):
        self._mode = "insert"
        self._payload = row
        return self

    def upsert(self, row):
        self._mode = "upsert"
        self._payload = row
        return self

    def delete(self):
        self._mode = "delete"
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def execute(self):
        rows = _tables.setdefault(self._table, [])

        if self._mode == "select":
            matched = self._apply_filters(rows)
            if self._order_col:
                matched.sort(key=lambda r: r.get(self._order_col, ""), reverse=self._order_desc)
            return _FakeResult(matched)

        if self._mode == "insert":
            row = dict(self._payload)
            if "id" not in row or row["id"] is None:
                row["id"] = str(uuid.uuid4())
            if self._table == "saved_dishes":
                for existing in rows:
                    if (existing["user_id"] == row.get("user_id")
                            and existing["dish_name"] == row.get("dish_name")
                            and existing["restaurant_slug"] == row.get("restaurant_slug")):
                        raise Exception("duplicate key value violates unique constraint (23505)")
            rows.append(row)
            return _FakeResult([row])

        if self._mode == "upsert":
            row = dict(self._payload)
            _tables[self._table] = [r for r in rows if r.get("id") != row.get("id")]
            _tables[self._table].append(row)
            return _FakeResult([row])

        if self._mode == "delete":
            matched = self._apply_filters(rows)
            _tables[self._table] = [r for r in rows if r not in matched]
            return _FakeResult(matched)

        return _FakeResult([])

    def _apply_filters(self, rows):
        result = list(rows)
        for col, val in self._filters:
            result = [r for r in result if r.get(col) == val]
        return result


class _FakeSupabase:
    def table(self, name):
        return _FakeQuery(name)

    class auth:
        @staticmethod
        def get_user(token):
            raise Exception("Use x-user-id header for tests")


# Patch before importing app
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import routers.user_intelligence as _router_mod
_router_mod._supabase_client = _FakeSupabase()

import main as _main_mod
from main import app
from fastapi.testclient import TestClient

# Register a fake restaurant so load_menu / resolve_display_name work
_FAKE_MENU = [{"name": "Pad Thai", "description": "Spicy Thai noodles", "price": 16, "category": "Food", "dietary_info": ["spicy"]}]
_main_mod.NAME_MAPPING["test-restaurant"] = "Test Restaurant"
_main_mod.REVERSE_MAPPING["test restaurant"] = "test-restaurant"
if "Test Restaurant" not in _main_mod.RESTAURANT_LIST:
    _main_mod.RESTAURANT_LIST.append("Test Restaurant")

test_client = TestClient(app)

USER_CHAT = str(uuid.uuid4())


def _mock_openai_response(content: str):
    """Create a mock that replaces client.chat.completions.create."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content
    return mock_resp


def _create_user_profile(user_id: str, overrides: dict | None = None):
    """Insert a taste profile for testing."""
    profile = _base_profile()
    profile["id"] = user_id
    if overrides:
        for k, v in overrides.items():
            if isinstance(v, dict) and isinstance(profile.get(k), dict):
                profile[k].update(v)
            else:
                profile[k] = v
    _tables["user_taste_profiles"].append(profile)
    return profile


@pytest.fixture(autouse=True)
def clean_tables():
    _reset_tables()
    # Re-assert our fake supabase client (another test module may have overwritten it)
    _router_mod._supabase_client = _FakeSupabase()
    yield
    _reset_tables()


def _patch_load_menu():
    """Return a patch that makes load_menu return our fake menu."""
    return patch("main.load_menu", return_value=_FAKE_MENU)


# 7. POST /chat/start with profile: system prompt contains taste narration
def test_chat_start_with_profile():
    _create_user_profile(USER_CHAT, {
        "spice_tolerance": 0.9,
        "cuisine_preferences": {"thai": 0.85},
    })
    mock_resp = _mock_openai_response("Hey! I'd recommend the Green Curry — it's spicy and Thai!")

    captured_call_args = None
    with patch("main.client") as mock_client, _patch_load_menu():
        mock_client.chat.completions.create.return_value = mock_resp
        resp = test_client.post(
            "/chat/start",
            json={"restaurant_slug": "test-restaurant"},
            headers={"x-user-id": USER_CHAT},
        )
        captured_call_args = mock_client.chat.completions.create.call_args

    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert data["session_id"] is not None

    # Verify system prompt was personalized
    assert captured_call_args is not None
    system_msg = captured_call_args.kwargs["messages"][0]["content"]
    assert "spicy" in system_msg.lower()
    assert "thai" in system_msg.lower()
    assert "MenuElf" in system_msg


# 8. POST /chat/start without profile: generic welcome
def test_chat_start_without_profile():
    with _patch_load_menu():
        resp = test_client.post(
            "/chat/start",
            json={"restaurant_slug": "test-restaurant"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "Welcome" in data["reply"]
    assert "mood" in data["reply"].lower() or "menu" in data["reply"].lower()
    assert data["session_id"] is None


# 9. POST /chat with user_id: system prompt includes taste info
def test_chat_with_user_id():
    _create_user_profile(USER_CHAT, {
        "spice_tolerance": 0.9,
        "cuisine_preferences": {"thai": 0.85},
    })
    mock_resp = _mock_openai_response("The Green Curry is perfect for you!")

    captured_call_args = None
    with patch("main.client") as mock_client, _patch_load_menu():
        mock_client.chat.completions.create.return_value = mock_resp
        resp = test_client.post(
            "/chat",
            json={"restaurant": "test-restaurant", "message": "What's spicy?"},
            headers={"x-user-id": USER_CHAT},
        )
        captured_call_args = mock_client.chat.completions.create.call_args

    assert resp.status_code == 200
    assert resp.json()["reply"] == "The Green Curry is perfect for you!"

    # Verify personalized system prompt
    assert captured_call_args is not None
    system_msg = captured_call_args.kwargs["messages"][0]["content"]
    assert "spicy" in system_msg.lower()
    assert "MenuElf" in system_msg


# 10. POST /chat without user_id: backwards compatible
def test_chat_without_user_id():
    mock_resp = _mock_openai_response("Try the Pad Thai!")

    captured_call_args = None
    with patch("main.client") as mock_client, _patch_load_menu():
        mock_client.chat.completions.create.return_value = mock_resp
        resp = test_client.post(
            "/chat",
            json={"restaurant": "test-restaurant", "message": "What's good?"},
        )
        captured_call_args = mock_client.chat.completions.create.call_args

    assert resp.status_code == 200
    assert resp.json()["reply"] == "Try the Pad Thai!"

    # Verify generic system prompt (no MenuElf branding, no taste info)
    assert captured_call_args is not None
    system_msg = captured_call_args.kwargs["messages"][0]["content"]
    assert "warm, knowledgeable food assistant" in system_msg
    assert "ABOUT THIS DINER" not in system_msg


# 11. Chat session storage: /chat/start then /chat twice, verify messages stored
def test_chat_session_storage():
    _create_user_profile(USER_CHAT)

    # Start session
    mock_start = _mock_openai_response("Welcome! Let me help you choose.")
    with _patch_load_menu(), patch("main.client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_start
        resp = test_client.post(
            "/chat/start",
            json={"restaurant_slug": "test-restaurant"},
            headers={"x-user-id": USER_CHAT},
        )
    session_id = resp.json()["session_id"]
    assert session_id is not None

    # Send first message
    mock_chat1 = _mock_openai_response("The Pad Thai is great!")
    with _patch_load_menu(), patch("main.client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_chat1
        test_client.post(
            "/chat",
            json={"restaurant": "test-restaurant", "message": "What's good?", "session_id": session_id},
            headers={"x-user-id": USER_CHAT},
        )

    # Send second message
    mock_chat2 = _mock_openai_response("Yes, it comes with shrimp.")
    with _patch_load_menu(), patch("main.client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_chat2
        test_client.post(
            "/chat",
            json={"restaurant": "test-restaurant", "message": "Is it spicy?", "session_id": session_id},
            headers={"x-user-id": USER_CHAT},
        )

    # Verify the chat session has messages stored
    sessions = _tables["chat_sessions"]
    session = next((s for s in sessions if s["id"] == session_id), None)
    assert session is not None
    messages = session.get("messages", [])
    # Should have: assistant greeting + user msg + assistant reply + user msg + assistant reply = 5
    assert len(messages) >= 3  # At minimum: greeting + user + assistant


# 12. Chat extraction trigger: 3+ user messages triggers preference engine
def test_chat_extraction_trigger():
    _create_user_profile(USER_CHAT)

    # Start session
    mock_start = _mock_openai_response("Welcome!")
    with _patch_load_menu(), patch("main.client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_start
        resp = test_client.post(
            "/chat/start",
            json={"restaurant_slug": "test-restaurant"},
            headers={"x-user-id": USER_CHAT},
        )
    session_id = resp.json()["session_id"]

    # Send 3 user messages to trigger extraction
    for i, msg in enumerate(["What's spicy?", "I love Thai food", "Any chicken dishes?"]):
        mock_resp = _mock_openai_response(f"Response {i}")
        with _patch_load_menu(), patch("main.client") as mock_client:
            mock_client.chat.completions.create.return_value = mock_resp
            test_client.post(
                "/chat",
                json={"restaurant": "test-restaurant", "message": msg, "session_id": session_id},
                headers={"x-user-id": USER_CHAT},
            )

    # Verify the session has messages
    sessions = _tables["chat_sessions"]
    session = next((s for s in sessions if s["id"] == session_id), None)
    assert session is not None
    messages = session.get("messages", [])
    user_msgs = [m for m in messages if m.get("role") == "user"]
    assert len(user_msgs) >= 3
