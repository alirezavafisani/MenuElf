"""The dish is the product, so these are the tests that matter.

Three things are covered here. Drinks must never be returned as a main course,
which was a real bug found on the live site. Distance has to be right, because
sorting by it is now the reason someone picks one restaurant over another. And
every dish row has to carry its own restaurant, since that is what makes a
single result shareable as a link.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# main.py reads these at import time and never makes a network call in these
# tests, so dummy values are enough.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-dummy")

import main
from main import haversine_km, matches_dish_type, _restaurant_context


# ─── Drinks are never mains ───

DRINKS_THAT_WERE_SERVED_AS_MAINS = [
    ({"name": "Van Gogh Double Espresso -", "category": "Food"}, "espresso under a food category"),
    ({"name": "Johnny Walker Black", "category": "Scotch & Whiskey"}, "brand name, spirit in the category"),
    ({"name": "Hendricks", "category": "Drink"}, "brand name, generic drink category"),
    ({"name": "Corona Cero 0.0", "category": "Non-Alcoholic Beer"}, "non alcoholic beer"),
    ({"name": "Gin Gin Mule", "category": "Food"}, "spirit in the name, food category"),
    ({"name": "Espresso Martini", "category": "Cocktails"}, "cocktail"),
]

REAL_FOOD = [
    ({"name": "Almond Chicken (Soo Gai)", "category": "Chicken"}, "a plain main"),
    ({"name": "Spicy Miso Ramen", "category": "Food"}, "a noodle main"),
    ({"name": "Peppered Assorted Meats", "category": "Food"}, "a generic food category"),
]

# "chai" and "matcha" are deliberately absent from the keyword lists, because
# they name cakes as often as they name drinks. Dropping a chai cheesecake out
# of the food index would be a worse bug than the one being fixed.
FOOD_THAT_SOUNDS_LIKE_A_DRINK = [
    ({"name": "Chai Spiced Cheesecake", "category": "Dessert"}, "chai names a cake too"),
    ({"name": "Matcha Tiramisu", "category": "Dessert"}, "matcha names a cake too"),
]


@pytest.mark.parametrize("dish,why", DRINKS_THAT_WERE_SERVED_AS_MAINS)
def test_drinks_are_never_mains(dish, why):
    assert matches_dish_type(dish, "main") is False, f"{dish['name']} came back as a main ({why})"


@pytest.mark.parametrize("dish,why", REAL_FOOD)
def test_real_food_still_counts_as_a_main(dish, why):
    assert matches_dish_type(dish, "main") is True, f"{dish['name']} stopped being a main ({why})"


@pytest.mark.parametrize("dish,why", FOOD_THAT_SOUNDS_LIKE_A_DRINK)
def test_desserts_named_after_drinks_survive(dish, why):
    assert matches_dish_type(dish, "dessert") is True, f"{dish['name']} was dropped as a drink ({why})"


def test_a_drink_still_resolves_as_a_drink():
    assert matches_dish_type({"name": "Van Gogh Double Espresso -", "category": "Food"}, "drink") is True


# ─── Distance ───

# Real Calgary coordinates, so a wrong formula shows up as a wrong number of
# kilometres rather than a plausible looking float.
DOWNTOWN = (51.0447, -114.0719)
UNIVERSITY_OF_CALGARY = (51.0786, -114.1319)


def test_distance_to_self_is_zero():
    assert haversine_km(*DOWNTOWN, *DOWNTOWN) == pytest.approx(0.0, abs=1e-9)


def test_downtown_to_campus_is_about_six_kilometres():
    d = haversine_km(*DOWNTOWN, *UNIVERSITY_OF_CALGARY)
    assert 5.0 < d < 7.0, f"expected roughly 6 km, got {d}"


def test_distance_is_symmetric():
    there = haversine_km(*DOWNTOWN, *UNIVERSITY_OF_CALGARY)
    back = haversine_km(*UNIVERSITY_OF_CALGARY, *DOWNTOWN)
    assert there == pytest.approx(back)


# ─── Every dish carries its own restaurant ───

def test_restaurant_context_carries_name_address_and_directions(monkeypatch):
    monkeypatch.setitem(main.NAME_MAPPING, "shiki-menya", "Shiki Menya")
    monkeypatch.setitem(
        main.PLACES_DATA,
        "shiki-menya",
        {"address": "1601 Centre St N", "lat": 51.0655, "lng": -114.0625},
    )

    ctx = _restaurant_context("shiki-menya")

    assert ctx["restaurant"] == "Shiki Menya"
    assert ctx["address"] == "1601 Centre St N"
    assert "google.com/maps/dir" in ctx["directions_url"]
    assert "51.0655,-114.0625" in ctx["directions_url"]


def test_restaurant_context_without_coordinates_has_no_directions(monkeypatch):
    monkeypatch.setitem(main.PLACES_DATA, "no-geo", {"address": "Somewhere"})
    ctx = _restaurant_context("no-geo")
    assert "directions_url" not in ctx


def test_restaurant_context_is_empty_for_a_missing_slug():
    assert _restaurant_context(None) == {}
