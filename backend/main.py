import os
import json
import time
import glob
import re
import random
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from analytics import log_event
from pydantic import BaseModel
from openai import OpenAI
from typing import List, Optional


def get_real_ip(request) -> str:
    """Extract real client IP from X-Forwarded-For header, falling back to request.client.

    Railway (and most PaaS) run behind a reverse proxy, so request.client.host is the
    proxy IP. The original client IP is in the first entry of X-Forwarded-For.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

# Resolve paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENUS_DIR = os.environ.get("MENUS_DIR", os.path.join(BASE_DIR, "menus"))

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ─── Simple IP-based rate limiter for the search endpoints ───
# Search hits OpenAI for one embedding per query, so it is worth capping per IP.
_search_rate_limits: dict[str, list[float]] = defaultdict(list)
SEARCH_RATE_LIMIT = 120  # requests per hour
SEARCH_RATE_WINDOW = 3600

def check_search_rate_limit(request: Request):
    ip = get_real_ip(request)
    now = time.time()
    _search_rate_limits[ip] = [t for t in _search_rate_limits[ip] if now - t < SEARCH_RATE_WINDOW]
    if len(_search_rate_limits[ip]) >= SEARCH_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    _search_rate_limits[ip].append(now)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


class AnalyticsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        try:
            path = request.url.path
            if path == "/" or path == "/app" or path == "/app/":
                ip = get_real_ip(request)
                log_event("page_view", ip, path)
        except Exception:
            pass
        return response


app.add_middleware(AnalyticsMiddleware)

# ─── Restaurant name list ───
NAME_MAPPING_FILE = os.path.join(BASE_DIR, "name_mapping.json")
NAME_MAPPING = {}
REVERSE_MAPPING = {}

def get_restaurant_names():
    global NAME_MAPPING, REVERSE_MAPPING
    if os.path.isfile(NAME_MAPPING_FILE):
        with open(NAME_MAPPING_FILE, "r") as f:
            NAME_MAPPING = json.load(f)
        print(f"Loaded name mapping with {len(NAME_MAPPING)} entries", flush=True)
    else:
        try:
            filenames = [f.replace(".json", "") for f in os.listdir(MENUS_DIR)
                         if f.endswith(".json") and f != "_conversion_log.json"]
            for slug in filenames:
                NAME_MAPPING[slug] = slug.replace("-", " ").replace("_", " ").title()
        except FileNotFoundError:
            print(
                f"WARNING: MENUS_DIR {MENUS_DIR} not found. "
                "App will start with no restaurants (expected in CI / fresh checkouts).",
                flush=True,
            )
            NAME_MAPPING = {}
        except Exception as e:
            print(f"WARNING: failed to list MENUS_DIR: {e}", flush=True)
            NAME_MAPPING = {}
    REVERSE_MAPPING = {v.lower(): k for k, v in NAME_MAPPING.items()}
    return sorted(NAME_MAPPING.values())

# Data loaders run inside @app.on_event("startup") (see bottom of file).
# At import time we only declare empty defaults so the app can ALWAYS import
# cleanly, even in CI or fresh checkouts with no data files.
RESTAURANT_LIST: list[str] = []

# ─── Menu loader ───
def load_menu(display_name: str):
    slug = REVERSE_MAPPING.get(display_name.lower())
    if slug:
        for fn_variant in [slug + ".json", slug.replace(" ", "-") + ".json", slug.replace(" ", "_") + ".json"]:
            path = os.path.join(MENUS_DIR, fn_variant)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
    base = display_name.lower().replace(" ", "").replace("'", "").replace("-", "")
    for variant in [base + ".json", display_name.lower().replace(" ", "-") + ".json"]:
        path = os.path.join(MENUS_DIR, variant)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    for fn in os.listdir(MENUS_DIR):
        if fn.endswith(".json"):
            fn_clean = fn.replace(".json", "").replace("-", "").replace("_", "").lower()
            if fn_clean == base:
                with open(os.path.join(MENUS_DIR, fn), "r", encoding="utf-8") as f:
                    return json.load(f)
    return None

# ─── Data cleaning ───
# Category normalization map: raw -> clean
_CATEGORY_RENAME = {
    "SEXY SANDWICHES": "Sandwiches",
    "FRICKEN MENU": "Chicken",
    "FRICKEN BY THE PIECE": "Chicken",
    "CHICKEN SINGLES": "Chicken",
    "CHICKEN PACK": "Chicken",
    "KETO PITA WRAP": "Wraps",
    "BAKED LASAGNA": "Pasta",
    "PASTA ME": "Pasta",
    "BŌLS": "Bowls",
    "GUS'S FAVES": "Specials",
    "SHISHA ACCESSORIES": "Other",
    "UNCATEGORIZED": "Other",
    "Uncategorized": "Other",
    "Menu": "Food",
    "Food Menu": "Food",
    "General Menu Items": "Other",
    "OTHER": "Other",
}

def _clean_category(cat: str | None) -> str:
    if not cat:
        return ""
    # Check rename map first
    if cat in _CATEGORY_RENAME:
        return _CATEGORY_RENAME[cat]
    # If ALL-CAPS (and more than 1 word or known short ones), title-case it
    if cat.isupper() and len(cat) > 1:
        return cat.title()
    return cat

def _clean_description(desc: str | None, name: str | None) -> str:
    if not desc or desc in ("None", "null", "none"):
        return ""
    desc = desc.strip()
    # Remove if description is just the name repeated
    if name and desc == name.strip():
        return ""
    # Remove if description is just a price number
    try:
        float(desc.replace("$", "").replace(",", "").strip())
        return ""
    except ValueError:
        pass
    return desc

def clean_menu_index(items: list[dict]) -> list[dict]:
    """Clean categories and descriptions in menu index in-place."""
    for item in items:
        item["category"] = _clean_category(item.get("category"))
        item["description"] = _clean_description(
            item.get("description"), item.get("name")
        )
    return items

# ─── Flat menu index ───
import numpy as np

MENU_DB_FILE = os.path.join(BASE_DIR, "menu_db.json")
EMBEDDINGS_NPZ_FILE = os.path.join(BASE_DIR, "menu_embeddings.npz")
EMBEDDINGS_NPY_FILE = os.path.join(BASE_DIR, "menu_embeddings.npy")
MENU_INDEX: List[dict] = []
MENU_EMBEDDINGS: np.ndarray = None

def load_menu_index():
    global MENU_INDEX, MENU_EMBEDDINGS
    try:
        if os.path.isfile(MENU_DB_FILE):
            with open(MENU_DB_FILE, "r") as f:
                MENU_INDEX = json.load(f)
            clean_menu_index(MENU_INDEX)
            print(f"Loaded and cleaned {len(MENU_INDEX)} menu items", flush=True)
        else:
            MENU_INDEX = []

        if os.path.isfile(EMBEDDINGS_NPZ_FILE):
            data = np.load(EMBEDDINGS_NPZ_FILE)
            MENU_EMBEDDINGS = data["embeddings"].astype(np.float32)
        elif os.path.isfile(EMBEDDINGS_NPY_FILE):
            MENU_EMBEDDINGS = np.load(EMBEDDINGS_NPY_FILE, mmap_mode='r')
        else:
            MENU_EMBEDDINGS = None
    except Exception as e:
        print(f"Error loading menu DB: {e}", flush=True)


# ─── Places Data ───
PLACES_DATA_FILE = os.path.join(BASE_DIR, "restaurant_places_data.json")
PLACES_DATA = {}

def load_places_data():
    global PLACES_DATA
    if os.path.isfile(PLACES_DATA_FILE):
        with open(PLACES_DATA_FILE, "r", encoding="utf-8") as f:
            PLACES_DATA = json.load(f)
        print(f"Loaded places data for {len(PLACES_DATA)} restaurants", flush=True)


# ─── Photo URLs ───
PHOTO_URLS_FILE = os.path.join(BASE_DIR, "restaurant_photo_urls.json")
PHOTO_URLS: dict[str, list[str]] = {}

def load_photo_urls():
    global PHOTO_URLS
    if os.path.isfile(PHOTO_URLS_FILE):
        with open(PHOTO_URLS_FILE, "r", encoding="utf-8") as f:
            PHOTO_URLS = json.load(f)
        print(f"Loaded photo URLs for {len(PHOTO_URLS)} restaurants", flush=True)


# ─── Restaurant Photos (Google Places references + Foursquare static) ───
RESTAURANT_PHOTOS_FILE = os.path.join(BASE_DIR, "restaurant_photos.json")
RESTAURANT_PHOTOS: dict[str, dict] = {}

def load_restaurant_photos():
    global RESTAURANT_PHOTOS
    if os.path.isfile(RESTAURANT_PHOTOS_FILE):
        with open(RESTAURANT_PHOTOS_FILE, "r", encoding="utf-8") as f:
            RESTAURANT_PHOTOS = json.load(f)
        print(f"Loaded photo references for {len(RESTAURANT_PHOTOS)} restaurants", flush=True)


# Static images directory (for Foursquare-scraped photos)
IMAGES_DIR = os.path.join(BASE_DIR, "restaurant_images")
PHOTO_MANIFEST_FILE = os.path.join(BASE_DIR, "restaurant_images_manifest.json")
PHOTO_MANIFEST: dict[str, str] = {}


def load_photo_manifest():
    global PHOTO_MANIFEST
    if os.path.isfile(PHOTO_MANIFEST_FILE):
        with open(PHOTO_MANIFEST_FILE, "r") as f:
            PHOTO_MANIFEST = json.load(f)
        print(f"Loaded photo manifest with {len(PHOTO_MANIFEST)} entries", flush=True)


# ─── Startup: load all data AFTER app object exists, so module import
# ─── itself can NEVER crash on missing files, bad JSON, or broken
# ─── filesystems. This is the structural fix for the chunk 1/2/3.1 bug class.
@app.on_event("startup")
async def load_all_data():
    global RESTAURANT_LIST
    try:
        RESTAURANT_LIST = get_restaurant_names()
    except Exception as e:
        print(f"Failed to load restaurant names: {e}", flush=True)
    try:
        load_menu_index()
    except Exception as e:
        print(f"Failed to load menu index: {e}", flush=True)
    try:
        load_places_data()
    except Exception as e:
        print(f"Failed to load places data: {e}", flush=True)
    try:
        load_photo_urls()
    except Exception as e:
        print(f"Failed to load photo URLs: {e}", flush=True)
    try:
        load_restaurant_photos()
    except Exception as e:
        print(f"Failed to load restaurant photos: {e}", flush=True)
    try:
        load_photo_manifest()
    except Exception as e:
        print(f"Failed to load photo manifest: {e}", flush=True)
    print(
        f"Startup complete: {len(RESTAURANT_LIST)} restaurants, "
        f"{len(MENU_INDEX)} dishes indexed",
        flush=True,
    )

# ─── Helpers ───
def _get_local_photo_url(slug: str) -> str | None:
    """Return a URL path if a local restaurant photo exists on disk, else None.

    Checks three patterns against the restaurant_images/ directory:
      {slug}/0.jpg  (subdir with numbered files — Foursquare scrape format)
      {slug}/1.jpg  (alternate index)
      {slug}.jpg    (flat file)
    """
    for rel in (
        os.path.join(slug, "0.jpg"),
        os.path.join(slug, "1.jpg"),
        f"{slug}.jpg",
    ):
        if os.path.isfile(os.path.join(IMAGES_DIR, rel)):
            return f"/restaurant-images/{rel}"
    return None


# ─── Endpoints ───
@app.get("/health")
def health_check():
    return {"status": "ok", "restaurants_loaded": len(RESTAURANT_LIST), "menu_items_indexed": len(MENU_INDEX)}

@app.get("/restaurants")
def get_restaurants(q: str = ""):
    q = q.lower().strip()
    load_places_data()

    results = []
    for display_name in RESTAURANT_LIST:
        if q and q not in display_name.lower():
            continue
        slug = REVERSE_MAPPING.get(display_name.lower())
        rest_info = {"name": display_name, "slug": slug, "lat": None, "lng": None, "rating": None, "reviews": None, "address": None, "photos": [], "photo_url": None}
        if slug and slug in PLACES_DATA:
            pdata = PLACES_DATA[slug]
            if "error" not in pdata:
                rest_info["lat"] = pdata.get("lat")
                rest_info["lng"] = pdata.get("lng")
                rest_info["address"] = pdata.get("address")
                # Only expose rating when backed by real reviews (>= 3).
                # Google Places returns rating=5 for unrated businesses.
                review_count = pdata.get("user_ratings_total") or 0
                if review_count >= 3 and pdata.get("rating"):
                    rest_info["rating"] = pdata["rating"]
                    rest_info["reviews"] = review_count

        if slug:
            # Clear the photos array — it contained Supabase CDN URLs from a
            # now-deleted Supabase project. All those URLs 403.
            rest_info["photos"] = []

            # Resolve photo_url from local static files ONLY.
            # Checks restaurant_images/{slug}/0.jpg, /1.jpg, and {slug}.jpg.
            # Returns None (no photo) if nothing exists on disk. The frontend
            # handles None gracefully (hides the image element via onError).
            rest_info["photo_url"] = _get_local_photo_url(slug)

        results.append(rest_info)
    return {"restaurants": results}

# ─── Dish Search Endpoints ───
class SearchRequest(BaseModel):
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    categories: Optional[List[str]] = None
    dietary: Optional[List[str]] = None
    query: Optional[str] = None
    limit: Optional[int] = 20
    # Caller's coordinates, used to rank by how far away the dish is.
    lat: Optional[float] = None
    lng: Optional[float] = None
    # "relevance" (semantic order), "price" (cheapest first), "distance" (nearest first).
    sort: Optional[str] = None


EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great circle distance in kilometres between two points.

    Calgary is flat and small enough that a planar approximation would do, but
    haversine costs nothing here and does not break if the index ever covers
    another city.
    """
    from math import radians, sin, cos, asin, sqrt
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def _restaurant_context(slug: Optional[str]) -> dict:
    """Name, address and coordinates for a restaurant slug.

    Every dish row carries this so a result can stand on its own, which is what
    lets a single dish be shared as a link.
    """
    if not slug:
        return {}
    place = PLACES_DATA.get(slug) or {}
    name = NAME_MAPPING.get(slug) or slug.replace("-", " ").replace("_", " ").title()
    ctx = {
        "restaurant": name,
        "restaurant_slug": slug,
        "address": place.get("address"),
        "lat": place.get("lat"),
        "lng": place.get("lng"),
    }
    if place.get("lat") is not None and place.get("lng") is not None:
        # Directions belong to Google Maps. Link out rather than rebuild a map.
        ctx["directions_url"] = (
            f"https://www.google.com/maps/dir/?api=1&destination={place['lat']},{place['lng']}"
        )
    return ctx


@app.get("/filter-options")
def get_filter_options():
    return {
        "categories": ["Food", "Drink", "Side", "Dessert", "Appetizer", "Pizza", "Salad", "Pasta", "Soup", "Bread"],
        "dietary_tags": ["vegan", "vegetarian", "gluten-free", "dairy-free", "nut-free", "halal", "kosher", "spicy"],
        "price_min": 0,
        "price_max": 200
    }

# The whole point of the product is comparing the same dish across restaurants,
# so a result set has to be long enough to read as a comparison rather than a
# single suggestion. Eight was too few to see a price spread.
MAX_SEARCH_RESULTS = 25

@app.post("/search-dishes")
def search_dishes(req: SearchRequest, request: Request):
    check_search_rate_limit(request)
    if req.limit is None or req.limit > MAX_SEARCH_RESULTS:
        req.limit = MAX_SEARCH_RESULTS

    candidates = []
    candidate_indices = []
    
    # 1. Hard filters
    for i, item in enumerate(MENU_INDEX):
        # Price
        price = item.get("price")
        if isinstance(price, str):
            try:
                p_str = price.replace('$', '').replace(',', '').strip()
                if '-' in p_str: p_str = p_str.split('-')[0].strip()
                price = float(p_str)
            except:
                price = None

        if price is not None and isinstance(price, (int, float)):
            if req.price_min is not None and price < req.price_min: continue
            if req.price_max is not None and price > req.price_max: continue
        else:
            # Exclude items with unknown price when price filter is active
            if req.price_min is not None or req.price_max is not None:
                continue
            
        # Category
        cat = item.get("category", "")
        if req.categories and len(req.categories) > 0:
            allowed = [c.lower() for c in req.categories]
            if cat.lower() not in allowed:
                continue
                
        # Dietary
        if req.dietary and len(req.dietary) > 0:
            item_tags = [str(t).lower() for t in item.get("dietary_info", [])]
            missing = False
            for d in req.dietary:
                if d.lower() not in item_tags:
                    missing = True
                    break
            if missing:
                continue
                
        candidates.append(item)
        candidate_indices.append(i)
        
    if not candidates:
        return {"dishes": []}
        
    final_dishes = []
    
    # 2. Semantic Search using RAG (if query exists)
    if req.query and req.query.strip() and MENU_EMBEDDINGS is not None:
        try:
            res = client.embeddings.create(
                input=req.query,
                model="text-embedding-3-large",
                dimensions=3072
            )
            q_vec = np.array(res.data[0].embedding)
            
            # Use matching embeddings layer
            cand_vecs = MENU_EMBEDDINGS[candidate_indices]
            similarities = np.dot(cand_vecs, q_vec)
            
            # Rank Top K
            limit = min(req.limit or 20, len(candidates))
            top_k_idx = similarities.argsort()[-limit:][::-1]
            
            for idx in top_k_idx:
                final_dishes.append(candidates[idx])
                
        except Exception as e:
            print(f"Embedding error: {e}", flush=True)
            final_dishes = candidates[:req.limit or 20]
    else:
        # Default ranking (top limit)
        np.random.seed(42) # Deterministic for no-query
        np.random.shuffle(candidates)
        final_dishes = candidates[:req.limit or 20]
        
    response_dishes = []
    for d in final_dishes:
        d_copy = dict(d)
        name = d_copy.get('name', '')
        desc = d_copy.get('description', '')
        
        if name:
            name = re.sub(r'^\d+[\.\)\-]\s*', '', name)
            name = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', name)
            name = re.sub(r'#+\s*', '', name)
            name = re.sub(r'\*{1,2}([^\*]*)\*{1,2}', r'\1', name)
            name = re.sub(r'_([^_]*)_', r'\1', name)
            name = re.sub(r'https?://\S+', '', name)
            name = re.sub(r'\[\$[\d\.]+\]', '', name)
            d_copy['name'] = re.sub(r'\s+', ' ', name).strip()
            
        if desc:
            desc = re.sub(r'^\d+[\.\)\-]\s*', '', desc)
            desc = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', desc)
            desc = re.sub(r'#+\s*', '', desc)
            desc = re.sub(r'\*{1,2}([^\*]*)\*{1,2}', r'\1', desc)
            desc = re.sub(r'_([^_]*)_', r'\1', desc)
            desc = re.sub(r'https?://\S+', '', desc)
            desc = re.sub(r'\[\$[\d\.]+\]', '', desc)
            d_copy['description'] = re.sub(r'\s+', ' ', desc).strip()
            
        # Each row carries its own restaurant, so a single dish can be read,
        # compared and shared without the surrounding list.
        d_copy.update(_restaurant_context(d_copy.get("restaurant_slug")))

        if req.lat is not None and req.lng is not None:
            r_lat, r_lng = d_copy.get("lat"), d_copy.get("lng")
            if r_lat is not None and r_lng is not None:
                d_copy["distance_km"] = round(
                    haversine_km(req.lat, req.lng, float(r_lat), float(r_lng)), 2
                )

        response_dishes.append(d_copy)

    def price_key(d):
        p = _parse_price(d.get('price'))
        if p is None or p <= 0:
            return float('inf')
        return p

    def distance_key(d):
        val = d.get('distance_km')
        return float('inf') if val is None else val

    sort = (req.sort or "").lower()
    if sort == "distance" and req.lat is not None and req.lng is not None:
        response_dishes.sort(key=distance_key)
    elif sort == "price":
        response_dishes.sort(key=price_key)
    elif sort == "relevance" and req.query:
        # Semantic order is whatever the embedding scoring produced, so leave it.
        pass
    else:
        # No query means no meaningful relevance order, so cheapest first is the
        # only ranking that helps. With a query, the caller asked for nothing in
        # particular, so keep the price ranking the app has always had.
        response_dishes.sort(key=price_key)

    try:
        ip = get_real_ip(request)
        log_event("search", ip, "/search-dishes", {"query": req.query or "", "has_filters": bool(req.categories or req.dietary or req.price_max or req.price_min)})
    except Exception:
        pass

    return {"dishes": response_dishes, "count": len(response_dishes), "sort": sort or "price"}


@app.get("/dish/{dish_id}")
def get_dish(dish_id: str, request: Request):
    """One dish, addressable by id, with no account and no app.

    This is what makes a result shareable. The person holding the phone sends a
    link and everyone else sees the dish, the price and where it is.
    """
    for item in MENU_INDEX:
        if item.get("id") == dish_id:
            dish = _clean_dish_text(dict(item))
            dish.update(_restaurant_context(dish.get("restaurant_slug")))
            try:
                log_event("dish_view", get_real_ip(request), "/dish", {"id": dish_id})
            except Exception:
                pass
            return {"dish": dish}
    raise HTTPException(status_code=404, detail="Dish not found")


# ─── Random dish (Hungry mode) ───
# A bar names only the brand and puts the spirit in the category, so
# "Johnny Walker Black" under "Scotch & Whiskey" matches no name keyword. The
# spirit words therefore have to live in the category list too.
NON_FOOD_CATEGORY_KEYWORDS = [
    "drink", "beverage", "wine", "beer", "cocktail",
    "liquor", "alcohol", "spirits", "juice", "soda",
    "coffee", "tea",
    "scotch", "whiskey", "whisky", "bourbon", "vodka", "gin", "rum",
    "tequila", "sake", "cider", "seltzer", "espresso", "latte", "smoothie",
]
# A pub files its espresso under a food category, so the name list has to carry
# the coffee words as well as the brands.
NON_FOOD_NAME_KEYWORDS = [
    "cabernet", "merlot", "pinot", "chardonnay", "sauvignon",
    "riesling", "malbec", "lager", "ipa", "pilsner", "stout", "ale",
    "rosé", "rose wine", "prosecco", "champagne",
    "tequila", "whiskey", "whisky", "vodka", "gin", "rum", "bourbon",
    "scotch", "espresso", "americano", "cappuccino", "latte", "macchiato",
]


DESSERT_KEYWORDS = [
    "dessert", "cake", "ice cream", "sweet", "pastry", "gelato",
    "sorbet", "pudding", "brownie", "tiramisu", "cheesecake", "cookie",
]
SIDE_KEYWORDS = ["side", "appetizer", "app", "starter", "salad", "fries"]


def is_food_dish(dish: dict) -> bool:
    """Return False for drinks / alcohol / other non-food items."""
    cat = (dish.get("category") or "").lower()
    name = (dish.get("name") or "").lower()
    if any(k in cat for k in NON_FOOD_CATEGORY_KEYWORDS):
        return False
    for k in NON_FOOD_NAME_KEYWORDS:
        if re.search(rf"\b{re.escape(k)}\b", name):
            return False
    return True


def is_drink_dish(dish: dict) -> bool:
    """Return True for drinks / beverages / alcohol."""
    return not is_food_dish(dish)


def matches_dish_type(dish: dict, dish_type: str) -> bool:
    """Filter a dish by the requested type (any, main, dessert, drink, side)."""
    if dish_type == "any":
        return is_food_dish(dish)
    cat = (dish.get("category") or "").lower()
    name = (dish.get("name") or "").lower()
    if dish_type == "main":
        return (
            is_food_dish(dish)
            and not any(k in cat or k in name for k in DESSERT_KEYWORDS)
            and not any(k in cat for k in SIDE_KEYWORDS)
        )
    if dish_type == "dessert":
        return any(k in cat or k in name for k in DESSERT_KEYWORDS)
    if dish_type == "drink":
        return is_drink_dish(dish)
    if dish_type == "side":
        return any(k in cat for k in SIDE_KEYWORDS)
    return is_food_dish(dish)


def _count_dishes_for_restaurant(slug: Optional[str]) -> int:
    """Count how many dishes in MENU_INDEX belong to the given restaurant slug.

    Used for honest fallback when chat opens a restaurant with no menu data.
    """
    if not slug:
        return 0
    return sum(1 for d in MENU_INDEX if d.get("restaurant_slug") == slug)


def _menu_is_empty(menu_json, slug: Optional[str] = None) -> bool:
    """True if the loaded menu has no usable dishes.

    Accepts the many shapes real menu files take: bare list, dict with
    'items'/'menu'/'dishes' key, or category-keyed dict of lists. Falls back
    to checking MENU_INDEX for the slug as a last resort.
    """
    if menu_json:
        if isinstance(menu_json, list):
            if len(menu_json) > 0:
                return False
        elif isinstance(menu_json, dict):
            for key in ("items", "menu", "dishes"):
                val = menu_json.get(key)
                if isinstance(val, list) and len(val) > 0:
                    return False
            for v in menu_json.values():
                if isinstance(v, list) and len(v) > 0:
                    return False
                if isinstance(v, dict) and v:
                    return False
    # Last resort: ask the flat dish index
    return _count_dishes_for_restaurant(slug) == 0


def _parse_price(val) -> Optional[float]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None
    try:
        s = str(val).replace("$", "").replace(",", "").strip()
        if "-" in s:
            s = s.split("-")[0].strip()
        p = float(s)
        return p if p > 0 else None
    except Exception:
        return None


def _clean_dish_text(d: dict) -> dict:
    """Strip markdown/links/numbering from dish name and description."""
    out = dict(d)
    for key in ("name", "description"):
        v = out.get(key, "") or ""
        if not v:
            continue
        v = re.sub(r"^\d+[\.\)\-]\s*", "", v)
        v = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", v)
        v = re.sub(r"#+\s*", "", v)
        v = re.sub(r"\*{1,2}([^\*]*)\*{1,2}", r"\1", v)
        v = re.sub(r"_([^_]*)_", r"\1", v)
        v = re.sub(r"https?://\S+", "", v)
        v = re.sub(r"\[\$[\d\.]+\]", "", v)
        out[key] = re.sub(r"\s+", " ", v).strip()
    return out


@app.get("/random-dish")
def random_dish(
    request: Request,
    max_price: Optional[float] = None,
    dish_type: str = "any",
):
    """Return a random dish filtered by type and optional max price.

    dish_type: any | main | dessert | drink | side
    """
    try:
        if not MENU_INDEX:
            raise HTTPException(status_code=404, detail="No dishes available")

        candidates = []
        for d in MENU_INDEX:
            p = _parse_price(d.get("price"))
            if p is None:
                continue
            if max_price is not None and p > max_price:
                continue
            if not matches_dish_type(d, dish_type):
                continue
            candidates.append(d)

        if not candidates:
            raise HTTPException(status_code=404, detail="No dishes found for that price")

        dish = _clean_dish_text(random.choice(candidates))

        try:
            ip = get_real_ip(request)
            log_event("random_dish", ip, "/random-dish", {"max_price": max_price})
        except Exception:
            pass

        return dish
    except HTTPException:
        raise
    except Exception as e:
        print(f"Random dish error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Something went wrong")


# ─── Category dishes (visual tile search) ───
@app.post("/category-dishes")
def category_dishes(req: SearchRequest, request: Request):
    """Semantic search by category name — thin wrapper around search_dishes."""
    req.limit = MAX_SEARCH_RESULTS
    return search_dishes(req, request)


# ─── Stats ───

# ─── Chat ───
class ChatMessage(BaseModel):
    role: str
    content: str



def resolve_display_name(slug_or_name: str) -> str:
    """Convert slug to display name."""
    if slug_or_name in RESTAURANT_LIST:
        return slug_or_name
    if slug_or_name in NAME_MAPPING:
        return NAME_MAPPING[slug_or_name]
    for display in RESTAURANT_LIST:
        if display.lower() == slug_or_name.lower():
            return display
    return slug_or_name


def _slug_for_restaurant(name_or_slug: str) -> str | None:
    """Resolve a restaurant name or slug to a slug."""
    if name_or_slug in NAME_MAPPING:
        return name_or_slug
    return REVERSE_MAPPING.get(name_or_slug.lower())












# ─── POST /chat/start ───



# ─── POST /chat (upgraded) ───



# ─── GET /chat/history ───



# ─── Restaurant photo proxy (Google Places) ───
import httpx

_photo_cache: dict[str, bytes] = {}

@app.get("/restaurant-photo/{slug}")
async def get_restaurant_photo(slug: str):
    """Proxy a Google Places photo for a restaurant.
    Uses the photo_reference from restaurant_photos.json and the
    GOOGLE_MAPS_API_KEY env var to fetch the image server-side.
    """
    from fastapi.responses import Response

    # Serve from in-memory cache if available
    if slug in _photo_cache:
        return Response(content=_photo_cache[slug], media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})

    # Check for static file first
    static_path = os.path.join(IMAGES_DIR, f"{slug}.jpg")
    if os.path.isfile(static_path):
        from fastapi.responses import FileResponse
        return FileResponse(static_path, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})

    # Look up photo reference
    photo_data = RESTAURANT_PHOTOS.get(slug)
    if not photo_data or not photo_data.get("photos"):
        raise HTTPException(status_code=404, detail="No photo available")

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Photo service unavailable")

    photo_ref = photo_data["photos"][0]["photo_reference"]
    url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={api_key}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client_http:
            resp = await client_http.get(url)
            resp.raise_for_status()
            img_bytes = resp.content
            # Cache in memory (limit to ~50MB)
            if len(_photo_cache) < 500:
                _photo_cache[slug] = img_bytes
            return Response(content=img_bytes, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch photo")

# ─── Serve static restaurant images ───
if os.path.isdir(IMAGES_DIR):
    from fastapi.staticfiles import StaticFiles as _StaticFiles
    app.mount("/restaurant-images", _StaticFiles(directory=IMAGES_DIR), name="restaurant-images")

# ─── Serve web frontend (static files) ───
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ─── Dish search front door ───
# The first thing a stranger sees is the search, with a real result already on
# screen and no account asked for. The Expo build stays reachable at /app.
FRONT_DIR = os.path.join(BASE_DIR, "front")
FRONT_INDEX = os.path.join(FRONT_DIR, "index.html")

if os.path.isfile(FRONT_INDEX):
    @app.get("/")
    def front_door():
        return FileResponse(FRONT_INDEX)

    @app.get("/d/{dish_id}")
    def shared_dish_page(dish_id: str):
        # Same page. It reads the id out of the path and opens on that dish.
        return FileResponse(FRONT_INDEX)

WEB_DIR = os.path.join(BASE_DIR, "web_dist")
if os.path.isdir(WEB_DIR):
    # Mount assets directly at /assets so the built HTML's /assets/*.js
    # references work when the SPA is served from the site root.
    assets_dir = os.path.join(WEB_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Keep /app/* working for backward compatibility (old screenshots,
    # bookmarks, social share links). StaticFiles(html=True) serves
    # index.html for the mount root.
    app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="app-legacy")

    # Serve index.html at root and for any unknown path (SPA catch-all).
    # Defined LAST so earlier exact API routes win.
    # Accepts both GET and HEAD so `curl -sI /` returns 200 (health-check
    # style pings and some monitors use HEAD).
    _API_PREFIXES = (
        "search-dishes", "random-dish", "category-dishes", "dish",
        "restaurants", "filter-options",
        "restaurant-images", "restaurant-photo", "health",
        "assets", "api",
    )

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(full_path: str):
        # Don't intercept API routes — let FastAPI's 404 handler handle them.
        if full_path.startswith(_API_PREFIXES):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = os.path.join(WEB_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(WEB_DIR, "index.html"))


