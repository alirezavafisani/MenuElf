import os
import json
import time
import glob
import re
import random
from collections import defaultdict
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from analytics import log_event, get_stats
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

# ─── Simple IP-based rate limiter for /chat ───
_chat_rate_limits: dict[str, list[float]] = defaultdict(list)
CHAT_RATE_LIMIT = 30  # requests per hour
CHAT_RATE_WINDOW = 3600  # 1 hour in seconds

def check_chat_rate_limit(request: Request):
    ip = get_real_ip(request)
    now = time.time()
    _chat_rate_limits[ip] = [t for t in _chat_rate_limits[ip] if now - t < CHAT_RATE_WINDOW]
    if len(_chat_rate_limits[ip]) >= CHAT_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    _chat_rate_limits[ip].append(now)

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

# ─── User Intelligence router ───
from routers.user_intelligence import router as user_intelligence_router
app.include_router(user_intelligence_router)

# ─── Friends router ───
from routers.friends import router as friends_router
app.include_router(friends_router)

# ─── Group Dining router ───
from routers.group_dining import router as group_dining_router
app.include_router(group_dining_router)

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
        filenames = [f.replace(".json", "") for f in os.listdir(MENUS_DIR) 
                     if f.endswith(".json") and f != "_conversion_log.json"]
        for slug in filenames:
            NAME_MAPPING[slug] = slug.replace("-", " ").replace("_", " ").title()
    REVERSE_MAPPING = {v.lower(): k for k, v in NAME_MAPPING.items()}
    return sorted(NAME_MAPPING.values())

RESTAURANT_LIST = get_restaurant_names()
print(f"Found {len(RESTAURANT_LIST)} restaurants", flush=True)

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

load_menu_index()

# ─── Places Data ───
PLACES_DATA_FILE = os.path.join(BASE_DIR, "restaurant_places_data.json")
PLACES_DATA = {}

def load_places_data():
    global PLACES_DATA
    if os.path.isfile(PLACES_DATA_FILE):
        with open(PLACES_DATA_FILE, "r", encoding="utf-8") as f:
            PLACES_DATA = json.load(f)
        print(f"Loaded places data for {len(PLACES_DATA)} restaurants", flush=True)

load_places_data()

# ─── Photo URLs ───
PHOTO_URLS_FILE = os.path.join(BASE_DIR, "restaurant_photo_urls.json")
PHOTO_URLS: dict[str, list[str]] = {}

def load_photo_urls():
    global PHOTO_URLS
    if os.path.isfile(PHOTO_URLS_FILE):
        with open(PHOTO_URLS_FILE, "r", encoding="utf-8") as f:
            PHOTO_URLS = json.load(f)
        print(f"Loaded photo URLs for {len(PHOTO_URLS)} restaurants", flush=True)

load_photo_urls()

# ─── Restaurant Photos (Google Places references + Foursquare static) ───
RESTAURANT_PHOTOS_FILE = os.path.join(BASE_DIR, "restaurant_photos.json")
RESTAURANT_PHOTOS: dict[str, dict] = {}

def load_restaurant_photos():
    global RESTAURANT_PHOTOS
    if os.path.isfile(RESTAURANT_PHOTOS_FILE):
        with open(RESTAURANT_PHOTOS_FILE, "r", encoding="utf-8") as f:
            RESTAURANT_PHOTOS = json.load(f)
        print(f"Loaded photo references for {len(RESTAURANT_PHOTOS)} restaurants", flush=True)

load_restaurant_photos()

# Static images directory (for Foursquare-scraped photos)
IMAGES_DIR = os.path.join(BASE_DIR, "restaurant_images")
PHOTO_MANIFEST_FILE = os.path.join(BASE_DIR, "restaurant_images_manifest.json")
PHOTO_MANIFEST: dict[str, str] = {}
if os.path.isfile(PHOTO_MANIFEST_FILE):
    with open(PHOTO_MANIFEST_FILE, "r") as f:
        PHOTO_MANIFEST = json.load(f)
    print(f"Loaded photo manifest with {len(PHOTO_MANIFEST)} entries", flush=True)

# ─── Endpoints ───
@app.get("/health")
def health_check():
    return {"status": "ok", "restaurants_loaded": len(RESTAURANT_LIST), "menu_items_indexed": len(MENU_INDEX)}

@app.get("/restaurants")
def get_restaurants(q: str = "", x_user_id: str = Header(default="")):
    q = q.lower().strip()
    load_places_data()

    # If a user ID is provided, try to load their taste profile for personalization
    user_profile = None
    items_by_slug: dict = {}
    if x_user_id:
        try:
            from routers.user_intelligence import _get_supabase
            sb = _get_supabase()
            profile_result = sb.table("user_taste_profiles").select("*").eq("id", x_user_id).execute()
            if profile_result.data:
                user_profile = profile_result.data[0]
                # Pre-group menu items by slug for O(n) lookup
                for item in MENU_INDEX:
                    s = item.get("restaurant_slug")
                    if s:
                        items_by_slug.setdefault(s, []).append(item)
        except Exception:
            pass  # Silently fall back to anonymous mode

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
                rest_info["rating"] = pdata.get("rating")
                rest_info["reviews"] = pdata.get("user_ratings_total")
                rest_info["address"] = pdata.get("address")

        if slug:
            rest_info["photos"] = PHOTO_URLS.get(slug, [])
            # Prefer static Foursquare image, fall back to Google Places proxy
            if slug in PHOTO_MANIFEST:
                rest_info["photo_url"] = f"/restaurant-images/{PHOTO_MANIFEST[slug]}"
            elif slug in RESTAURANT_PHOTOS and RESTAURANT_PHOTOS[slug].get("photos"):
                rest_info["photo_url"] = f"/restaurant-photo/{slug}"

        # Enrich with personalization if user profile is available
        if user_profile and slug:
            try:
                from engines.restaurant_scorer import (
                    get_cached_signature,
                    score_restaurant_for_user,
                    find_top_dish_for_user,
                )
                menu_items = items_by_slug.get(slug, [])
                sig = get_cached_signature(slug, menu_items)
                rest_info["match_score"] = score_restaurant_for_user(user_profile, sig)
                rest_info["top_dish"] = find_top_dish_for_user(user_profile, menu_items, sig)
            except Exception:
                pass  # Skip personalization on error

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

@app.get("/filter-options")
def get_filter_options():
    return {
        "categories": ["Food", "Drink", "Side", "Dessert", "Appetizer", "Pizza", "Salad", "Pasta", "Soup", "Bread"],
        "dietary_tags": ["vegan", "vegetarian", "gluten-free", "dairy-free", "nut-free", "halal", "kosher", "spicy"],
        "price_min": 0,
        "price_max": 200
    }

MAX_SEARCH_RESULTS = 8

@app.post("/search-dishes")
def search_dishes(req: SearchRequest, request: Request):
    # Quality over quantity: cap at MAX_SEARCH_RESULTS
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
            
        response_dishes.append(d_copy)
        
    def sort_key(d):
        val = d.get('price')
        if val is None or val == "":
            return float('inf')
        try:
            if isinstance(val, str):
                p_str = val.replace('$', '').replace(',', '').strip()
                if '-' in p_str: p_str = p_str.split('-')[0].strip()
                p = float(p_str)
            else:
                p = float(val)
            if p <= 0: return float('inf')
            return p
        except:
            return float('inf')

    response_dishes.sort(key=sort_key)

    try:
        ip = get_real_ip(request)
        log_event("search", ip, "/search-dishes", {"query": req.query or "", "has_filters": bool(req.categories or req.dietary or req.price_max or req.price_min)})
    except Exception:
        pass

    return {"dishes": response_dishes}


# ─── Random dish (Hungry mode) ───
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
def random_dish(request: Request, max_price: Optional[float] = None):
    """Return a random dish, optionally filtered by max price."""
    try:
        if not MENU_INDEX:
            raise HTTPException(status_code=404, detail="No dishes available")

        if max_price is not None:
            candidates = []
            for d in MENU_INDEX:
                p = _parse_price(d.get("price"))
                if p is not None and p <= max_price:
                    candidates.append(d)
        else:
            candidates = [d for d in MENU_INDEX if _parse_price(d.get("price")) is not None]

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
@app.get("/stats")
def stats_endpoint():
    return get_stats()

# ─── Chat ───
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    restaurant: str
    message: str
    history: List[ChatMessage] = []
    session_id: Optional[str] = None

class ChatStartRequest(BaseModel):
    restaurant_slug: str

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


def _build_generic_system_prompt(display_name: str, menu_json) -> str:
    return (
        f"You are a warm, knowledgeable food assistant for {display_name}. "
        f"Below is the restaurant's FULL MENU in JSON.\n\n"
        f"MENU JSON:\n{json.dumps(menu_json)}\n\n"
        "YOUR GUIDELINES:\n"
        "- You should answer ANY food-related question: ingredients, sauces, spiciness levels, "
        "dietary info, cuisine style, cooking methods, pairing suggestions, allergens, "
        "what's good for kids, what's vegetarian, comparisons between dishes, etc.\n"
        "- Use general culinary knowledge to fill in gaps.\n"
        "- When recommending or mentioning a specific menu item, ALWAYS include its price.\n"
        "- NEVER invent a dish name that isn't on this menu.\n"
        "- Be concise (2-3 sentences) unless the user asks for more detail.\n"
        "- Only decline questions completely unrelated to food or dining.\n"
    )


def _build_personalized_system_prompt(
    display_name: str,
    menu_json,
    profile_narration: str,
    recommendations_text: str,
    avoid_text: str,
) -> str:
    parts = [
        f"You are MenuElf, a knowledgeable and friendly dining concierge for {display_name}.\n\n",
        f"MENU:\n{json.dumps(menu_json)}\n\n",
        f"ABOUT THIS DINER:\n{profile_narration}\n\n",
        f"YOUR TOP RECOMMENDATIONS FOR THEM:\n{recommendations_text}\n\n",
    ]
    if avoid_text:
        parts.append(f"DISHES TO AVOID SUGGESTING:\n{avoid_text}\n\n")
    parts.append(
        "GUIDELINES:\n"
        "- Be warm, enthusiastic, and conversational\n"
        "- Lead with your recommendations if this is the start of the conversation\n"
        "- If they ask for something different, adapt but keep their preferences in mind\n"
        "- Never suggest dishes that conflict with their dietary restrictions\n"
        "- When mentioning a dish, include its price naturally\n"
        "- Keep responses concise (2-3 sentences for simple questions, more for comparisons)\n"
        "- Do NOT mention that you have their \"taste profile\" or \"data\" — just naturally know their preferences like a friend would\n"
        "- NEVER invent a dish name that isn't on this menu\n"
    )
    return "".join(parts)


def _get_personalization_context(user_id: str, restaurant_slug: str) -> dict | None:
    """Fetch taste profile and compute recommendations for a user + restaurant.

    Returns a dict with keys: narration, recommendations_text, avoid_text, top_dishes.
    Returns None if no profile is found.
    """
    try:
        from routers.user_intelligence import _get_supabase
        from engines.restaurant_scorer import (
            get_cached_signature,
            find_top_n_dishes_for_user,
            find_avoid_dishes,
        )
        from engines.profile_narrator import (
            narrate_profile,
            format_recommendations,
            format_avoid_list,
        )

        sb = _get_supabase()
        result = sb.table("user_taste_profiles").select("*").eq("id", user_id).execute()
        if not result.data:
            return None
        profile = result.data[0]

        menu_items = [item for item in MENU_INDEX if item.get("restaurant_slug") == restaurant_slug]
        sig = get_cached_signature(restaurant_slug, menu_items)

        top_dishes = find_top_n_dishes_for_user(profile, menu_items, n=3)
        avoid_dishes = find_avoid_dishes(profile, menu_items)

        return {
            "narration": narrate_profile(profile),
            "recommendations_text": format_recommendations(top_dishes, profile),
            "avoid_text": format_avoid_list(avoid_dishes),
            "top_dishes": top_dishes,
            "profile": profile,
        }
    except Exception:
        return None


def _run_chat_extraction_if_needed(user_id: str, session_messages: list[dict], supabase_client):
    """Trigger preference engine chat extraction if 3+ user messages."""
    user_count = sum(1 for m in session_messages if m.get("role") == "user")
    if user_count >= 3:
        try:
            from engines.preference_engine import process_and_update_profile
            process_and_update_profile(
                user_id,
                "chat_message",
                {"messages": session_messages, "session_ended": False},
                supabase_client,
            )
        except Exception:
            pass


def _store_session_message(session_id: str, role: str, content: str, supabase_client) -> list[dict]:
    """Append a message to a chat session and return the updated messages list."""
    try:
        result = supabase_client.table("chat_sessions").select("messages").eq("id", session_id).execute()
        if not result.data:
            return []
        messages = result.data[0].get("messages", [])
        if not isinstance(messages, list):
            messages = []
        messages.append({"role": role, "content": content})
        supabase_client.table("chat_sessions").upsert({
            "id": session_id,
            "messages": messages,
        }).execute()
        return messages
    except Exception:
        return []


# ─── POST /chat/start ───

@app.post("/chat/start")
def chat_start(req: ChatStartRequest, x_user_id: str = Header(default="")):
    slug = req.restaurant_slug
    display_name = NAME_MAPPING.get(slug, slug.replace("-", " ").title())

    menu_json = load_menu(display_name)
    if menu_json is None:
        menu_json = load_menu(slug)

    session_id = None
    personalization = None

    if x_user_id:
        personalization = _get_personalization_context(x_user_id, slug)

        # Create a chat session
        try:
            from routers.user_intelligence import _get_supabase
            sb = _get_supabase()
            session_result = sb.table("chat_sessions").insert({
                "user_id": x_user_id,
                "restaurant_slug": slug,
                "messages": [],
            }).execute()
            if session_result.data:
                session_id = session_result.data[0]["id"]
        except Exception:
            pass

    if personalization and menu_json:
        system_prompt = _build_personalized_system_prompt(
            display_name,
            menu_json,
            personalization["narration"],
            personalization["recommendations_text"],
            personalization["avoid_text"],
        )
        user_prompt = "Hi! I just opened the menu. What do you recommend for me?"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini", messages=messages, temperature=0.4, max_tokens=500
            )
            reply = response.choices[0].message.content

            # Store the assistant greeting in the session
            if session_id:
                try:
                    from routers.user_intelligence import _get_supabase
                    sb = _get_supabase()
                    _store_session_message(session_id, "assistant", reply, sb)
                except Exception:
                    pass

            return {"reply": reply, "session_id": session_id}
        except Exception as e:
            print(f"OpenAI error: {e}", flush=True)

    # Fallback: generic welcome
    generic_reply = (
        f"Welcome to {display_name}! I know every dish on this menu. "
        "What are you in the mood for?"
    )

    if session_id:
        try:
            from routers.user_intelligence import _get_supabase
            sb = _get_supabase()
            _store_session_message(session_id, "assistant", generic_reply, sb)
        except Exception:
            pass

    return {"reply": generic_reply, "session_id": session_id}


# ─── POST /chat (upgraded) ───

@app.post("/chat")
def chat_with_menu(
    req: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    x_user_id: str = Header(default=""),
):
    check_chat_rate_limit(request)
    # Try both slug and display name for menu loading
    menu_json = load_menu(req.restaurant)
    if menu_json is None:
        display = resolve_display_name(req.restaurant)
        menu_json = load_menu(display)
    if menu_json is None:
        raise HTTPException(status_code=404, detail=f"Restaurant '{req.restaurant}' not found")

    display_name = resolve_display_name(req.restaurant)
    slug = _slug_for_restaurant(req.restaurant)

    # Build system prompt — personalized if user_id present
    personalization = None
    if x_user_id and slug:
        personalization = _get_personalization_context(x_user_id, slug)

    if personalization:
        system_prompt = _build_personalized_system_prompt(
            display_name,
            menu_json,
            personalization["narration"],
            personalization["recommendations_text"],
            personalization["avoid_text"],
        )
    else:
        system_prompt = _build_generic_system_prompt(display_name, menu_json)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages, temperature=0.4, max_tokens=500
        )
        reply = response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Error communicating with OpenAI")

    try:
        client_ip = get_real_ip(request)
        log_event("chat", client_ip, "/chat", {"restaurant": req.restaurant})
    except Exception:
        pass

    # Store messages in session and trigger extraction if needed
    session_id = req.session_id
    if x_user_id and session_id:
        try:
            from routers.user_intelligence import _get_supabase
            sb = _get_supabase()
            _store_session_message(session_id, "user", req.message, sb)
            updated_msgs = _store_session_message(session_id, "assistant", reply, sb)

            background_tasks.add_task(
                _run_chat_extraction_if_needed, x_user_id, updated_msgs, sb,
            )
        except Exception:
            pass

    return {"reply": reply, "session_id": session_id}


# ─── GET /chat/history ───

@app.get("/chat/history/{restaurant_slug}")
def get_chat_history(restaurant_slug: str, x_user_id: str = Header(default="")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing x-user-id header")
    try:
        from routers.user_intelligence import _get_supabase
        sb = _get_supabase()
        result = (
            sb.table("chat_sessions")
            .select("*")
            .eq("user_id", x_user_id)
            .eq("restaurant_slug", restaurant_slug)
            .order("created_at", desc=True)
            .execute()
        )
        return {"sessions": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chat history: {e}")


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
from fastapi.responses import FileResponse, RedirectResponse

WEB_DIR = os.path.join(BASE_DIR, "web_dist")
if os.path.isdir(WEB_DIR):
    # Redirect root to /app/
    @app.get("/")
    async def root_redirect():
        return RedirectResponse(url="/app/")

    # Serve static assets (JS, CSS, images)
    app.mount("/app/assets", StaticFiles(directory=os.path.join(WEB_DIR, "assets")), name="web-assets")

    # Catch-all for SPA routes under /app
    @app.get("/app/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(WEB_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(WEB_DIR, "index.html"))

    @app.get("/app")
    async def serve_app_root():
        return FileResponse(os.path.join(WEB_DIR, "index.html"))


