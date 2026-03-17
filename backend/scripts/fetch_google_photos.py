#!/usr/bin/env python3
"""
Fetch Google Places photo references for all restaurants.

Usage:
    GOOGLE_MAPS_API_KEY=<key> python backend/scripts/fetch_google_photos.py

Reads restaurant_places_data.json (which has lat/lng/address per slug),
uses Google Places API (New) Text Search to locate each restaurant
and retrieve photo references, then saves results to restaurant_photos.json.

The new Places API (v1) is used by default. It returns photo resource names
like "places/ChIJ.../photos/AelY_C..." which the backend converts to URLs.

Requires: requests (pip install requests)
"""

import json
import os
import sys
import time

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DATA_FILE = os.path.join(BASE_DIR, "restaurant_places_data.json")
NAME_MAPPING_FILE = os.path.join(BASE_DIR, "name_mapping.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "restaurant_photos.json")
MAX_PHOTOS = 3
DELAY_BETWEEN_REQUESTS = 0.1


def load_name_mapping() -> dict:
    """Load slug -> display name mapping."""
    if os.path.isfile(NAME_MAPPING_FILE):
        with open(NAME_MAPPING_FILE, "r") as f:
            return json.load(f)
    return {}


def fetch_photos_new_api(name: str, place_data: dict, api_key: str) -> dict | None:
    """Use the new Places API (v1) Text Search to get place id and photos."""
    address = place_data.get("address", "")
    query = f"{name} {address}" if address else f"{name} Calgary"

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.photos",
    }
    body = {"textQuery": query, "maxResultCount": 1}

    lat = place_data.get("lat")
    lng = place_data.get("lng")
    if lat and lng:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 500.0,
            }
        }

    resp = requests.post(url, json=body, headers=headers, timeout=15)
    data = resp.json()

    if resp.status_code != 200:
        error_msg = data.get("error", {}).get("message", resp.text[:200])
        raise RuntimeError(f"API error {resp.status_code}: {error_msg}")

    places = data.get("places", [])
    if not places:
        return None

    place = places[0]
    place_id = place.get("id", "")
    raw_photos = place.get("photos", [])

    photos = []
    for photo in raw_photos[:MAX_PHOTOS]:
        photo_name = photo.get("name", "")
        if photo_name:
            photos.append({
                "photo_reference": photo_name,
                "width": photo.get("widthPx"),
                "height": photo.get("heightPx"),
                "attributions": [a.get("displayName", "") for a in photo.get("authorAttributions", [])],
            })

    if not photos:
        return None

    return {
        "place_id": place_id,
        "photos": photos,
    }


def fetch_photos_legacy_api(name: str, place_data: dict, api_key: str) -> dict | None:
    """Use legacy Places API Find Place from Text to get place_id and photos."""
    address = place_data.get("address", "")
    query = f"{name} {address}" if address else f"{name} Calgary"

    lat = place_data.get("lat")
    lng = place_data.get("lng")

    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id,photos",
        "key": api_key,
    }
    if lat and lng:
        params["locationbias"] = f"point:{lat},{lng}"

    resp = requests.get(
        "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
        params=params,
        timeout=15,
    )
    data = resp.json()

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        raise RuntimeError(f"API status: {data.get('status')} - {data.get('error_message', '')}")

    candidates = data.get("candidates", [])
    if not candidates:
        return None

    candidate = candidates[0]
    place_id = candidate.get("place_id", "")
    raw_photos = candidate.get("photos", [])

    photos = []
    for photo in raw_photos[:MAX_PHOTOS]:
        ref = photo.get("photo_reference", "")
        if ref:
            photos.append({
                "photo_reference": ref,
                "width": photo.get("width"),
                "height": photo.get("height"),
                "attributions": photo.get("html_attributions", []),
            })

    if not photos:
        return None

    return {
        "place_id": place_id,
        "photos": photos,
    }


def main():
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_MAPS_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    use_legacy = os.environ.get("USE_LEGACY_API", "").lower() in ("1", "true", "yes")

    if not os.path.isfile(PLACES_DATA_FILE):
        print(f"ERROR: {PLACES_DATA_FILE} not found.", file=sys.stderr)
        sys.exit(1)

    with open(PLACES_DATA_FILE, "r", encoding="utf-8") as f:
        places_data = json.load(f)

    name_mapping = load_name_mapping()

    api_label = "legacy" if use_legacy else "new (v1)"
    print(f"Loaded {len(places_data)} restaurants from places data.", flush=True)
    print(f"Using {api_label} Places API.", flush=True)

    # Load existing results to allow resuming
    results = {}
    if os.path.isfile(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
        print(f"Loaded {len(results)} existing results (will skip these).", flush=True)

    total = len(places_data)
    success_count = len(results)
    fail_count = 0
    no_photos_count = 0
    skipped_count = 0

    fetch_fn = fetch_photos_legacy_api if use_legacy else fetch_photos_new_api

    for i, (slug, pdata) in enumerate(places_data.items(), 1):
        # Use proper display name from name_mapping if available
        display_name = name_mapping.get(slug, slug.replace("-", " ").replace("_", " ").title())

        # Skip already fetched
        if slug in results:
            skipped_count += 1
            continue

        # Skip entries with errors
        if "error" in pdata:
            no_photos_count += 1
            print(f"  Skipped {i}/{total}: {display_name} (has error in places data)", flush=True)
            continue

        try:
            result = fetch_fn(display_name, pdata, api_key)
            if result:
                results[slug] = result
                success_count += 1
                photo_count = len(result["photos"])
                print(f"  Fetched photos for {i}/{total}: {display_name} ({photo_count} photos)", flush=True)
            else:
                no_photos_count += 1
                print(f"  No photos for {i}/{total}: {display_name}", flush=True)
        except Exception as e:
            fail_count += 1
            print(f"  FAILED {i}/{total}: {display_name} - {e}", flush=True)

        # Rate limiting
        time.sleep(DELAY_BETWEEN_REQUESTS)

        # Save progress every 50 restaurants
        if i % 50 == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
            print(f"  [Progress saved: {len(results)} restaurants]", flush=True)

    # Final save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone. {success_count} restaurants with photos, {fail_count} failed, "
          f"{no_photos_count} had no photos, {skipped_count} skipped (already fetched).", flush=True)
    print(f"Results saved to {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    main()
