#!/usr/bin/env python3
"""
Download Google Places photos and upload to Supabase Storage.

Usage:
    GOOGLE_MAPS_API_KEY=<key> SUPABASE_SERVICE_KEY=<key> python backend/scripts/upload_photos_to_supabase.py

Reads restaurant_photos.json, downloads each photo from Google Places,
uploads to Supabase Storage bucket 'restaurant-photos', and saves
the resulting public URLs to restaurant_photo_urls.json.
"""

import json
import os
import sys
import time

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTOS_FILE = os.path.join(BASE_DIR, "restaurant_photos.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "restaurant_photo_urls.json")

SUPABASE_URL = "https://vzpgecftlnghkrzosjxb.supabase.co"
BUCKET_NAME = "restaurant-photos"
DELAY_BETWEEN_REQUESTS = 0.1


def create_bucket(service_key: str):
    """Create the storage bucket if it doesn't exist."""
    url = f"{SUPABASE_URL}/storage/v1/bucket"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    body = {"id": BUCKET_NAME, "name": BUCKET_NAME, "public": True}
    resp = requests.post(url, json=body, headers=headers, timeout=15)
    if resp.status_code == 200:
        print(f"Created bucket '{BUCKET_NAME}'.", flush=True)
    elif resp.status_code == 409:
        print(f"Bucket '{BUCKET_NAME}' already exists.", flush=True)
    else:
        print(f"Warning: bucket creation returned {resp.status_code}: {resp.text[:200]}", flush=True)


def download_photo(photo_ref: str, google_key: str) -> bytes | None:
    """Download a photo from Google Places API. Returns image bytes."""
    if photo_ref.startswith("places/"):
        url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxWidthPx=800&key={google_key}"
    else:
        url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference={photo_ref}&key={google_key}"

    resp = requests.get(url, timeout=30, allow_redirects=True)
    if resp.status_code != 200:
        raise RuntimeError(f"Download failed ({resp.status_code}): {resp.text[:100]}")

    content_type = resp.headers.get("Content-Type", "")
    if "image" not in content_type and len(resp.content) < 1000:
        raise RuntimeError(f"Not an image response: {content_type}")

    return resp.content


def upload_to_supabase(image_bytes: bytes, path: str, service_key: str) -> str:
    """Upload image bytes to Supabase Storage. Returns public URL."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{path}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "image/jpeg",
        "x-upsert": "true",
    }
    resp = requests.put(url, data=image_bytes, headers=headers, timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed ({resp.status_code}): {resp.text[:200]}")

    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{path}"


def main():
    google_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not google_key:
        print("ERROR: GOOGLE_MAPS_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)
    if not service_key:
        print("ERROR: SUPABASE_SERVICE_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(PHOTOS_FILE):
        print(f"ERROR: {PHOTOS_FILE} not found.", file=sys.stderr)
        sys.exit(1)

    with open(PHOTOS_FILE, "r", encoding="utf-8") as f:
        photos_data = json.load(f)

    print(f"Loaded photo references for {len(photos_data)} restaurants.", flush=True)

    # Create bucket
    create_bucket(service_key)

    # Load existing results to allow resuming
    results = {}
    if os.path.isfile(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
        print(f"Loaded {len(results)} existing results (will skip these).", flush=True)

    total = len(photos_data)
    success_count = len(results)
    fail_count = 0
    photo_count = 0

    for i, (slug, data) in enumerate(photos_data.items(), 1):
        if slug in results:
            continue

        photos = data.get("photos", [])
        slug_urls = []
        slug_failed = False

        for idx, photo in enumerate(photos):
            ref = photo.get("photo_reference", "")
            if not ref:
                continue

            try:
                image_bytes = download_photo(ref, google_key)
                if image_bytes:
                    path = f"{slug}/{idx}.jpg"
                    public_url = upload_to_supabase(image_bytes, path, service_key)
                    slug_urls.append(public_url)
                    photo_count += 1
            except Exception as e:
                print(f"  Error {slug} photo {idx}: {e}", flush=True)
                slug_failed = True

            time.sleep(DELAY_BETWEEN_REQUESTS)

        if slug_urls:
            results[slug] = slug_urls
            success_count += 1
        elif not slug_failed:
            results[slug] = []
            success_count += 1
        else:
            fail_count += 1

        if i % 10 == 0:
            print(f"  Progress: {i}/{total} restaurants processed, {photo_count} photos uploaded", flush=True)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)

    # Final save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone. {success_count} restaurants uploaded, {fail_count} failed, "
          f"{photo_count} total photos.", flush=True)
    print(f"Results saved to {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    main()
