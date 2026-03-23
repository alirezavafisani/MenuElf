#!/usr/bin/env python3
"""Fix quick data quality issues in menu JSON files."""

import json
from pathlib import Path

MENUS_DIR = Path(__file__).parent.parent / "menus"

CATEGORY_KEYWORDS = {
    "Appetizers": [
        "soup", "salad", "appetizer", "wings", "nachos", "spring roll", "edamame",
    ],
    "Mains": [
        "burger", "steak", "chicken", "pasta", "curry", "bowl", "sandwich",
        "pizza", "wrap", "taco", "noodle", "rice plate", "entree",
    ],
    "Desserts": [
        "cake", "ice cream", "brownie", "cheesecake", "dessert", "sundae", "pie",
    ],
    "Drinks": [
        "beer", "wine", "cocktail", "coffee", "tea", "juice", "smoothie",
        "latte", "espresso", "soda", "pop",
    ],
    "Sides": [
        "fries", "rice", "bread", "coleslaw", "side",
    ],
}


def guess_category(item: dict) -> str | None:
    """Try to guess category from item name and description."""
    text = (item.get("name", "") + " " + (item.get("description", "") or "")).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return None


def main():
    zero_fixed = 0
    categorized = 0

    for f in sorted(MENUS_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue

        modified = False
        for item in data.get("items", []):
            # Fix zero prices
            if item.get("price") == 0:
                item["price"] = None
                zero_fixed += 1
                modified = True

            # Fix missing category
            if not item.get("category"):
                cat = guess_category(item)
                if cat:
                    item["category"] = cat
                    categorized += 1
                    modified = True

        if modified:
            f.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    print(f"Fixed {zero_fixed} zero prices, categorized {categorized} dishes")


if __name__ == "__main__":
    main()
