"""Tests for the group dining system (Brick 10).

Run with:
    python -m pytest backend/tests/test_group_dining.py -v
"""

import sys
import os
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# In-memory fake Supabase
# ---------------------------------------------------------------------------

_tables: dict = {}


def _reset_tables():
    global _tables
    _tables = {
        "user_profiles": [],
        "user_taste_profiles": [],
        "friend_requests": [],
        "friendships": [],
        "interaction_logs": [],
        "saved_dishes": [],
        "chat_sessions": [],
        "onboarding_questions": [],
        "dining_plans": [],
        "dining_plan_members": [],
        "group_messages": [],
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

    def update(self, row):
        self._mode = "update"
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
                matched.sort(
                    key=lambda r: r.get(self._order_col, ""),
                    reverse=self._order_desc,
                )
            if self._columns != "*":
                cols = [c.strip() for c in self._columns.split(",")]
                matched = [{k: r.get(k) for k in cols} for r in matched]
            return _FakeResult(matched)

        if self._mode == "insert":
            row = dict(self._payload)
            if "id" not in row or row["id"] is None:
                row["id"] = str(uuid.uuid4())

            # Unique constraints
            if self._table == "user_profiles":
                for existing in rows:
                    if existing.get("username") == row.get("username"):
                        raise Exception("duplicate key (23505)")
                    if existing.get("id") == row.get("id"):
                        raise Exception("duplicate key (23505)")
            if self._table == "dining_plan_members":
                for existing in rows:
                    if (
                        existing.get("plan_id") == row.get("plan_id")
                        and existing.get("user_id") == row.get("user_id")
                    ):
                        raise Exception("duplicate key (23505)")
            if self._table == "saved_dishes":
                for existing in rows:
                    if (
                        existing["user_id"] == row.get("user_id")
                        and existing["dish_name"] == row.get("dish_name")
                        and existing["restaurant_slug"] == row.get("restaurant_slug")
                    ):
                        raise Exception("duplicate key (23505)")

            rows.append(row)
            return _FakeResult([row])

        if self._mode == "upsert":
            row = dict(self._payload)
            _tables[self._table] = [
                r for r in rows if r.get("id") != row.get("id")
            ]
            _tables[self._table].append(row)
            return _FakeResult([row])

        if self._mode == "update":
            matched = self._apply_filters(rows)
            for r in matched:
                r.update(self._payload)
            return _FakeResult(matched)

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
        class admin:
            @staticmethod
            def create_user(data):
                pass

        @staticmethod
        def get_user(token):
            raise Exception("Use x-user-id header for tests")


# Patch environment and modules before importing app
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import routers.user_intelligence as _ui_mod
import routers.friends as _friends_mod
import routers.group_dining as _gd_mod

_ui_mod._supabase_client = _FakeSupabase()
_friends_mod._supabase_client = _FakeSupabase()
_gd_mod._supabase_client = _FakeSupabase()

# Mock AI generation
_ai_calls = []


def _mock_ai_generate(plan_id, members_ctx, constraints_ctx, messages_ctx):
    _ai_calls.append(
        {
            "plan_id": plan_id,
            "members_ctx": members_ctx,
            "constraints_ctx": constraints_ctx,
            "messages_ctx": messages_ctx,
        }
    )
    return "I suggest we try Thai Palace! Everyone loves it."


_gd_mod._ai_generate_fn = _mock_ai_generate

from main import app

client = TestClient(app)

USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())
USER_C = str(uuid.uuid4())
USER_D = str(uuid.uuid4())  # Not in any plan


@pytest.fixture(autouse=True)
def clean_tables():
    _reset_tables()
    _ai_calls.clear()
    _ui_mod._supabase_client = _FakeSupabase()
    _friends_mod._supabase_client = _FakeSupabase()
    _gd_mod._supabase_client = _FakeSupabase()
    _gd_mod._ai_generate_fn = _mock_ai_generate
    yield
    _reset_tables()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_profiles():
    """Create user profiles for A, B, C."""
    for uid, uname in [(USER_A, "alice"), (USER_B, "bob"), (USER_C, "carol")]:
        client.post(
            "/profile/setup",
            json={"username": uname, "display_name": uname.title()},
            headers={"x-user-id": uid},
        )


def _create_plan(creator=USER_A, friends=None):
    """Create a plan with friends."""
    if friends is None:
        friends = [USER_B, USER_C]
    resp = client.post(
        "/plans",
        json={"name": "Dinner tonight", "friend_ids": friends},
        headers={"x-user-id": creator},
    )
    return resp


# ---------------------------------------------------------------------------
# 1. Create plan
# ---------------------------------------------------------------------------


def test_create_plan():
    _setup_profiles()
    resp = _create_plan()
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"]["name"] == "Dinner tonight"
    assert data["plan"]["status"] == "active"
    members = data["members"]
    assert len(members) == 3
    statuses = {m["status"] for m in members}
    assert "joined" in statuses
    assert "invited" in statuses


# ---------------------------------------------------------------------------
# 2. List plans — all members see it
# ---------------------------------------------------------------------------


def test_list_plans():
    _setup_profiles()
    _create_plan()

    for uid in [USER_A, USER_B, USER_C]:
        resp = client.get("/plans", headers={"x-user-id": uid})
        assert resp.status_code == 200
        assert len(resp.json()["plans"]) == 1


# ---------------------------------------------------------------------------
# 3. Join plan
# ---------------------------------------------------------------------------


def test_join_plan():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]

    resp = client.post(
        f"/plans/{plan_id}/join",
        headers={"x-user-id": USER_B},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "joined"

    # Verify in DB
    members = [
        m
        for m in _tables["dining_plan_members"]
        if m["plan_id"] == plan_id and m["user_id"] == USER_B
    ]
    assert members[0]["status"] == "joined"


# ---------------------------------------------------------------------------
# 4. Decline plan
# ---------------------------------------------------------------------------


def test_decline_plan():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]

    resp = client.post(
        f"/plans/{plan_id}/decline",
        headers={"x-user-id": USER_C},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"


# ---------------------------------------------------------------------------
# 5. Send message
# ---------------------------------------------------------------------------


def test_send_message():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]

    # User A (creator, joined) sends message
    resp = client.post(
        f"/plans/{plan_id}/messages",
        json={"content": "Hey everyone!"},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"]["content"] == "Hey everyone!"
    assert data["message"]["sender_type"] == "user"


# ---------------------------------------------------------------------------
# 6. Non-member blocked
# ---------------------------------------------------------------------------


def test_non_member_blocked():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]

    resp = client.post(
        f"/plans/{plan_id}/messages",
        json={"content": "I shouldn't be here"},
        headers={"x-user-id": USER_D},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 7. AI trigger on keyword
# ---------------------------------------------------------------------------


def test_ai_trigger_on_keyword():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]

    # First send a non-first message so we test keyword trigger
    client.post(
        f"/plans/{plan_id}/messages",
        json={"content": "Hey all"},
        headers={"x-user-id": USER_A},
    )
    _ai_calls.clear()

    resp = client.post(
        f"/plans/{plan_id}/messages",
        json={"content": "Can you recommend a place?"},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_response"] is not None
    assert "Thai Palace" in data["ai_response"]["content"]
    assert len(_ai_calls) == 1


# ---------------------------------------------------------------------------
# 8. AI silent on normal chat
# ---------------------------------------------------------------------------


def test_ai_silent_on_normal_chat():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]

    # First message triggers AI (welcome), so send that first
    client.post(
        f"/plans/{plan_id}/messages",
        json={"content": "Starting chat"},
        headers={"x-user-id": USER_A},
    )
    _ai_calls.clear()

    resp = client.post(
        f"/plans/{plan_id}/messages",
        json={"content": "hey everyone how are you"},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    assert resp.json()["ai_response"] is None
    assert len(_ai_calls) == 0


# ---------------------------------------------------------------------------
# 9. Get messages with polling (after timestamp)
# ---------------------------------------------------------------------------


def test_get_messages_polling():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]

    # Send 3 messages
    for text in ["msg1", "msg2", "msg3"]:
        client.post(
            f"/plans/{plan_id}/messages",
            json={"content": text},
            headers={"x-user-id": USER_A},
        )

    # Get all messages
    resp = client.get(
        f"/plans/{plan_id}/messages",
        headers={"x-user-id": USER_A},
    )
    all_msgs = resp.json()["messages"]
    # At least 3 user messages (might have AI responses too)
    user_msgs = [m for m in all_msgs if m["sender_type"] == "user"]
    assert len(user_msgs) >= 3

    # Polling with a future timestamp should return 0 messages
    future_ts = "2099-01-01T00:00:00+00:00"
    resp2 = client.get(
        f"/plans/{plan_id}/messages?after={future_ts}",
        headers={"x-user-id": USER_A},
    )
    after_msgs = resp2.json()["messages"]
    assert len(after_msgs) == 0

    # Polling with a past timestamp should return all messages
    past_ts = "2020-01-01T00:00:00+00:00"
    resp3 = client.get(
        f"/plans/{plan_id}/messages?after={past_ts}",
        headers={"x-user-id": USER_A},
    )
    past_msgs = resp3.json()["messages"]
    assert len(past_msgs) == len(all_msgs)


# ---------------------------------------------------------------------------
# 10. Group recommendations (skip if no menus dir)
# ---------------------------------------------------------------------------


def test_group_recommendations():
    _setup_profiles()

    # Create taste profiles for members
    for uid in [USER_A, USER_B]:
        _tables["user_taste_profiles"].append(
            {
                "id": uid,
                "spice_tolerance": 0.7,
                "sweetness_preference": 0.5,
                "adventurousness": 0.6,
                "price_comfort": 0.5,
                "meal_size_preference": 0.5,
                "protein_preference": {"beef": 0.7, "chicken": 0.6},
                "cuisine_preferences": {"thai": 0.8, "italian": 0.6},
                "texture_preferences": {"crispy": 0.7},
                "dietary_restrictions": [],
            }
        )

    plan_resp = _create_plan(friends=[USER_B])
    plan_id = plan_resp.json()["plan"]["id"]
    client.post(f"/plans/{plan_id}/join", headers={"x-user-id": USER_B})

    resp = client.get(
        f"/plans/{plan_id}/recommendations",
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    # Result depends on menu files existing, just check structure
    data = resp.json()
    assert "restaurants" in data


# ---------------------------------------------------------------------------
# 11. Cancel plan
# ---------------------------------------------------------------------------


def test_cancel_plan():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]

    resp = client.post(
        f"/plans/{plan_id}/cancel",
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    plan = [p for p in _tables["dining_plans"] if p["id"] == plan_id]
    assert plan[0]["status"] == "cancelled"


# ---------------------------------------------------------------------------
# 12. Decide restaurant
# ---------------------------------------------------------------------------


def test_decide_restaurant():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]

    resp = client.post(
        f"/plans/{plan_id}/decide",
        json={"restaurant_slug": "thai-palace"},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "decided"
    assert resp.json()["restaurant_slug"] == "thai-palace"


# ---------------------------------------------------------------------------
# 13. Welcome message (first message triggers AI)
# ---------------------------------------------------------------------------


def test_welcome_message():
    _setup_profiles()
    plan_resp = _create_plan()
    plan_id = plan_resp.json()["plan"]["id"]
    _ai_calls.clear()

    resp = client.post(
        f"/plans/{plan_id}/messages",
        json={"content": "Hey everyone!"},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    # First message should trigger AI
    assert resp.json()["ai_response"] is not None
    assert len(_ai_calls) == 1
