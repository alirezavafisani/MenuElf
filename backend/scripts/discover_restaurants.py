#!/usr/bin/env python3
"""Discover restaurants in Calgary via Google Places API."""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

API_KEY = "AIzaSyAlNXWy4c6rHFcnPPxMsMwscOm2yRcf9Cw"
MENUS_DIR = Path(__file__).parent.parent / "menus"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "discovered_restaurants.json"

SEARCH_QUERIES = [
    "restaurants Calgary downtown",
    "restaurants Calgary Kensington",
    "restaurants Calgary 17th ave",
    "restaurants Calgary Inglewood",
    "restaurants Calgary Beltline",
    "restaurants Calgary Mission",
    "restaurants Calgary Marda Loop",
    "Thai restaurant Calgary",
    "Japanese restaurant Calgary",
    "Indian restaurant Calgary",
    "Italian restaurant Calgary",
    "Mexican restaurant Calgary",
    "Korean restaurant Calgary",
    "Vietnamese restaurant Calgary",
    "Chinese restaurant Calgary",
    "Ethiopian restaurant Calgary",
    "Steakhouse Calgary",
    "Sushi Calgary",
    "Brunch Calgary",
    "Fine dining Calgary",
]


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def get_existing_restaurants() -> set:
    """Get normalized names of existing restaurants."""
    names = set()
    for f in MENUS_DIR.glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text())
            rname = data.get("restaurant", f.stem)
            names.add(normalize_name(rname))
        except Exception:
            names.add(normalize_name(f.stem))
    return names


def search_places(query: str) -> list:
    """Search Google Places API Text Search."""
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json?" + urlencode(
        {"query": query, "key": API_KEY}
    )
    resp = urlopen(url)
    data = json.loads(resp.read())
    results = []
    for r in data.get("results", []):
        if "restaurant" in r.get("types", []) or "food" in r.get("types", []) or "meal_takeaway" in r.get("types", []):
            results.append(
                {
                    "name": r.get("name", ""),
                    "place_id": r.get("place_id", ""),
                    "address": r.get("formatted_address", ""),
                    "lat": r.get("geometry", {}).get("location", {}).get("lat"),
                    "lng": r.get("geometry", {}).get("location", {}).get("lng"),
                    "rating": r.get("rating"),
                    "price_level": r.get("price_level"),
                }
            )
    return results


def get_place_details(place_id: str) -> str | None:
    """Get website URL from place details."""
    url = "https://maps.googleapis.com/maps/api/place/details/json?" + urlencode(
        {"place_id": place_id, "fields": "website", "key": API_KEY}
    )
    try:
        resp = urlopen(url)
        data = json.loads(resp.read())
        return data.get("result", {}).get("website")
    except Exception:
        return None


def main():
    existing = get_existing_restaurants()
    print(f"Existing restaurants in database: {len(existing)}")

    # Collect all results, deduplicate by place_id
    all_places = {}
    for i, query in enumerate(SEARCH_QUERIES):
        print(f"Searching [{i+1}/{len(SEARCH_QUERIES)}]: {query}")
        try:
            results = search_places(query)
            for r in results:
                pid = r["place_id"]
                if pid not in all_places:
                    all_places[pid] = r
            print(f"  Found {len(results)} restaurants ({len(all_places)} unique total)")
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(2)  # Rate limit

    print(f"\nTotal unique restaurants found: {len(all_places)}")

    # Get website URLs for all places
    print("\nFetching website URLs...")
    for i, (pid, place) in enumerate(all_places.items()):
        if i % 20 == 0 and i > 0:
            print(f"  Progress: {i}/{len(all_places)}")
        place["website"] = get_place_details(pid)
        time.sleep(0.5)  # Rate limit for details

    # Compare against existing
    new_count = 0
    already_count = 0
    output = []
    new_names = []

    for place in sorted(all_places.values(), key=lambda x: x["name"]):
        norm = normalize_name(place["name"])
        if norm in existing:
            status = "already_have"
            already_count += 1
        else:
            status = "new"
            new_count += 1
            new_names.append(place["name"])

        output.append(
            {
                "name": place["name"],
                "slug": slugify(place["name"]),
                "place_id": place["place_id"],
                "address": place["address"],
                "lat": place["lat"],
                "lng": place["lng"],
                "rating": place["rating"],
                "price_level": place["price_level"],
                "website": place["website"],
                "status": status,
            }
        )

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))

    # Print summary
    print("\n" + "=" * 60)
    print("DISCOVERY SUMMARY")
    print("=" * 60)
    print(f"Total unique restaurants found: {len(output)}")
    print(f"Already in database:            {already_count}")
    print(f"NEW restaurants not in database: {new_count}")
    print()
    print("NEW RESTAURANT NAMES:")
    print("-" * 60)
    for name in sorted(new_names):
        print(f"  - {name}")
    print("=" * 60)
    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
