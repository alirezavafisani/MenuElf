"""Drinks must never be served as a main.

Found on the live site on 2026-08-09. "Surprise me with a main under $10" returned
"Van Gogh Double Espresso" at $7.75 from Beckham's Pub, and the default feed offered
Johnny Walker Black and Hendricks as dishes.

Two separate holes, both in the same pair of keyword lists.

A pub files its espresso under a food category, so the category list never sees it,
and "espresso" was missing from the name list. That is the first hole.

A bar names only the brand and declares the spirit in the category, so
"Johnny Walker Black" under "Scotch & Whiskey" matched neither list. The name list
cannot fix that without holding every brand on every bar menu in the city, so the
spirit words belong in the category list too. That is the second hole, and it is the
one the first version of this fix missed.

The false-positive cases below matter as much as the failures. "chai" and "matcha"
are deliberately absent from the keyword lists, because they name cakes as often as
they name drinks, and dropping a chai cheesecake out of the food index would be a
worse bug than the one being fixed.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# main.py reads these at import time. The smoke-test workflow sets the same
# dummy values for the same reason: this file tests pure filtering logic and
# never makes a network call.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-dummy")

from main import matches_dish_type


DRINKS_THAT_WERE_SERVED_AS_MAINS = [
    ({"name": "Van Gogh Double Espresso -", "category": "Food"}, "espresso under a food category"),
    ({"name": "Johnny Walker Black", "category": "Scotch & Whiskey"}, "brand name, spirit in the category"),
    ({"name": "Hendricks", "category": "Drink"}, "brand name, generic drink category"),
    ({"name": "Corona Cero 0.0", "category": "Non-Alcoholic Beer"}, "non-alcoholic beer"),
    ({"name": "Gin Gin Mule", "category": "Food"}, "spirit in the name, food category"),
    ({"name": "Espresso Martini", "category": "Cocktails"}, "cocktail"),
]

REAL_FOOD = [
    ({"name": "Almond Chicken (Soo Gai)", "category": "Chicken"}, "a plain main"),
    ({"name": "Spicy Miso Ramen", "category": "Food"}, "a noodle main"),
    ({"name": "Peppered Assorted Meats", "category": "Food"}, "a generic food category"),
]

FOOD_THAT_SOUNDS_LIKE_A_DRINK = [
    ({"name": "Chai Spiced Cheesecake", "category": "Dessert"}, "chai names a cake too"),
    ({"name": "Matcha Tiramisu", "category": "Dessert"}, "matcha names a cake too"),
]


@pytest.mark.parametrize("dish,why", DRINKS_THAT_WERE_SERVED_AS_MAINS, ids=lambda v: v if isinstance(v, str) else "")
def test_drinks_are_never_mains(dish, why):
    assert matches_dish_type(dish, "main") is False, f"{dish['name']} came back as a main ({why})"


@pytest.mark.parametrize("dish,why", REAL_FOOD, ids=lambda v: v if isinstance(v, str) else "")
def test_real_food_still_counts_as_a_main(dish, why):
    assert matches_dish_type(dish, "main") is True, f"{dish['name']} stopped being a main ({why})"


@pytest.mark.parametrize("dish,why", FOOD_THAT_SOUNDS_LIKE_A_DRINK, ids=lambda v: v if isinstance(v, str) else "")
def test_desserts_named_after_drinks_survive(dish, why):
    assert matches_dish_type(dish, "dessert") is True, f"{dish['name']} was dropped as a drink ({why})"


def test_a_drink_still_resolves_as_a_drink():
    espresso = {"name": "Van Gogh Double Espresso -", "category": "Food"}
    assert matches_dish_type(espresso, "drink") is True


def test_desserts_and_sides_stay_out_of_mains():
    assert matches_dish_type({"name": "Kunafa Cheese Cake", "category": "Dessert"}, "main") is False
    assert matches_dish_type({"name": "Chicken Wings", "category": "Appetizers"}, "main") is False
