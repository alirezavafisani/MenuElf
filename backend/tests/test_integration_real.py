"""Integration tests that hit the REAL production backend.

Usage:
    python -m pytest backend/tests/test_integration_real.py -v -m integration

These are NOT part of the regular test suite. They need network access to
https://menuelfapp.com and the `requests` package.

Everything here checks the dish path, because that is now the whole product.
The onboarding, taste profile, friends, group dining and chat tests that used
to live in this file were removed with the endpoints they covered.
"""
import pytest
import requests

BASE_URL = "https://menuelfapp.com"

pytestmark = pytest.mark.integration


def api(method: str, path: str, json=None):
    # Certificate verification stays on. Railway serves a valid certificate, and
    # a test that skips verification would pass against a man in the middle.
    return requests.request(
        method,
        BASE_URL + path,
        json=json,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )


def test_health():
    resp = api("GET", "/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_restaurants_load():
    resp = api("GET", "/restaurants")
    assert resp.status_code == 200
    assert len(resp.json()["restaurants"]) > 100


def test_filter_options_still_works():
    resp = api("GET", "/filter-options")
    assert resp.status_code == 200
    body = resp.json()
    assert body["categories"]
    assert body["dietary_tags"]


def test_search_returns_dishes_with_their_restaurant():
    """Every row has to stand alone, which is what makes it shareable."""
    resp = api("POST", "/search-dishes", json={"query": "pasta"})
    assert resp.status_code == 200
    dishes = resp.json()["dishes"]
    assert dishes, "no dishes came back for pasta"
    assert all(d.get("restaurant") for d in dishes), "a dish came back with no restaurant"
    assert all(d.get("id") for d in dishes), "a dish came back with no id to link to"


def test_price_filter_is_respected():
    resp = api("POST", "/search-dishes", json={"query": "noodles", "price_max": 15})
    assert resp.status_code == 200
    for d in resp.json()["dishes"]:
        price = float(str(d["price"]).replace("$", "").split("-")[0].strip())
        assert price <= 15, f"{d['name']} at {price} came back under a $15 cap"


def test_distance_sort_puts_the_nearest_first():
    """Sorting by distance is what turns a list into a decision."""
    downtown = {"lat": 51.0447, "lng": -114.0719}
    resp = api("POST", "/search-dishes", json={"query": "pizza", "sort": "distance", **downtown})
    assert resp.status_code == 200
    body = resp.json()
    assert body["sort"] == "distance"
    known = [d["distance_km"] for d in body["dishes"] if d.get("distance_km") is not None]
    assert known == sorted(known), "distance sort did not come back in order"


def test_a_dish_can_be_fetched_on_its_own():
    """The share link has to resolve without an account."""
    search = api("POST", "/search-dishes", json={"query": "burger"})
    dishes = search.json()["dishes"]
    assert dishes, "no dishes came back for burger"

    resp = api("GET", f"/dish/{dishes[0]['id']}")
    assert resp.status_code == 200
    dish = resp.json()["dish"]
    assert dish["name"]
    assert dish["restaurant"]


def test_a_missing_dish_is_a_404():
    resp = api("GET", "/dish/definitely-not-a-real-dish-id")
    assert resp.status_code == 404
