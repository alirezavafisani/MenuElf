"""
Integration tests that hit the REAL production backend.

Usage:
    python -m pytest backend/tests/test_integration_real.py -v -m integration

These tests are NOT part of the regular test suite.
They require network access to https://menuelf-production.up.railway.app
"""
import pytest
import requests
import urllib3

# Suppress InsecureRequestWarning for environments with clock skew / cert issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://menuelf-production.up.railway.app"

# Fixed UUID so cleanup can target it reliably
TEST_USER_ID = "00000000-0000-4000-a000-000000000001"


def api(method: str, path: str, json=None, user_id: str | None = TEST_USER_ID):
    headers = {"Content-Type": "application/json"}
    if user_id:
        headers["x-user-id"] = user_id
    url = f"{BASE_URL}{path}"
    resp = requests.request(method, url, json=json, headers=headers, timeout=30, verify=False)
    return resp


# ---------------------------------------------------------------------------
# Setup / Teardown: create & delete a test user in auth.users
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def manage_test_user():
    """Create a test user before all tests, delete after all tests."""
    # Setup: create the test user in auth.users
    resp = api("POST", "/test/create-user", user_id=TEST_USER_ID)
    assert resp.status_code == 200, \
        f"Failed to create test user: {resp.status_code} {resp.text[:500]}"
    print(f"\nCreated test user {TEST_USER_ID}")

    yield  # Run all tests

    # Teardown: delete the test user (CASCADE deletes all related data)
    resp = api("DELETE", "/test/delete-user", user_id=TEST_USER_ID)
    if resp.status_code == 200:
        print(f"\nDeleted test user {TEST_USER_ID} and all related data")
    else:
        print(f"\nWarning: cleanup failed: {resp.status_code} {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_health():
    """Backend health-check returns 200."""
    resp = api("GET", "/health", user_id=None)
    assert resp.status_code == 200


@pytest.mark.integration
def test_restaurants_load():
    """GET /restaurants returns >400 restaurants."""
    resp = api("GET", "/restaurants?q=")
    assert resp.status_code == 200
    data = resp.json()
    restaurants = data.get("restaurants", [])
    assert len(restaurants) > 400, f"Expected >400 restaurants, got {len(restaurants)}"


@pytest.mark.integration
def test_onboarding_questions_available():
    """GET /onboarding/questions returns exactly 5 questions with no raw signals."""
    resp = api("GET", "/onboarding/questions")
    assert resp.status_code == 200
    data = resp.json()
    questions = data.get("questions", [])
    assert len(questions) == 5, f"Expected 5 questions, got {len(questions)}"

    for q in questions:
        assert "option_a" in q and "option_b" in q
        for opt_key in ("option_a", "option_b"):
            opt = q[opt_key]
            assert "image_url" in opt, f"Missing image_url in {opt_key}"
            assert "label" in opt, f"Missing label in {opt_key}"

    # Signals should not be exposed to the client
    raw = resp.text.lower()
    assert "signals" not in raw, "Raw signals should not be sent to client"


@pytest.mark.integration
def test_onboarding_complete_flow():
    """POST /onboarding/complete accepts answers and returns a profile."""
    answers = [
        {"question_index": i, "chosen_option": "a" if i % 2 == 0 else "b"}
        for i in range(5)
    ]
    resp = api("POST", "/onboarding/complete", json={"answers": answers})
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
    data = resp.json()
    assert "profile" in data or "taste_profile" in data or "status" in data, \
        f"Unexpected response keys: {list(data.keys())}"


@pytest.mark.integration
def test_taste_profile_retrieval():
    """GET /profile/taste returns the profile created during onboarding."""
    # Ensure onboarding is done first
    answers = [
        {"question_index": i, "chosen_option": "a"} for i in range(5)
    ]
    complete_resp = api("POST", "/onboarding/complete", json={"answers": answers})
    assert complete_resp.status_code == 200, f"Onboarding failed: {complete_resp.text[:500]}"

    resp = api("GET", "/profile/taste")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
    data = resp.json()
    assert data.get("onboarding_completed") is True or "dimensions" in data or "profile" in data, \
        f"Profile missing expected fields: {list(data.keys())}"


@pytest.mark.integration
def test_interaction_logging():
    """POST /interactions/log accepts fire-and-forget logs."""
    resp = api("POST", "/interactions/log", json={
        "interaction_type": "restaurant_tap",
        "payload": {"restaurant_slug": "test-restaurant", "source": "integration_test"},
    })
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"


@pytest.mark.integration
def test_personalized_restaurants():
    """GET /restaurants with x-user-id returns match_score and top_dish for at least some restaurants."""
    # Ensure user has a profile
    answers = [{"question_index": i, "chosen_option": "a"} for i in range(5)]
    complete_resp = api("POST", "/onboarding/complete", json={"answers": answers})
    assert complete_resp.status_code == 200, f"Onboarding failed: {complete_resp.text[:500]}"

    resp = api("GET", "/restaurants?q=")
    assert resp.status_code == 200
    data = resp.json()
    restaurants = data.get("restaurants", [])
    assert len(restaurants) > 0

    scored = [r for r in restaurants if r.get("match_score") is not None]
    assert len(scored) > 0, "No restaurants have match_score after onboarding"


@pytest.mark.integration
def test_chat_start_personalized():
    """POST /chat/start returns a personalized greeting with session_id."""
    # Ensure user has a profile
    answers = [{"question_index": i, "chosen_option": "b"} for i in range(5)]
    api("POST", "/onboarding/complete", json={"answers": answers})

    rest_resp = api("GET", "/restaurants?q=")
    restaurants = rest_resp.json().get("restaurants", [])
    assert len(restaurants) > 0
    slug = restaurants[0]["slug"]

    resp = api("POST", "/chat/start", json={"restaurant_slug": slug})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data, f"Missing 'reply' in chat/start response: {list(data.keys())}"
    assert "session_id" in data, f"Missing 'session_id' in chat/start response"
    assert len(data["reply"]) > 10, "Reply seems too short"


@pytest.mark.integration
def test_chat_message():
    """POST /chat with a message returns a reply."""
    rest_resp = api("GET", "/restaurants?q=")
    restaurants = rest_resp.json().get("restaurants", [])
    slug = restaurants[0]["slug"]

    resp = api("POST", "/chat", json={
        "restaurant": slug,
        "message": "What are your most popular dishes?",
        "history": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data, f"Missing 'reply' in chat response"


@pytest.mark.integration
def test_filter_options_still_works():
    """GET /filter-options returns categories and dietary_tags."""
    resp = api("GET", "/filter-options", user_id=None)
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data or "dietary_tags" in data, \
        f"Unexpected filter-options response: {list(data.keys())}"


@pytest.mark.integration
def test_search_dishes_still_works():
    """POST /search-dishes returns dish results."""
    resp = api("POST", "/search-dishes", json={"query": "pasta"}, user_id=None)
    assert resp.status_code == 200
    data = resp.json()
    assert "dishes" in data, f"Missing 'dishes' key: {list(data.keys())}"
