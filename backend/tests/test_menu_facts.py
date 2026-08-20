"""Superlatives are arithmetic, so code does them, not the model.

Found live on 2026-08-20 at Sen Vietnamese Kitchen. Three questions in a row,
three wrong answers:

  "Cheapest food here?" -> Spring Rolls at $9.50. A $8.50 dessert was in the list.
  "Cheapest item"       -> $9.50. Soft Drinks were $2.95.
  "No drink?"           -> $2.95, correct, and it contradicted the answer above it.

It also missed that Tea ties Soft Drinks at $2.95. A model reading a JSON blob
does not reliably take a minimum over ninety six rows, and it has no way to
notice it just contradicted itself. These are computed now.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-dummy")

from main import _cheapest, _menu_facts


# Trimmed from the real Sen Vietnamese Kitchen menu, keeping the shape that broke.
SEN = [
    {"name": "Soft Drinks", "price": 2.95, "category": "Drinks"},
    {"name": "Tea", "price": 2.95, "category": "Drinks"},
    {"name": "Juice", "price": 3.95, "category": "Drinks"},
    {"name": "Deep Fried Banana with Ice Cream", "price": 8.50, "category": "Dessert"},
    {"name": "Deep Fried Pork Spring Rolls", "price": 9.50, "category": "Appetizers"},
    {"name": "Shrimp Salad Rolls", "price": 9.50, "category": "Appetizers"},
    {"name": "Spicy Satay Chicken Noodle Soup", "price": 15.50, "category": "Noodle Soup"},
    {"name": "Vermicelli Combo for 4", "price": 56.25, "category": "Vermicelli Combo for 4"},
]


def test_the_cheapest_item_is_the_drink_not_the_spring_rolls():
    """The exact wrong answer. $9.50 was six dollars off."""
    got = _cheapest(SEN)
    assert got["price"] == 2.95
    assert "Deep Fried Pork Spring Rolls" not in got["names"]


def test_a_tie_names_both():
    got = _cheapest(SEN)
    assert set(got["names"]) == {"Soft Drinks", "Tea"}


def test_the_cheapest_food_is_the_dessert_it_skipped():
    facts = _menu_facts(SEN)
    assert "Cheapest food: Deep Fried Banana with Ice Cream at $8.50" in facts


def test_cheapest_item_and_cheapest_drink_cannot_disagree():
    """The contradiction it produced two turns apart, held down in one place."""
    facts = _menu_facts(SEN)
    assert "Cheapest item on the whole menu, food or drink: Soft Drinks, Tea at $2.95" in facts
    assert "Cheapest drink: Soft Drinks, Tea at $2.95" in facts


def test_the_dearest_is_reported():
    assert "Most expensive item: Vermicelli Combo for 4 at $56.25" in _menu_facts(SEN)


def test_items_without_a_price_are_ignored():
    rows = SEN + [{"name": "Market Price Special", "price": None, "category": "Specials"},
                  {"name": "Free Tap Water", "price": 0, "category": "Drinks"}]
    got = _cheapest(rows)
    assert got["price"] == 2.95, "a zero or missing price must not win"


def test_no_prices_means_no_facts():
    assert _menu_facts([{"name": "Something", "category": "Food"}]) == ""
