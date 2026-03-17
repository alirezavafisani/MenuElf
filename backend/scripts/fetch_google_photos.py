#!/usr/bin/env python3
"""
Fetch Google Places photo references for all restaurants.

Usage:
    GOOGLE_MAPS_API_KEY=<key> python backend/scripts/fetch_google_photos.py

Reads restaurant_places_data.json (which has lat/lng/address per slug),
uses Google Places Find Place from Text API to locate each restaurant
and retrieve photo references, then saves results to restaurant_photos.json.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DATA_FILE = os.path.join(BASE_DIR, "restaurant_places_data.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "restaurant_photos.json")
MAX_PHOTOS = 3
DELAY_BETWEEN_REQUESTS = 0.1


def fetch_photos_for_restaurant(name: str, slug: str, place_data: dict, api_key: str) -> dict | None:
    """Use Find Place from Text API to get place_id and photos in one call."""
    lat = place_data.get("lat")
    lng = place_data.get("lng")
    address = place_data.get("address", "")

    # Build search query from restaurant name + city
    query = f"{name} Calgary"
    if address:
        query = f"{name} {address}"

    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id,photos",
        "key": api_key,
    }
    if lat and lng:
        params["locationbias"] = f"point:{lat},{lng}"

    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"HTTP error: {e}")

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
        photos.append({
            "photo_reference": photo.get("photo_reference", ""),
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

    if not os.path.isfile(PLACES_DATA_FILE):
        print(f"ERROR: {PLACES_DATA_FILE} not found.", file=sys.stderr)
        sys.exit(1)

    with open(PLACES_DATA_FILE, "r", encoding="utf-8") as f:
        places_data = json.load(f)

    print(f"Loaded {len(places_data)} restaurants from places data.", flush=True)

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

    for i, (slug, pdata) in enumerate(places_data.items(), 1):
        display_name = slug.replace("-", " ").replace("_", " ").title()

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
            result = fetch_photos_for_restaurant(display_name, slug, pdata, api_key)
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
