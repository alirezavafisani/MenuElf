import os
import json
import time
import glob
import re
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from typing import List, Optional

# Resolve paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENUS_DIR = os.environ.get("MENUS_DIR", os.path.join(BASE_DIR, "menus"))

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ─── User Intelligence router ───
from routers.user_intelligence import router as user_intelligence_router
app.include_router(user_intelligence_router)

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

# ─── Flat menu index ───
# ─── Flat menu index ───
import numpy as np

MENU_DB_FILE = os.path.join(BASE_DIR, "menu_db.json")
EMBEDDINGS_FILE = os.path.join(BASE_DIR, "menu_embeddings.npy")
MENU_INDEX: List[dict] = []
MENU_EMBEDDINGS: np.ndarray = None

def load_menu_index():
    global MENU_INDEX, MENU_EMBEDDINGS
    try:
        if os.path.isfile(MENU_DB_FILE):
            with open(MENU_DB_FILE, "r") as f:
                MENU_INDEX = json.load(f)
        else:
            MENU_INDEX = []
            
        if os.path.isfile(EMBEDDINGS_FILE):
            MENU_EMBEDDINGS = np.load(EMBEDDINGS_FILE, mmap_mode='r')
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
        rest_info = {"name": display_name, "slug": slug, "lat": None, "lng": None, "rating": None, "reviews": None, "address": None}
        if slug and slug in PLACES_DATA:
            pdata = PLACES_DATA[slug]
            if "error" not in pdata:
                rest_info["lat"] = pdata.get("lat")
                rest_info["lng"] = pdata.get("lng")
                rest_info["rating"] = pdata.get("rating")
                rest_info["reviews"] = pdata.get("user_ratings_total")
                rest_info["address"] = pdata.get("address")

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

@app.post("/search-dishes")
def search_dishes(req: SearchRequest):
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
    
    return {"dishes": response_dishes}

# ─── Chat ───
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    restaurant: str
    message: str
    history: List[ChatMessage] = []

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

@app.post("/chat")
def chat_with_menu(req: ChatRequest):
    # Try both slug and display name for menu loading
    menu_json = load_menu(req.restaurant)
    if menu_json is None:
        display = resolve_display_name(req.restaurant)
        menu_json = load_menu(display)
    if menu_json is None:
        raise HTTPException(status_code=404, detail=f"Restaurant '{req.restaurant}' not found")

    display_name = resolve_display_name(req.restaurant)

    system_prompt = (
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

    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages, temperature=0.4, max_tokens=500
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        print(f"OpenAI error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Error communicating with OpenAI")


