#!/usr/bin/env python3
"""Rebuild menu_db.json from cleaned restaurant JSON files.

This rebuilds the flat menu index used for search. It does NOT rebuild
vector embeddings (menu_embeddings.npy) — that requires an OpenAI API key
and should be run on Railway where the key is configured.
"""

import json
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
MENUS_DIR = BACKEND_DIR / "menus"
NAME_MAPPING_FILE = BACKEND_DIR / "name_mapping.json"
MENU_DB_FILE = BACKEND_DIR / "menu_db.json"


def rebuild():
    # Load name mapping
    with open(NAME_MAPPING_FILE) as f:
        name_mapping = json.load(f)

    menu_index = []

    for fname in sorted(os.listdir(MENUS_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue

        with open(MENUS_DIR / fname) as f:
            data = json.load(f)

        slug = data.get("restaurant", fname.replace(".json", ""))
        display_name = name_mapping.get(slug, slug)

        for idx, item in enumerate(data.get("items", [])):
            entry = {
                "id": f"{slug}_{idx}",
                "name": item.get("name", ""),
                "price": item.get("price"),
                "description": item.get("description") or item.get("simplified_description") or "",
                "category": item.get("category", "OTHER"),
                "restaurant_slug": slug,
                "restaurant_name": display_name,
                "dietary_info": item.get("dietary_info", []),
            }
            menu_index.append(entry)

    # Save
    with open(MENU_DB_FILE, "w") as f:
        json.dump(menu_index, f, ensure_ascii=False)

    print(f"Rebuilt menu_db.json: {len(menu_index)} items from {len(set(e['restaurant_slug'] for e in menu_index))} restaurants")


if __name__ == "__main__":
    rebuild()
