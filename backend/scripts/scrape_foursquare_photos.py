#!/usr/bin/env python3
"""
Scrape restaurant photos from Foursquare Places API.
Downloads one photo per restaurant and saves to backend/restaurant_images/.
Reads FOURSQUARE_API_KEY from environment variable.
"""

import json
import os
import sys
import time
import requests

# --- Config ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_DATA_FILE = os.path.join(BASE_DIR, "restaurant_places_data.json")
NAME_MAPPING_FILE = os.path.join(BASE_DIR, "name_mapping.json")
IMAGES_DIR = os.path.join(BASE_DIR, "restaurant_images")
MANIFEST_FILE = os.path.join(BASE_DIR, "restaurant_images_manifest.json")

FSQ_SEARCH_URL = "https://api.foursquare.com/v3/places/search"
FSQ_PHOTOS_URL = "https://api.foursquare.com/v3/places/{fsq_id}/photos"
PHOTO_SIZE = "400x400"
DELAY = 0.1  # seconds between requests


def main():
    api_key = os.environ.get("FOURSQUARE_API_KEY")
    if not api_key:
        print("ERROR: FOURSQUARE_API_KEY environment variable is not set.")
        print("Set it with: export FOURSQUARE_API_KEY=your_key_here")
        sys.exit(1)

    headers = {
        "Authorization": api_key,
        "Accept": "application/json",
    }

    # Load data
    with open(PLACES_DATA_FILE, "r") as f:
        places = json.load(f)
    with open(NAME_MAPPING_FILE, "r") as f:
        name_mapping = json.load(f)

    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Load existing manifest if resuming
    manifest = {}
    if os.path.isfile(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r") as f:
            manifest = json.load(f)

    slugs = sorted(places.keys())
    total = len(slugs)
    downloaded = 0
    skipped = 0
    failed = 0

    for i, slug in enumerate(slugs, 1):
        filename = f"{slug}.jpg"
        filepath = os.path.join(IMAGES_DIR, filename)

        # Skip if already downloaded
        if os.path.isfile(filepath) and slug in manifest:
            skipped += 1
            print(f"[{i}/{total}] {slug}: SKIP (already exists)")
            continue

        place_data = places[slug]
        lat = place_data.get("lat")
        lng = place_data.get("lng")
        display_name = name_mapping.get(slug, slug.replace("-", " ").title())

        if not lat or not lng:
            print(f"[{i}/{total}] {slug}: SKIP (no coordinates)")
            failed += 1
            continue

        try:
            # Step 1: Search for the place
            search_params = {
                "query": display_name,
                "ll": f"{lat},{lng}",
                "radius": 200,
                "limit": 1,
            }
            resp = requests.get(FSQ_SEARCH_URL, headers=headers, params=search_params, timeout=10)
            resp.raise_for_status()
            results = resp.json().get("results", [])

            if not results:
                print(f"[{i}/{total}] {slug}: NO MATCH")
                failed += 1
                time.sleep(DELAY)
                continue

            fsq_id = results[0]["fsq_id"]
            time.sleep(DELAY)

            # Step 2: Get photos
            photos_url = FSQ_PHOTOS_URL.format(fsq_id=fsq_id)
            resp = requests.get(photos_url, headers=headers, params={"limit": 1}, timeout=10)
            resp.raise_for_status()
            photos = resp.json()

            if not photos:
                print(f"[{i}/{total}] {slug}: NO PHOTOS")
                failed += 1
                time.sleep(DELAY)
                continue

            photo = photos[0]
            photo_url = f"{photo['prefix']}{PHOTO_SIZE}{photo['suffix']}"
            time.sleep(DELAY)

            # Step 3: Download image
            img_resp = requests.get(photo_url, timeout=15)
            img_resp.raise_for_status()

            with open(filepath, "wb") as f:
                f.write(img_resp.content)

            manifest[slug] = filename
            downloaded += 1
            print(f"[{i}/{total}] {slug}: OK ({len(img_resp.content) // 1024}KB)")

            # Save manifest periodically (every 20 downloads)
            if downloaded % 20 == 0:
                with open(MANIFEST_FILE, "w") as f:
                    json.dump(manifest, f, indent=2)

        except Exception as e:
            print(f"[{i}/{total}] {slug}: ERROR - {e}")
            failed += 1

        time.sleep(DELAY)

    # Final manifest save
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*50}")
    print(f"DONE: {downloaded} downloaded, {skipped} skipped, {failed} failed")
    print(f"Total in manifest: {len(manifest)}/{total}")
    print(f"Images dir: {IMAGES_DIR}")
    print(f"Manifest: {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
