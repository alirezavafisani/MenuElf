"""Tests for the friends system.

Run with:
    python -m pytest backend/tests/test_friends.py -v
"""

import sys
import os
import re
import uuid
from unittest.mock import MagicMock, patch

import pytest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# In-memory fake Supabase (shared with user_intelligence tests pattern)
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
    }


_reset_tables()


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Chainable fake that mimics supabase-py's query builder."""

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
            # Filter columns
            if self._columns != "*":
                cols = [c.strip() for c in self._columns.split(",")]
                matched = [{k: r.get(k) for k in cols} for r in matched]
            return _FakeResult(matched)

        if self._mode == "insert":
            row = dict(self._payload)
            if "id" not in row or row["id"] is None:
                row["id"] = str(uuid.uuid4())

            # Check unique constraints
            if self._table == "user_profiles":
                for existing in rows:
                    if existing.get("username") == row.get("username"):
                        raise Exception(
                            "duplicate key value violates unique constraint (23505)"
                        )
                    if existing.get("id") == row.get("id"):
                        raise Exception(
                            "duplicate key value violates unique constraint (23505)"
                        )
            if self._table == "friend_requests":
                for existing in rows:
                    if (
                        existing.get("from_user_id") == row.get("from_user_id")
                        and existing.get("to_user_id") == row.get("to_user_id")
                    ):
                        raise Exception(
                            "duplicate key value violates unique constraint (23505)"
                        )
            if self._table == "friendships":
                for existing in rows:
                    if (
                        existing.get("user_a_id") == row.get("user_a_id")
                        and existing.get("user_b_id") == row.get("user_b_id")
                    ):
                        raise Exception(
                            "duplicate key value violates unique constraint (23505)"
                        )
            if self._table == "saved_dishes":
                for existing in rows:
                    if (
                        existing["user_id"] == row.get("user_id")
                        and existing["dish_name"] == row.get("dish_name")
                        and existing["restaurant_slug"] == row.get("restaurant_slug")
                    ):
                        raise Exception(
                            "duplicate key value violates unique constraint (23505)"
                        )

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


# Patch environment and supabase client before importing app
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import routers.user_intelligence as _ui_mod
import routers.friends as _friends_mod

_ui_mod._supabase_client = _FakeSupabase()
_friends_mod._supabase_client = _FakeSupabase()

from main import app

client = TestClient(app)

USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())
USER_C = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def clean_tables():
    _reset_tables()
    _ui_mod._supabase_client = _FakeSupabase()
    _friends_mod._supabase_client = _FakeSupabase()
    yield
    _reset_tables()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_profile(user_id: str, username: str, display_name: str = None):
    return client.post(
        "/profile/setup",
        json={
            "username": username,
            "display_name": display_name or username,
        },
        headers={"x-user-id": user_id},
    )


# ---------------------------------------------------------------------------
# 1. Create profile
# ---------------------------------------------------------------------------


def test_create_profile():
    resp = _setup_profile(USER_A, "alice_test")
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert profile["username"] == "alice_test"
    assert profile["display_name"] == "alice_test"
    assert profile["avatar_emoji"] == "🧝"


# ---------------------------------------------------------------------------
# 2. Duplicate username
# ---------------------------------------------------------------------------


def test_duplicate_username():
    _setup_profile(USER_A, "taken_name")
    resp = _setup_profile(USER_B, "taken_name")
    assert resp.status_code == 409
    assert "taken" in resp.json()["detail"].lower() or "already" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Invalid username format
# ---------------------------------------------------------------------------


def test_invalid_username_format():
    resp = _setup_profile(USER_A, "AB CD!")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 4. Username too short
# ---------------------------------------------------------------------------


def test_username_too_short():
    resp = _setup_profile(USER_A, "ab")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 5. Send friend request
# ---------------------------------------------------------------------------


def test_send_friend_request():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")

    resp = client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    assert resp.json()["request"]["from_user_id"] == USER_A


# ---------------------------------------------------------------------------
# 6. Self friend request
# ---------------------------------------------------------------------------


def test_self_friend_request():
    _setup_profile(USER_A, "alice")

    resp = client.post(
        "/friends/request",
        json={"username": "alice"},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 400
    assert "yourself" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 7. Duplicate request
# ---------------------------------------------------------------------------


def test_duplicate_request():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")

    client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )
    resp = client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 409
    assert "already" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 8. Accept request
# ---------------------------------------------------------------------------


def test_accept_request():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")

    # Send request
    client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )

    # Get incoming requests for User B
    resp = client.get(
        "/friends/requests/incoming",
        headers={"x-user-id": USER_B},
    )
    assert resp.status_code == 200
    requests = resp.json()["requests"]
    assert len(requests) == 1
    request_id = requests[0]["id"]

    # Accept
    resp = client.post(
        f"/friends/requests/{request_id}/accept",
        headers={"x-user-id": USER_B},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    # Verify friendship exists
    friendships = _tables["friendships"]
    assert len(friendships) == 1


# ---------------------------------------------------------------------------
# 9. Friends list
# ---------------------------------------------------------------------------


def test_friends_list():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")

    # Send and accept
    client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )
    reqs = client.get(
        "/friends/requests/incoming",
        headers={"x-user-id": USER_B},
    ).json()["requests"]
    client.post(
        f"/friends/requests/{reqs[0]['id']}/accept",
        headers={"x-user-id": USER_B},
    )

    # Both users see each other
    resp_a = client.get("/friends", headers={"x-user-id": USER_A})
    assert resp_a.status_code == 200
    friends_a = resp_a.json()["friends"]
    assert len(friends_a) == 1
    assert friends_a[0]["username"] == "bob"

    resp_b = client.get("/friends", headers={"x-user-id": USER_B})
    assert resp_b.status_code == 200
    friends_b = resp_b.json()["friends"]
    assert len(friends_b) == 1
    assert friends_b[0]["username"] == "alice"


# ---------------------------------------------------------------------------
# 10. Decline request
# ---------------------------------------------------------------------------


def test_decline_request():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")

    client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )
    reqs = client.get(
        "/friends/requests/incoming",
        headers={"x-user-id": USER_B},
    ).json()["requests"]
    request_id = reqs[0]["id"]

    resp = client.post(
        f"/friends/requests/{request_id}/decline",
        headers={"x-user-id": USER_B},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"

    # Verify status changed
    req_row = [r for r in _tables["friend_requests"] if r["id"] == request_id]
    assert req_row[0]["status"] == "declined"


# ---------------------------------------------------------------------------
# 11. Already friends
# ---------------------------------------------------------------------------


def test_already_friends_request():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")

    # Become friends
    client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )
    reqs = client.get(
        "/friends/requests/incoming",
        headers={"x-user-id": USER_B},
    ).json()["requests"]
    client.post(
        f"/friends/requests/{reqs[0]['id']}/accept",
        headers={"x-user-id": USER_B},
    )

    # Try to send another request
    resp = client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 400
    assert "already friends" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 12. Remove friend
# ---------------------------------------------------------------------------


def test_remove_friend():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")

    # Become friends
    client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )
    reqs = client.get(
        "/friends/requests/incoming",
        headers={"x-user-id": USER_B},
    ).json()["requests"]
    client.post(
        f"/friends/requests/{reqs[0]['id']}/accept",
        headers={"x-user-id": USER_B},
    )

    # Remove
    resp = client.delete(
        f"/friends/{USER_B}",
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200

    # Both should no longer see each other
    resp_a = client.get("/friends", headers={"x-user-id": USER_A})
    assert len(resp_a.json()["friends"]) == 0

    resp_b = client.get("/friends", headers={"x-user-id": USER_B})
    assert len(resp_b.json()["friends"]) == 0


# ---------------------------------------------------------------------------
# 13. Search users
# ---------------------------------------------------------------------------


def test_search_users():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")
    _setup_profile(USER_C, "bobby")

    resp = client.get(
        "/users/search?q=bob",
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    users = resp.json()["users"]
    usernames = [u["username"] for u in users]
    assert "bob" in usernames
    assert "bobby" in usernames
    assert "alice" not in usernames  # Self excluded


# ---------------------------------------------------------------------------
# 14. Search excludes friends
# ---------------------------------------------------------------------------


def test_search_excludes_friends():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")
    _setup_profile(USER_C, "bobby")

    # Make alice and bob friends
    client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )
    reqs = client.get(
        "/friends/requests/incoming",
        headers={"x-user-id": USER_B},
    ).json()["requests"]
    client.post(
        f"/friends/requests/{reqs[0]['id']}/accept",
        headers={"x-user-id": USER_B},
    )

    # Search should exclude bob (already friend) but include bobby
    resp = client.get(
        "/users/search?q=bob",
        headers={"x-user-id": USER_A},
    )
    users = resp.json()["users"]
    usernames = [u["username"] for u in users]
    assert "bob" not in usernames
    assert "bobby" in usernames


# ---------------------------------------------------------------------------
# 15. Get my profile
# ---------------------------------------------------------------------------


def test_get_my_profile():
    _setup_profile(USER_A, "alice", "Alice Wonder")

    resp = client.get("/profile/me", headers={"x-user-id": USER_A})
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert profile["username"] == "alice"
    assert profile["display_name"] == "Alice Wonder"


# ---------------------------------------------------------------------------
# 16. Profile not found
# ---------------------------------------------------------------------------


def test_profile_not_found():
    resp = client.get("/profile/me", headers={"x-user-id": USER_A})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 17. Outgoing requests
# ---------------------------------------------------------------------------


def test_outgoing_requests():
    _setup_profile(USER_A, "alice")
    _setup_profile(USER_B, "bob")

    client.post(
        "/friends/request",
        json={"username": "bob"},
        headers={"x-user-id": USER_A},
    )

    resp = client.get(
        "/friends/requests/outgoing",
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    requests = resp.json()["requests"]
    assert len(requests) == 1
    assert requests[0]["to_profile"]["username"] == "bob"
