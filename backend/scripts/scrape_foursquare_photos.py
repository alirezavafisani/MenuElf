#!/usr/bin/env python3
"""Scrape restaurant photos from Foursquare Places API v3.

Resumable: re-running skips restaurants that already have a photo on disk.
Reads from backend/restaurant_places_data.json (slug -> {name, lat, lng}).
Saves photos to backend/restaurant_images/{slug}/0.jpg.
Writes backend/restaurant_images_manifest.json on completion.

Usage:
    export FOURSQUARE_API_KEY=fsq3...
    cd backend
    python3 scripts/scrape_foursquare_photos.py

If restaurant_places_data.json is missing, fetch it from production:
    curl -s https://menuelfapp.com/restaurants | python3 -c "
    import sys, json
    d = json.load(sys.stdin)
    places = {}
    for r in d['restaurants']:
        if r.get('lat') and r.get('lng') and r.get('slug'):
            places[r['slug']] = {'name': r['name'], 'lat': r['lat'], 'lng': r['lng']}
    with open('restaurant_places_data.json', 'w') as f:
        json.dump(places, f)
    print(f'Saved {len(places)} restaurants')
    "
"""

import json
import os
import sys
import time
import requests

# --- Config ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES_FILE = os.path.join(BASE_DIR, "restaurant_places_data.json")
IMAGES_DIR = os.path.join(BASE_DIR, "restaurant_images")
MANIFEST_FILE = os.path.join(BASE_DIR, "restaurant_images_manifest.json")

FSQ_BASE = "https://api.foursquare.com/v3"
PHOTO_SIZE = "600x400"
SLEEP = 0.2  # seconds between API calls
TIMEOUT = 15


def main():
    api_key = os.environ.get("FOURSQUARE_API_KEY", "").strip()
    if not api_key:
        print("ERROR: FOURSQUARE_API_KEY environment variable is not set.")
        print("Set it with: export FOURSQUARE_API_KEY=fsq3...")
        sys.exit(1)

    headers = {"Authorization": api_key, "Accept": "application/json"}
    session = requests.Session()
    session.headers.update(headers)

    # Load restaurant list
    if not os.path.isfile(PLACES_FILE):
        print(f"ERROR: {PLACES_FILE} not found.")
        print("Fetch it from production -- see docstring for instructions.")
        sys.exit(1)

    with open(PLACES_FILE) as f:
        places = json.load(f)

    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Load existing manifest (for resume)
    manifest = {}
    if os.path.isfile(MANIFEST_FILE):
        with open(MANIFEST_FILE) as f:
            manifest = json.load(f)

    slugs = sorted(places.keys())
    total = len(slugs)
    saved = 0
    skipped = 0
    no_match = 0
    no_photo = 0
    errors = 0

    print(f"Loaded {total} restaurants from {os.path.basename(PLACES_FILE)}")
    print(f"Images dir: {IMAGES_DIR}")
    print(f"Photo size: {PHOTO_SIZE}")
    print(f"Existing manifest entries: {len(manifest)}\n")

    for i, slug in enumerate(slugs, 1):
        dest_dir = os.path.join(IMAGES_DIR, slug)
        dest = os.path.join(dest_dir, "0.jpg")

        # Resume: skip if already downloaded
        if os.path.isfile(dest) and os.path.getsize(dest) > 500:
            if slug not in manifest:
                manifest[slug] = f"{slug}/0.jpg"
            skipped += 1
            if skipped % 50 == 0:
                print(f"[{i}/{total}] (skipped {skipped} existing so far)", flush=True)
            continue

        info = places[slug]
        name = info.get("name", slug.replace("-", " ").title())
        lat = info.get("lat")
        lng = info.get("lng")

        if not lat or not lng:
            print(f"[{i}/{total}] {name} -> NO COORDS")
            errors += 1
            continue

        try:
            # Step 1: Search Foursquare for a match
            r = session.get(
                f"{FSQ_BASE}/places/search",
                params={
                    "query": name,
                    "ll": f"{lat},{lng}",
                    "radius": 300,
                    "limit": 1,
                    "categories": "13065",
                },
                timeout=TIMEOUT,
            )
            time.sleep(SLEEP)

            if r.status_code == 401:
                print("\nERROR: 401 Unauthorized -- check FOURSQUARE_API_KEY")
                sys.exit(1)
            if r.status_code == 429:
                print("\nRate limited on search. Waiting 60s...", flush=True)
                time.sleep(60)
                continue  # will retry on next run (resumable)
            r.raise_for_status()

            results = r.json().get("results", [])
            if not results:
                print(f"[{i}/{total}] {name} -> NO MATCH")
                no_match += 1
                continue

            fsq_id = results[0]["fsq_id"]

            # Step 2: Get photo URL
            r = session.get(
                f"{FSQ_BASE}/places/{fsq_id}/photos",
                params={"limit": 1, "sort": "POPULAR"},
                timeout=TIMEOUT,
            )
            time.sleep(SLEEP)

            if r.status_code == 429:
                print("\nRate limited on photos. Waiting 60s...", flush=True)
                time.sleep(60)
                continue
            r.raise_for_status()

            photos = r.json()
            if not photos:
                print(f"[{i}/{total}] {name} -> NO PHOTO")
                no_photo += 1
                continue

            prefix = photos[0].get("prefix", "")
            suffix = photos[0].get("suffix", "")
            if not prefix or not suffix:
                print(f"[{i}/{total}] {name} -> BAD PHOTO DATA")
                no_photo += 1
                continue

            photo_url = f"{prefix}{PHOTO_SIZE}{suffix}"

            # Step 3: Download image bytes
            img_r = requests.get(photo_url, timeout=TIMEOUT)
            img_r.raise_for_status()

            if len(img_r.content) < 500:
                print(f"[{i}/{total}] {name} -> IMAGE TOO SMALL ({len(img_r.content)}B)")
                errors += 1
                continue

            os.makedirs(dest_dir, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(img_r.content)

            manifest[slug] = f"{slug}/0.jpg"
            saved += 1

            size_kb = len(img_r.content) / 1024
            if saved <= 5 or saved % 20 == 0:
                print(f"[{i}/{total}] {name} -> SAVED ({size_kb:.0f} KB)", flush=True)

            # Save manifest every 20 downloads (crash recovery)
            if saved % 20 == 0:
                with open(MANIFEST_FILE, "w") as f:
                    json.dump(manifest, f, indent=2, sort_keys=True)

        except Exception as e:
            print(f"[{i}/{total}] {name} -> ERROR: {e}")
            errors += 1

        time.sleep(SLEEP)

    # Final manifest save
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    # Summary
    total_bytes = sum(
        os.path.getsize(os.path.join(dp, fn))
        for dp, _, fns in os.walk(IMAGES_DIR)
        for fn in fns
        if fn.endswith(".jpg")
    )

    print(f"\n{'=' * 50}")
    print(f"DONE: {total} restaurants processed")
    print(f"  Saved:       {saved}")
    print(f"  Skipped:     {skipped} (already existed)")
    print(f"  No match:    {no_match} (not on Foursquare)")
    print(f"  No photo:    {no_photo} (match but no photos)")
    print(f"  Errors:      {errors}")
    print(f"  Manifest:    {len(manifest)} entries")
    print(f"  Disk usage:  {total_bytes / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
