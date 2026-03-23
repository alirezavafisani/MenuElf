#!/usr/bin/env python3
"""Scrape menus — Batch 2: next 50 restaurants that have website URLs."""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Comment

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MENUS_DIR = Path(__file__).parent.parent / "menus"
DATA_DIR = Path(__file__).parent.parent / "data"
DISCOVERED_PATH = DATA_DIR / "discovered_restaurants.json"
NAME_MAPPING_PATH = Path(__file__).parent.parent / "name_mapping.json"
PLACES_DATA_PATH = Path(__file__).parent.parent / "restaurant_places_data.json"

BATCH_SIZE = 50
MIN_ITEMS = 3
MAX_ITEMS = 200
REQUEST_DELAY = 1  # 1s between different domains
REQUEST_TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MenuElf/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

SKIP_DOMAINS = [
    "youtube.com", "facebook.com", "instagram.com", "twitter.com",
    "jotform.com", "clover.com", "restaurants.accor.com", "form.",
    "linktr.ee", "tiktok.com", "linkedin.com", "yelp.com",
    "tripadvisor.com", "google.com/maps",
]

MENU_LINK_KEYWORDS = [
    "menu", "food", "our-menu", "eat", "order", "dine", "kitchen", "fare",
    "lunch", "dinner", "brunch",
]

COMMON_MENU_PATHS = [
    "/menu", "/food-menu", "/our-menu", "/menus", "/food",
    "/lunch-menu", "/dinner-menu", "/menu/", "/dine",
]

OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def clean_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def extract_price(text: str) -> float | None:
    m = re.search(r"\$\s?(\d{1,3}(?:\.\d{1,2})?)", text)
    if m:
        v = float(m.group(1))
        if 0.5 <= v <= 500:  # Sanity: skip $0 or $9999
            return v
    return None


def safe_get(url: str, label: str = "") -> tuple[requests.Response | None, str]:
    """GET with delay/timeout. Returns (response, failure_reason)."""
    time.sleep(REQUEST_DELAY)
    try:
        r = requests.get(
            url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True,
        )
        r.raise_for_status()
        return r, ""
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "connection_error"
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        return None, f"http_{code}"
    except Exception as e:
        return None, "connection_error"


# ---------------------------------------------------------------------------
# GPT fallback
# ---------------------------------------------------------------------------

def gpt_extract_menu(raw_text: str) -> list[dict]:
    if not OPENAI_KEY:
        return []
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_KEY)
        resp = client.chat.completions.create(
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
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        items = json.loads(content)
        return items if isinstance(items, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# HTML parsing — improved
# ---------------------------------------------------------------------------

def _is_js_rendered(soup: BeautifulSoup) -> bool:
    """Detect pages that need JavaScript to render content."""
    body = soup.find("body")
    if not body:
        return True
    text = body.get_text(strip=True)
    # Very little visible text usually means JS app
    if len(text) < 100:
        return True
    # Common SPA markers
    for marker in ["__NEXT_DATA__", "react-root", "app-root", "ng-app"]:
        if body.find(id=marker) or body.find(class_=marker):
            if len(text) < 300:
                return True
    return False


def find_menu_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Find likely menu page links from a homepage."""
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href_lower = a["href"].lower()
        text_lower = (a.get_text() or "").lower().strip()
        matched = any(kw in href_lower or kw in text_lower for kw in MENU_LINK_KEYWORDS)
        if not matched:
            continue
        full = urljoin(base_url, a["href"])
        # Exclude external ordering platforms
        if any(d in full.lower() for d in ["skip", "doordash", "ubereats", "grubhub"]):
            continue
        norm = full.rstrip("/").lower()
        if norm not in seen:
            seen.add(norm)
            links.append(full)
    return links[:6]


def try_common_menu_paths(base_url: str) -> list[str]:
    """Generate common menu page URLs to probe."""
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return [origin + p for p in COMMON_MENU_PATHS]


def parse_menu_from_html(soup: BeautifulSoup) -> list[dict]:
    """Extract menu items from parsed HTML. Improved multi-strategy."""
    body = soup.find("body") or soup

    # Remove noise
    for tag in body.find_all(["script", "style", "noscript"]):
        tag.decompose()
    for comment in body.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    items = []
    seen_names = set()
    current_category = None

    # --- Strategy 1: Menu-specific CSS classes ---
    menu_containers = body.select(
        "[class*=menu-item], [class*=dish], [class*=food-item], "
        "[class*=menu_item], [class*=menuItem], [class*=product-card], "
        "[class*=menu-card], [class*=item-card]"
    )
    if menu_containers:
        for container in menu_containers:
            text = clean_text(container.get_text())
            price = extract_price(text)
            # Find name: first heading or first bold/strong or first child text
            name_el = container.find(["h3", "h4", "h5", "strong", "b"])
            name = clean_text(name_el.get_text()) if name_el else ""
            if not name:
                # Fallback: first non-empty line
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                name = lines[0] if lines else ""
            name = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", name).strip(" -–—·•|")
            if not name or len(name) < 2 or len(name) > 120:
                continue
            nk = name.lower()
            if nk in seen_names:
                continue
            seen_names.add(nk)

            # Description
            desc_el = container.find(["p", "span"], class_=lambda c: c and ("desc" in str(c).lower() or "detail" in str(c).lower()))
            desc = clean_text(desc_el.get_text()) if desc_el else None
            if desc:
                desc = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", desc).strip()
                if len(desc) < 3:
                    desc = None

            items.append({
                "name": name, "price": price, "description": desc,
                "category": current_category, "dietary_info": [],
            })
        if len(items) >= MIN_ITEMS:
            return items

    # --- Strategy 2: DL/DT/DD lists ---
    for dl in body.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            name = clean_text(dt.get_text())
            dd_text = clean_text(dd.get_text())
            price = extract_price(dd_text) or extract_price(name)
            name = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", name).strip(" -–—·•|")
            if not name or len(name) < 2 or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            desc = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", dd_text).strip()
            items.append({
                "name": name, "price": price,
                "description": desc if len(desc) > 2 else None,
                "category": current_category, "dietary_info": [],
            })
    if len(items) >= MIN_ITEMS:
        return items

    # --- Strategy 3: Table rows ---
    for table in body.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            row_text = " ".join(clean_text(c.get_text()) for c in cells)
            price = extract_price(row_text)
            if price is None:
                continue
            name = clean_text(cells[0].get_text())
            name = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", name).strip()
            if not name or len(name) < 2 or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            desc = clean_text(cells[1].get_text()) if len(cells) > 2 else None
            if desc:
                desc = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", desc).strip()
                if len(desc) < 3:
                    desc = None
            items.append({
                "name": name, "price": price, "description": desc,
                "category": current_category, "dietary_info": [],
            })
    if len(items) >= MIN_ITEMS:
        return items

    # --- Strategy 4: Generic blocks with price patterns ---
    text_blocks = body.find_all(
        ["div", "li", "tr", "article", "section", "p", "dt", "dd"],
    )
    for block in text_blocks:
        block_text = clean_text(block.get_text())
        if not block_text or len(block_text) < 3:
            continue
        # Detect category headings
        if block.name in ("h2", "h3", "h4"):
            candidate = clean_text(block.get_text())
            if len(candidate) < 50 and not re.search(r"\$\d", candidate):
                current_category = candidate
                continue

        price = extract_price(block_text)
        if price is None:
            continue

        lines = [l.strip() for l in block_text.split("\n") if l.strip()]
        if not lines:
            continue
        name = lines[0]
        name = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", name).strip()
        name = re.sub(r"\s+", " ", name).strip(" -–—·•|")
        if not name or len(name) < 2 or len(name) > 120:
            continue
        nk = name.lower()
        if nk in seen_names:
            continue
        seen_names.add(nk)

        desc = " ".join(lines[1:]) if len(lines) > 1 else None
        if desc:
            desc = re.sub(r"\$\s?\d+(?:\.\d{1,2})?", "", desc).strip()
            if len(desc) < 3:
                desc = None

        items.append({
            "name": name, "price": price, "description": desc,
            "category": current_category, "dietary_info": [],
        })

    return items


def get_visible_text(soup: BeautifulSoup) -> str:
    body = soup.find("body") or soup
    for tag in body.find_all(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return clean_text(body.get_text(separator="\n"))


# ---------------------------------------------------------------------------
# Website scraping pipeline
# ---------------------------------------------------------------------------

def scrape_website(restaurant: dict) -> tuple[list[dict], str]:
    """
    Scrape a restaurant website for menu items.
    Returns (items, failure_reason).  failure_reason == "" on success.
    """
    url = restaurant.get("website", "")
    if not url:
        return [], "no_website"

    if any(d in url.lower() for d in SKIP_DOMAINS):
        return [], "no_menu_link"

    # --- Fetch homepage ---
    resp, fail = safe_get(url, "homepage")
    if not resp:
        return [], fail or "connection_error"

    soup = BeautifulSoup(resp.text, "html.parser")

    if _is_js_rendered(soup):
        return [], "js_rendered"

    # --- Collect candidate pages ---
    menu_links = find_menu_links(soup, url)
    # Also probe common paths
    for cp in try_common_menu_paths(url):
        norm = cp.rstrip("/").lower()
        if norm not in {l.rstrip("/").lower() for l in menu_links}:
            menu_links.append(cp)

    pages: list[tuple[BeautifulSoup, str]] = [(soup, url)]

    for link in menu_links[:6]:
        r2, _ = safe_get(link, "menu page")
        if r2:
            s2 = BeautifulSoup(r2.text, "html.parser")
            if not _is_js_rendered(s2):
                pages.append((s2, link))

    # --- Parse each page, keep the best ---
    best_items: list[dict] = []
    best_text = ""

    for s, page_url in pages:
        items = parse_menu_from_html(s)
        if len(items) > len(best_items):
            best_items = items
            best_text = get_visible_text(s)

    # --- GPT fallback ---
    if len(best_items) < MIN_ITEMS and best_text and OPENAI_KEY:
        gpt_items = gpt_extract_menu(best_text)
        if len(gpt_items) > len(best_items):
            best_items = gpt_items

    if len(best_items) < MIN_ITEMS:
        if not menu_links and len(best_items) == 0:
            return [], "no_menu_link"
        return best_items, "too_few_items"

    if len(best_items) > MAX_ITEMS:
        return best_items, "too_many_items"

    return best_items, ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    discovered = json.loads(DISCOVERED_PATH.read_text())

    # Build lookup by place_id for fast updates
    disc_idx = {d["place_id"]: d for d in discovered}

    # Filter: new + has website + not a junk domain
    candidates = [
        r for r in discovered
        if r["status"] == "new"
        and r.get("website")
        and not any(d in (r["website"] or "").lower() for d in SKIP_DOMAINS)
    ]
    candidates.sort(key=lambda r: r.get("rating") or 0, reverse=True)
    batch = candidates[:BATCH_SIZE]

    print("=" * 78)
    print(f"MENU SCRAPING — BATCH 2  ({len(batch)} restaurants with websites)")
    print("=" * 78)
    print(f"Found {len(candidates)} total new restaurants with usable websites")
    print()

    name_mapping = json.loads(NAME_MAPPING_PATH.read_text())
    places_data = json.loads(PLACES_DATA_PATH.read_text())

    results = []
    total_items = 0
    total_priced = 0
    success_count = 0
    fail_reasons: dict[str, int] = {}

    for i, restaurant in enumerate(batch):
        name = restaurant["name"]
        slug = slugify(name)
        print(f"\n[{i+1}/{len(batch)}] {name}")

        menu_path = MENUS_DIR / f"{slug}.json"
        if menu_path.exists():
            print(f"    SKIP — menu file already exists")
            results.append({"name": name, "status": "exists", "items": 0, "priced": 0, "reason": ""})
            continue

        items, reason = scrape_website(restaurant)

        if reason:
            # Failed
            print(f"    FAILED — {reason} ({len(items)} items found)")
            disc_idx[restaurant["place_id"]]["status"] = "failed"
            disc_idx[restaurant["place_id"]]["failure_reason"] = reason
            fail_reasons[reason] = fail_reasons.get(reason, 0) + 1
            results.append({"name": name, "status": "failed", "items": len(items), "priced": 0, "reason": reason})
            continue

        # Clean items
        clean_items = []
        for item in items:
            price = item.get("price")
            if isinstance(price, str):
                try:
                    price = float(re.sub(r"[^0-9.]", "", price))
                except (ValueError, TypeError):
                    price = None
            n = clean_text(str(item.get("name", "")))
            if not n or len(n) < 2:
                continue
            clean_items.append({
                "name": n,
                "price": price,
                "description": clean_text(str(item.get("description", ""))) or None,
                "category": item.get("category"),
                "dietary_info": item.get("dietary_info", []),
            })

        if len(clean_items) < MIN_ITEMS:
            print(f"    FAILED — too_few_items after cleaning ({len(clean_items)})")
            disc_idx[restaurant["place_id"]]["status"] = "failed"
            disc_idx[restaurant["place_id"]]["failure_reason"] = "too_few_items"
            fail_reasons["too_few_items"] = fail_reasons.get("too_few_items", 0) + 1
            results.append({"name": name, "status": "failed", "items": len(clean_items), "priced": 0, "reason": "too_few_items"})
            continue

        priced = sum(1 for it in clean_items if it["price"] is not None)
        print(f"    OK — {len(clean_items)} items, {priced} priced")

        # Save menu
        menu_data = {
            "restaurant": slug,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "item_count": len(clean_items),
            "items": clean_items,
        }
        menu_path.write_text(json.dumps(menu_data, indent=2, ensure_ascii=False))

        name_mapping[slug] = name
        places_data[slug] = {
            "lat": restaurant.get("lat"),
            "lng": restaurant.get("lng"),
            "rating": restaurant.get("rating"),
            "user_ratings_total": None,
            "address": restaurant.get("address", ""),
        }
        disc_idx[restaurant["place_id"]]["status"] = "scraped"

        results.append({"name": name, "status": "scraped", "items": len(clean_items), "priced": priced, "reason": ""})
        total_items += len(clean_items)
        total_priced += priced
        success_count += 1

    # Persist
    NAME_MAPPING_PATH.write_text(json.dumps(name_mapping, indent=2, ensure_ascii=False))
    PLACES_DATA_PATH.write_text(json.dumps(places_data, indent=2, ensure_ascii=False))
    DISCOVERED_PATH.write_text(json.dumps(discovered, indent=2, ensure_ascii=False))

    # Report
    print()
    print("=" * 90)
    print("SCRAPING REPORT — BATCH 2")
    print("=" * 90)
    print(f"{'Restaurant':<42} {'Status':<10} {'Items':>5} {'Priced':>6}  {'Reason'}")
    print("-" * 90)
    for r in results:
        print(f"{r['name'][:42]:<42} {r['status']:<10} {r['items']:>5} {r['priced']:>6}  {r['reason']}")
    print("-" * 90)
    print(f"Attempted:                {len(batch)}")
    print(f"Scraped successfully:     {success_count}")
    print(f"Failed:                   {len(batch) - success_count}")
    if fail_reasons:
        print(f"  Failure breakdown:")
        for reason, count in sorted(fail_reasons.items(), key=lambda x: -x[1]):
            print(f"    {reason:<25} {count}")
    print(f"Total new menu items:     {total_items}")
    print(f"Items with prices:        {total_priced}")
    print("=" * 90)


if __name__ == "__main__":
    main()
