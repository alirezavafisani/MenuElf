#!/usr/bin/env python3
"""Discover restaurants in Calgary via Google Places API (v1)."""

import json
import os
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

API_KEY = os.environ.get(
    "GOOGLE_PLACES_API_KEY", "AIzaSyAlNXWy4c6rHFcnPPxMsMwscOm2yRcf9Cw"
)
MENUS_DIR = Path(__file__).parent.parent / "menus"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "discovered_restaurants.json"

FIELD_MASK = ",".join(
    [
        "places.displayName",
        "places.id",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.priceLevel",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.types",
        "nextPageToken",
    ]
)

MAX_RESULTS_PER_PAGE = 20  # API max for v1 searchText
MAX_PAGES_PER_QUERY = 3

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

PRICE_MAP = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


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


def _api_post(url: str, body: dict, headers: dict) -> dict:
    """Make a POST request and return parsed JSON."""
    req = Request(
        url,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    resp = urlopen(req)
    return json.loads(resp.read())


def _parse_place(p: dict) -> dict:
    """Parse a single place from Places API v1 response."""
    display = p.get("displayName", {})
    loc = p.get("location", {})
    return {
        "name": display.get("text", ""),
        "place_id": p.get("id", ""),
        "address": p.get("formattedAddress", ""),
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
        "rating": p.get("rating"),
        "price_level": PRICE_MAP.get(p.get("priceLevel")),
        "website": p.get("websiteUri"),
        "phone": p.get("nationalPhoneNumber"),
        "types": p.get("types", []),
    }


def search_places(query: str) -> list:
    """Search Google Places Text Search v1 with pagination."""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    all_results = []
    body = {"textQuery": query, "maxResultCount": MAX_RESULTS_PER_PAGE}

    for page in range(MAX_PAGES_PER_QUERY):
        try:
            data = _api_post(url, body, headers)
        except Exception as e:
            print(f"    Page {page+1} error: {e}")
            break

        places = data.get("places", [])
        food_types = {
            "restaurant", "food", "meal_takeaway", "meal_delivery",
            "cafe", "bar",
        }
        for p in places:
            types = set(p.get("types", []))
            if types & food_types:
                all_results.append(_parse_place(p))

        next_token = data.get("nextPageToken")
        if not next_token:
            break

        time.sleep(2)
        body = {
            "textQuery": query,
            "maxResultCount": MAX_RESULTS_PER_PAGE,
            "pageToken": next_token,
        }

    return all_results


def main():
    existing = get_existing_restaurants()
    print(f"Existing restaurants in database: {len(existing)}")
    print(f"Using API key: {API_KEY[:12]}...{API_KEY[-4:]}")

    # Collect all results, deduplicate by place_id
    all_places = {}
    for i, query in enumerate(SEARCH_QUERIES):
        print(f"Searching [{i+1}/{len(SEARCH_QUERIES)}]: {query}")
        try:
            results = search_places(query)
            new_in_batch = sum(
                1 for r in results if r["place_id"] not in all_places
            )
            for r in results:
                pid = r["place_id"]
                if pid not in all_places:
                    all_places[pid] = r
            print(
                f"  Found {len(results)} results, {new_in_batch} new "
                f"({len(all_places)} unique total)"
            )
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(2)  # Rate limit between queries

    print(f"\nTotal unique restaurants found: {len(all_places)}")

    # Classify new vs already_have
    new_pids = []
    already_pids = []
    for pid, place in all_places.items():
        norm = normalize_name(place["name"])
        if norm in existing:
            already_pids.append(pid)
        else:
            new_pids.append(pid)

    print(f"Already in database: {len(already_pids)}")
    print(f"NEW restaurants: {len(new_pids)}")

    # Build output
    output = []
    new_names = []

    for place in sorted(all_places.values(), key=lambda x: x["name"]):
        norm = normalize_name(place["name"])
        if norm in existing:
            status = "already_have"
        else:
            status = "new"
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
                "website": place.get("website"),
                "phone": place.get("phone"),
                "types": place.get("types", []),
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
    print(f"Already in database:            {len(already_pids)}")
    print(f"NEW restaurants not in database: {len(new_pids)}")
    print()
    print("NEW RESTAURANT NAMES:")
    print("-" * 60)
    for name in sorted(new_names):
        print(f"  - {name}")
    print("=" * 60)
    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
