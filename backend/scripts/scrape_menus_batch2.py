#!/usr/bin/env python3
"""Scrape menus for discovered restaurants — Batch 2 (restaurants 16-30)."""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MENUS_DIR = Path(__file__).parent.parent / "menus"
DATA_DIR = Path(__file__).parent.parent / "data"
DISCOVERED_PATH = DATA_DIR / "discovered_restaurants.json"
NAME_MAPPING_PATH = Path(__file__).parent.parent / "name_mapping.json"
PLACES_DATA_PATH = Path(__file__).parent.parent / "restaurant_places_data.json"
PROGRESS_PATH = DATA_DIR / "scrape_progress.json"

BATCH_SIZE = 15
BATCH_LABEL = "15c"
MIN_ITEMS = 3
REQUEST_DELAY = 2
REQUEST_TIMEOUT = 5
HEADERS = {"User-Agent": "MenuElf/1.0 Calgary Restaurant Menu Aggregator"}

OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def safe_get(url: str, **kwargs) -> requests.Response | None:
    time.sleep(REQUEST_DELAY)
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"      GET failed ({url[:80]}): {e}")
        return None


def extract_price(text: str) -> float | None:
    m = re.search(r"\$\s?(\d+(?:\.\d{1,2})?)", text)
    if m:
        return float(m.group(1))
    return None


def clean_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# GPT-4o-mini fallback
# ---------------------------------------------------------------------------

def gpt_extract_menu(raw_text: str) -> list[dict]:
    if not OPENAI_KEY:
        return []
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a menu data extractor. Given raw text from a "
                        "restaurant website, extract ALL menu items into a JSON "
                        "array. Each item: {\"name\": string, \"price\": number "
                        "or null, \"description\": string or null, \"category\": "
                        "string or null, \"dietary_info\": []}. Only real menu "
                        "items. Prices as numbers without $. Return ONLY valid "
                        "JSON array, nothing else."
                    ),
                },
                {"role": "user", "content": raw_text[:4000]},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        items = json.loads(content)
        if isinstance(items, list):
            return items
    except Exception as e:
        print(f"      GPT extraction failed: {e}")
    return []


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------

def find_menu_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    keywords = ["menu", "food", "our-menu", "eat", "order", "dishes", "carte"]
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = (a.get_text() or "").lower()
        if any(kw in href or kw in text for kw in keywords):
            full = a["href"]
            if full.startswith("/") or not full.startswith("http"):
                from urllib.parse import urljoin
                full = urljoin(base_url, full)
            if full not in links:
                links.append(full)
    return links[:5]


def parse_menu_from_html(soup: BeautifulSoup) -> list[dict]:
    items = []
    body = soup.find("body") or soup
    text_blocks = body.find_all(
        ["div", "li", "tr", "article", "section", "p", "span", "h2", "h3", "h4", "dt", "dd"],
    )

    seen_names = set()
    current_category = None

    for block in text_blocks:
        block_text = clean_text(block.get_text())
        if not block_text or len(block_text) < 2:
            continue

        if block.name in ("h2", "h3", "h4") and len(block_text) < 50:
            if not re.search(r"\$\d", block_text):
                current_category = block_text
                continue

        price = extract_price(block_text)
        if price is None:
            continue

        lines = [l.strip() for l in block_text.split("\n") if l.strip()]
        if not lines:
            continue

        name = lines[0]
        name = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", name).strip()
        name = re.sub(r"\s+", " ", name).strip(" -\u2013\u2014\u00b7\u2022|")
        if not name or len(name) < 2 or len(name) > 120:
            continue

        name_key = name.lower()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        desc = " ".join(lines[1:]) if len(lines) > 1 else None
        if desc:
            desc = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", desc).strip()
            if len(desc) < 3:
                desc = None

        items.append({
            "name": name,
            "price": price,
            "description": desc,
            "category": current_category,
            "dietary_info": [],
        })

    return items


def get_visible_text(soup: BeautifulSoup) -> str:
    body = soup.find("body") or soup
    for tag in body.find_all(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return clean_text(body.get_text(separator="\n"))


# ---------------------------------------------------------------------------
# Source scrapers
# ---------------------------------------------------------------------------

def try_website(restaurant: dict) -> tuple[list[dict], str]:
    url = restaurant.get("website")
    if not url:
        return [], ""

    skip_domains = ["youtube.com", "facebook.com", "instagram.com", "twitter.com",
                    "jotform.com", "clover.com", "restaurants.accor.com", "form.",
                    "ritual.co", "order.online"]
    if any(d in url.lower() for d in skip_domains):
        print(f"      Skipping non-menu website: {url[:60]}")
        return [], ""

    print(f"      Trying website: {url[:70]}")
    resp = safe_get(url)
    if not resp:
        return [], ""

    soup = BeautifulSoup(resp.text, "html.parser")
    menu_links = find_menu_links(soup, url)
    pages_to_parse = [(soup, resp.text)]

    for link in menu_links[:3]:
        print(f"      Following menu link: {link[:70]}")
        mresp = safe_get(link)
        if mresp:
            msoup = BeautifulSoup(mresp.text, "html.parser")
            pages_to_parse.append((msoup, mresp.text))

    best_items = []
    best_text = ""
    for s, raw in pages_to_parse:
        items = parse_menu_from_html(s)
        if len(items) > len(best_items):
            best_items = items
            best_text = get_visible_text(s)

    if len(best_items) < MIN_ITEMS and best_text:
        return best_items, best_text

    return best_items, best_text if len(best_items) < 10 else ""


def try_doordash(name: str) -> tuple[list[dict], str]:
    search_url = f"https://www.doordash.com/search/store/{quote_plus(name + ' Calgary')}/"
    print(f"      Trying DoorDash: {search_url[:70]}")
    resp = safe_get(search_url)
    if not resp:
        return [], ""

    soup = BeautifulSoup(resp.text, "html.parser")
    items = parse_menu_from_html(soup)
    text = get_visible_text(soup) if len(items) < MIN_ITEMS else ""
    return items, text


def try_google_search(name: str) -> tuple[list[dict], str]:
    query = quote_plus(f"{name} Calgary menu")
    url = f"https://www.google.com/search?q={query}"
    print(f"      Trying Google search: {name} Calgary menu")
    resp = safe_get(url)
    if not resp:
        return [], ""

    soup = BeautifulSoup(resp.text, "html.parser")
    result_urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/url?q=" in href:
            actual = href.split("/url?q=")[1].split("&")[0]
            if "google.com" not in actual and actual.startswith("http"):
                result_urls.append(actual)

    best_items = []
    best_text = ""
    for rurl in result_urls[:2]:
        print(f"      Following Google result: {rurl[:70]}")
        rresp = safe_get(rurl)
        if not rresp:
            continue
        rsoup = BeautifulSoup(rresp.text, "html.parser")
        items = parse_menu_from_html(rsoup)
        if len(items) > len(best_items):
            best_items = items
            best_text = get_visible_text(rsoup)

    return best_items, best_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape_restaurant(restaurant: dict) -> tuple[list[dict], str]:
    name = restaurant["name"]

    # Source 1: Website
    items, raw_text = try_website(restaurant)
    if len(items) >= MIN_ITEMS:
        return items, "website"

    # Source 2: DoorDash (best success rate from batch 1)
    dd_items, dd_text = try_doordash(name)
    if len(dd_items) >= MIN_ITEMS:
        return dd_items, "doordash"
    if len(dd_items) > len(items):
        items, raw_text = dd_items, dd_text

    # Source 3: Google search
    g_items, g_text = try_google_search(name)
    if len(g_items) >= MIN_ITEMS:
        return g_items, "google"
    if len(g_items) > len(items):
        items, raw_text = g_items, g_text

    # GPT fallback
    if raw_text and len(items) < MIN_ITEMS:
        print(f"      Trying GPT extraction on {len(raw_text)} chars of text...")
        gpt_items = gpt_extract_menu(raw_text)
        if len(gpt_items) >= MIN_ITEMS:
            return gpt_items, "GPT"
        if len(gpt_items) > len(items):
            items = gpt_items

    if len(items) >= MIN_ITEMS:
        return items, "parsed"

    return [], "failed"


def main():
    # Load discovered restaurants
    discovered = json.loads(DISCOVERED_PATH.read_text())
    new_restaurants = [r for r in discovered if r["status"] == "new"]
    batch = new_restaurants[:BATCH_SIZE]

    # Load existing progress
    if PROGRESS_PATH.exists():
        prev_progress = json.loads(PROGRESS_PATH.read_text())
        prev_restaurants = prev_progress.get("restaurants", [])
        prev_success = prev_progress.get("scraped_success", 0)
        prev_failed = prev_progress.get("scraped_failed", 0)
    else:
        prev_restaurants = []
        prev_success = 0
        prev_failed = 0

    print("=" * 70)
    print(f"MENU SCRAPING — BATCH 2 ({len(batch)} restaurants)")
    print("=" * 70)
    print()

    for i, r in enumerate(batch):
        print(f"{i+1:2}. {r['name'][:50]:<51} rating={r.get('rating','?'):<5} web={'yes' if r.get('website') else 'no'}")
    print()

    # Load existing supporting files
    name_mapping = json.loads(NAME_MAPPING_PATH.read_text())
    places_data = json.loads(PLACES_DATA_PATH.read_text())

    results = []
    total_items = 0
    total_with_price = 0
    success_count = 0

    for i, restaurant in enumerate(batch):
        name = restaurant["name"]
        slug = slugify(name)
        print(f"\n[{i+1}/{len(batch)}] {name}")
        print(f"    Slug: {slug}")

        # Check if menu already exists
        menu_path = MENUS_DIR / f"{slug}.json"
        if menu_path.exists():
            print(f"    SKIP: Menu file already exists")
            results.append({"name": name, "source": "exists", "items": 0, "priced": 0})
            continue

        items, source = scrape_restaurant(restaurant)

        if source == "failed" or len(items) < MIN_ITEMS:
            print(f"    FAILED: Could not find menu for {name}")
            results.append({"name": name, "source": "failed", "items": 0, "priced": 0})
            for d in discovered:
                if d["place_id"] == restaurant["place_id"]:
                    d["status"] = "failed"
            continue

        # Normalize items
        clean_items = []
        for item in items:
            price = item.get("price")
            if isinstance(price, str):
                try:
                    price = float(re.sub(r"[^0-9.]", "", price))
                except (ValueError, TypeError):
                    price = None
            clean_items.append({
                "name": clean_text(str(item.get("name", ""))),
                "price": price,
                "description": clean_text(str(item.get("description", ""))) or None,
                "category": item.get("category"),
                "dietary_info": item.get("dietary_info", []),
            })

        priced = sum(1 for it in clean_items if it["price"] is not None)
        print(f"    SUCCESS: {len(clean_items)} items ({priced} with prices) via {source}")

        # Save menu file
        menu_data = {
            "restaurant": slug,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "item_count": len(clean_items),
            "items": clean_items,
        }
        menu_path.write_text(json.dumps(menu_data, indent=2, ensure_ascii=False))

        # Update name_mapping
        name_mapping[slug] = name

        # Update places data
        places_data[slug] = {
            "lat": restaurant.get("lat"),
            "lng": restaurant.get("lng"),
            "rating": restaurant.get("rating"),
            "user_ratings_total": None,
            "address": restaurant.get("address", ""),
        }

        # Mark as scraped in discovered
        for d in discovered:
            if d["place_id"] == restaurant["place_id"]:
                d["status"] = "scraped"

        results.append({"name": name, "source": source, "items": len(clean_items), "priced": priced})
        total_items += len(clean_items)
        total_with_price += priced
        success_count += 1

    # Save updated files
    NAME_MAPPING_PATH.write_text(json.dumps(name_mapping, indent=2, ensure_ascii=False))
    PLACES_DATA_PATH.write_text(json.dumps(places_data, indent=2, ensure_ascii=False))
    DISCOVERED_PATH.write_text(json.dumps(discovered, indent=2, ensure_ascii=False))

    # Report
    print()
    print("=" * 70)
    print("BATCH 2 SCRAPING REPORT")
    print("=" * 70)
    print(f"{'Restaurant':<45} {'Source':<12} {'Items':>5} {'Priced':>6}")
    print("-" * 70)
    for r in results:
        print(f"{r['name'][:45]:<45} {r['source']:<12} {r['items']:>5} {r['priced']:>6}")
    print("-" * 70)
    print(f"Restaurants attempted:          {len(batch)}")
    print(f"Restaurants successfully scraped: {success_count}")
    print(f"Total new menu items:            {total_items}")
    print(f"Items with prices:               {total_with_price}")
    print()

    # Running totals
    running_success = prev_success + success_count
    running_failed = prev_failed + sum(1 for r in results if r["source"] == "failed")
    print(f"RUNNING TOTALS (all batches):")
    print(f"  Total scraped successfully: {running_success}")
    print(f"  Total failed:              {running_failed}")
    print("=" * 70)

    # Save scrape_progress.json (append to existing)
    batch_failed = sum(1 for r in results if r["source"] == "failed")
    batch_skipped = sum(1 for r in results if r["source"] == "exists")

    batch_entries = []
    for r in results:
        entry = {
            "name": r["name"],
            "slug": slugify(r["name"]),
            "status": "success" if r["source"] not in ("failed", "exists") else r["source"],
            "items_count": r["items"],
        }
        if r["source"] == "failed":
            entry["reason"] = "no menu found"
        elif r["source"] == "exists":
            entry["reason"] = "already exists"
        batch_entries.append(entry)

    progress = {
        "total_discovered": len(discovered),
        "scraped_success": running_success,
        "scraped_failed": running_failed,
        "skipped": batch_skipped,
        "remaining": len(new_restaurants) - len(batch),
        "last_batch": BATCH_LABEL,
        "restaurants": prev_restaurants + batch_entries,
    }

    PROGRESS_PATH.write_text(json.dumps(progress, indent=2))
    print(f"\nProgress saved to: {PROGRESS_PATH}")


if __name__ == "__main__":
    main()
