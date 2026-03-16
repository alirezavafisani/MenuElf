#!/usr/bin/env python3
"""Fix restaurant slug names using name_mapping.json and auto-fix heuristics."""

import json
import os
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
MENUS_DIR = BACKEND_DIR / "menus"
NAME_MAPPING_FILE = BACKEND_DIR / "name_mapping.json"

# Common abbreviation fixes for title-casing
ABBREVIATIONS = {
    "Bbq": "BBQ",
    "Nyc": "NYC",
    "Yyc": "YYC",
    "Nw": "NW",
    "Ne": "NE",
    "Sw": "SW",
    "Se": "SE",
    "Ii": "II",
    "Iii": "III",
    "Tv": "TV",
    "Dq": "DQ",
    "Kfc": "KFC",
    "Bk": "BK",
}

# Word-splitting patterns: insert space before uppercase in camelCase-like slugs
# e.g., "goodearthcoffeehouse" → need word boundaries
# Common compound words to split
COMPOUND_SPLITS = {
    "coffeehouse": "Coffee House",
    "pizzahouse": "Pizza House",
    "sportsbar": "Sports Bar",
    "steakhouse": "Steak House",
    "foodtruck": "Food Truck",
    "icecream": "Ice Cream",
    "seafood": "Seafood",
    "takeout": "Takeout",
    "hotdog": "Hot Dog",
    "chophouse": "Chop House",
    "brewpub": "Brew Pub",
    "brewhouse": "Brew House",
    "firehouse": "Fire House",
    "smokehouse": "Smoke House",
    "bakehouse": "Bake House",
    "farmhouse": "Farm House",
    "alehouse": "Ale House",
    "roadhouse": "Road House",
    "teahouse": "Tea House",
    "taphouse": "Tap House",
    "penthouse": "Penthouse",
    "warehouse": "Warehouse",
    "glasshouse": "Glass House",
    "gatehouse": "Gate House",
    "powerhouse": "Powerhouse",
}


def is_slug(name: str) -> bool:
    """Check if a restaurant name looks like a URL slug."""
    if not name:
        return False
    if name == name.lower() and " " not in name:
        return True
    return False


def auto_fix_slug(slug: str) -> str:
    """Attempt to auto-fix a slug into a readable name."""
    name = slug

    # Replace hyphens and underscores with spaces
    name = name.replace("-", " ").replace("_", " ")

    # Remove trailing numbers that look like duplicates (e.g., "appnatiffin0")
    name = re.sub(r"\s*\d+$", "", name) if re.search(r"[a-z]\d+$", name) else name

    # Title case
    name = name.title()

    # Fix common abbreviations
    for wrong, right in ABBREVIATIONS.items():
        name = re.sub(r"\b" + wrong + r"\b", right, name)

    # Strip trailing/leading whitespace
    name = name.strip()

    # Remove "Website" suffix (from scraping artifacts)
    name = re.sub(r"\s+Website$", "", name)

    return name


def fix_names():
    # Load existing name mapping
    with open(NAME_MAPPING_FILE) as f:
        name_mapping = json.load(f)

    changes = []
    new_mappings = 0

    for fname in sorted(os.listdir(MENUS_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue

        filepath = MENUS_DIR / fname
        with open(filepath) as f:
            data = json.load(f)

        rest_name = data.get("restaurant", "")
        if not is_slug(rest_name):
            continue

        # Check if name_mapping has a clean version
        if rest_name in name_mapping:
            clean_name = name_mapping[rest_name]
            # Check if the mapping itself still looks like a slug
            if is_slug(clean_name):
                clean_name = auto_fix_slug(clean_name)
                name_mapping[rest_name] = clean_name
                new_mappings += 1
        else:
            # Auto-fix
            clean_name = auto_fix_slug(rest_name)
            name_mapping[rest_name] = clean_name
            new_mappings += 1

        changes.append(f"  {rest_name} → {name_mapping[rest_name]}")

    # Save updated name mapping
    with open(NAME_MAPPING_FILE, "w") as f:
        json.dump(name_mapping, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Name fixes: {len(changes)} restaurants checked")
    print(f"New/updated mappings added: {new_mappings}")
    print()
    if changes:
        print("All mappings:")
        for c in changes:
            print(c)


if __name__ == "__main__":
    fix_names()
