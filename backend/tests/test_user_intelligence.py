"""Tests for the user intelligence system.

Run with:
    python -m pytest backend/tests/test_user_intelligence.py -v
"""

import sys
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Mock Supabase before importing the app so the router's lazy init never
# fires against a real database.
# ---------------------------------------------------------------------------

# In-memory stores keyed by table name
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
    """Chainable fake that mimics supabase-py's query builder."""

    def __init__(self, table_name: str):
        self._table = table_name
        self._filters: list = []
        self._order_col = None
        self._order_desc = False
        self._mode = None  # select / insert / upsert / delete
        self._columns = "*"
        self._payload = None

    # ── query starters ──

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

    # ── filters ──

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    # ── execute ──

    def execute(self):
        rows = _tables.setdefault(self._table, [])

        if self._mode == "select":
            matched = self._apply_filters(rows)
            if self._order_col:
                matched.sort(key=lambda r: r.get(self._order_col, ""), reverse=self._order_desc)
            return _FakeResult(matched)

        if self._mode == "insert":
            row = dict(self._payload)
            # Auto-generate id if missing
            if "id" not in row or row["id"] is None:
                row["id"] = str(uuid.uuid4())
            # Check unique constraints for saved_dishes
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
            # Remove existing row with same id, then insert
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


# Patch environment and supabase client before importing app
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# We need to patch the supabase client in the router module
import routers.user_intelligence as _router_mod
_router_mod._supabase_client = _FakeSupabase()

# Now import the app
from main import app

client = TestClient(app)

USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_tables():
    _reset_tables()
    yield
    _reset_tables()


def _onboarding_all_a():
    """All 5 answers choosing option A (spicy/adventurous)."""
    return {
        "answers": [
            {"question_index": i, "chosen_option": "a"}
            for i in range(1, 6)
        ]
    }


def _onboarding_all_b():
    """All 5 answers choosing option B (comfort/mild)."""
    return {
        "answers": [
            {"question_index": i, "chosen_option": "b"}
            for i in range(1, 6)
        ]
    }


def _onboarding_mixed():
    """Mix of A and B answers."""
    return {
        "answers": [
            {"question_index": 1, "chosen_option": "a"},
            {"question_index": 2, "chosen_option": "b"},
            {"question_index": 3, "chosen_option": "a"},
            {"question_index": 4, "chosen_option": "b"},
            {"question_index": 5, "chosen_option": "a"},
        ]
    }


# ---------------------------------------------------------------------------
# 1. Onboarding – spicy/adventurous user
# ---------------------------------------------------------------------------

def test_onboarding_spicy_adventurous():
    resp = client.post(
        "/onboarding/complete",
        json=_onboarding_all_a(),
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert profile["spice_tolerance"] >= 0.65
    assert profile["adventurousness"] >= 0.65


# ---------------------------------------------------------------------------
# 2. Onboarding – comfort/mild user
# ---------------------------------------------------------------------------

def test_onboarding_comfort_mild():
    resp = client.post(
        "/onboarding/complete",
        json=_onboarding_all_b(),
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert profile["spice_tolerance"] < 0.4


# ---------------------------------------------------------------------------
# 3. Onboarding – mixed user
# ---------------------------------------------------------------------------

def test_onboarding_mixed():
    resp = client.post(
        "/onboarding/complete",
        json=_onboarding_mixed(),
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert 0.4 <= profile["spice_tolerance"] <= 0.6
    assert 0.4 <= profile["adventurousness"] <= 0.6


# ---------------------------------------------------------------------------
# 4. Interaction logging – 5 different types
# ---------------------------------------------------------------------------

def test_interaction_logging():
    types_and_payloads = [
        ("chat_message", {"restaurant_slug": "test-rest", "message": "hi", "role": "user"}),
        ("dish_view", {"dish_name": "Pad Thai", "restaurant_slug": "test-rest"}),
        ("dish_save", {"dish_name": "Ramen", "restaurant_slug": "ramen-shop", "price": 15.0}),
        ("search_query", {"query": "spicy noodles", "results_count": 5}),
        ("filter_apply", {"filter_type": "price", "value": "under_20"}),
    ]
    for itype, payload in types_and_payloads:
        resp = client.post(
            "/interactions/log",
            json={"interaction_type": itype, "payload": payload},
            headers={"x-user-id": USER_A},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    # Verify all 5 stored (plus none from other tests due to autouse fixture)
    stored = _tables["interaction_logs"]
    user_logs = [r for r in stored if r["user_id"] == USER_A]
    assert len(user_logs) == 5
    stored_types = {r["interaction_type"] for r in user_logs}
    assert stored_types == {"chat_message", "dish_view", "dish_save", "search_query", "filter_apply"}


# ---------------------------------------------------------------------------
# 5. Saved dishes CRUD
# ---------------------------------------------------------------------------

def test_saved_dishes_crud():
    # Save
    resp = client.post(
        "/dishes/save",
        json={
            "dish_name": "Spicy Ramen",
            "restaurant_slug": "ramen-shop",
            "restaurant_name": "Ramen Shop",
            "price": 18.5,
            "category": "Food",
            "dietary_info": ["spicy"],
            "notes": "Extra spicy please",
        },
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 200
    dish = resp.json()["dish"]
    dish_id = dish["id"]
    assert dish["dish_name"] == "Spicy Ramen"
    assert dish["price"] == 18.5

    # Retrieve
    resp = client.get("/dishes/saved", headers={"x-user-id": USER_A})
    assert resp.status_code == 200
    dishes = resp.json()["dishes"]
    assert len(dishes) == 1
    assert dishes[0]["dish_name"] == "Spicy Ramen"
    assert dishes[0]["notes"] == "Extra spicy please"

    # Delete
    resp = client.delete(f"/dishes/save/{dish_id}", headers={"x-user-id": USER_A})
    assert resp.status_code == 200

    # Verify gone
    resp = client.get("/dishes/saved", headers={"x-user-id": USER_A})
    assert resp.status_code == 200
    assert len(resp.json()["dishes"]) == 0


# ---------------------------------------------------------------------------
# 6. Saved dishes uniqueness
# ---------------------------------------------------------------------------

def test_saved_dishes_uniqueness():
    dish_data = {
        "dish_name": "Pad Thai",
        "restaurant_slug": "thai-place",
        "restaurant_name": "Thai Place",
        "price": 14.0,
    }
    resp = client.post("/dishes/save", json=dish_data, headers={"x-user-id": USER_A})
    assert resp.status_code == 200

    # Duplicate should fail
    resp = client.post("/dishes/save", json=dish_data, headers={"x-user-id": USER_A})
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 7. Taste profile retrieval
# ---------------------------------------------------------------------------

def test_taste_profile_retrieval():
    # Create via onboarding
    client.post(
        "/onboarding/complete",
        json=_onboarding_all_a(),
        headers={"x-user-id": USER_A},
    )

    # Read back
    resp = client.get("/profile/taste", headers={"x-user-id": USER_A})
    assert resp.status_code == 200
    profile = resp.json()
    assert profile["id"] == USER_A
    assert profile["onboarding_completed"] is True
    assert profile["spice_tolerance"] >= 0.65


# ---------------------------------------------------------------------------
# 8. Taste profile isolation
# ---------------------------------------------------------------------------

def test_taste_profile_isolation():
    # Create profiles for both users
    client.post("/onboarding/complete", json=_onboarding_all_a(), headers={"x-user-id": USER_A})
    client.post("/onboarding/complete", json=_onboarding_all_b(), headers={"x-user-id": USER_B})

    # User A should get their own profile
    resp_a = client.get("/profile/taste", headers={"x-user-id": USER_A})
    assert resp_a.status_code == 200
    assert resp_a.json()["id"] == USER_A
    assert resp_a.json()["spice_tolerance"] >= 0.65

    # User B should get their own profile
    resp_b = client.get("/profile/taste", headers={"x-user-id": USER_B})
    assert resp_b.status_code == 200
    assert resp_b.json()["id"] == USER_B
    assert resp_b.json()["spice_tolerance"] < 0.4


# ---------------------------------------------------------------------------
# 9. Interaction log isolation
# ---------------------------------------------------------------------------

def test_interaction_log_isolation():
    # Log for user A
    client.post(
        "/interactions/log",
        json={"interaction_type": "dish_view", "payload": {"dish_name": "Ramen"}},
        headers={"x-user-id": USER_A},
    )
    # Log for user B
    client.post(
        "/interactions/log",
        json={"interaction_type": "dish_view", "payload": {"dish_name": "Pizza"}},
        headers={"x-user-id": USER_B},
    )

    # Verify isolation via in-memory store
    a_logs = [r for r in _tables["interaction_logs"] if r["user_id"] == USER_A]
    b_logs = [r for r in _tables["interaction_logs"] if r["user_id"] == USER_B]
    assert len(a_logs) == 1
    assert len(b_logs) == 1
    assert a_logs[0]["payload"]["dish_name"] == "Ramen"
    assert b_logs[0]["payload"]["dish_name"] == "Pizza"


# ---------------------------------------------------------------------------
# 10. Edge case – empty / missing onboarding answers
# ---------------------------------------------------------------------------

def test_onboarding_empty_answers():
    # No answers at all
    resp = client.post(
        "/onboarding/complete",
        json={"answers": []},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 422  # Pydantic validation error (min_length=5)


def test_onboarding_partial_answers():
    # Only 3 answers
    resp = client.post(
        "/onboarding/complete",
        json={"answers": [
            {"question_index": 1, "chosen_option": "a"},
            {"question_index": 2, "chosen_option": "b"},
            {"question_index": 3, "chosen_option": "a"},
        ]},
        headers={"x-user-id": USER_A},
    )
    assert resp.status_code == 422  # Pydantic validation error (min_length=5)


# ---------------------------------------------------------------------------
# Verify existing endpoints still work
# ---------------------------------------------------------------------------

def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_filter_options_endpoint():
    resp = client.get("/filter-options")
    assert resp.status_code == 200
    assert "categories" in resp.json()
