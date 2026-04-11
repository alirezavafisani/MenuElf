"""Lightweight test server for Playwright analytics tests.

Imports the real analytics module and exposes:
- GET /stats          — real stats from analytics.db
- POST /search-dishes — mock search that logs analytics events (cap 8)
- POST /category-dishes — same as search, capped at 8
- GET /random-dish    — random mock dish, filtered by max_price
- POST /chat          — mock chat that logs analytics events
- GET /restaurants    — mock restaurant list
- GET /filter-options — mock filter options
- GET /, /app, /app/  — serves the built React app from web/dist if present,
                        otherwise a minimal HTML shell for analytics tests.
"""
import os
import sys
import random
import tempfile

# Use a temporary DB for testing
TEST_DB = os.path.join(tempfile.gettempdir(), "menuelf_test_analytics.db")
os.environ["ANALYTICS_DB_PATH"] = TEST_DB
os.environ["ANALYTICS_SALT"] = "test-salt-playwright"

# Add backend to path so we can import the real analytics module
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "backend"))
WEB_DIST_DIR = os.path.normpath(os.path.join(HERE, "..", "dist"))
sys.path.insert(0, BACKEND_DIR)
from analytics import log_event, get_stats, init_db  # noqa: E402

from fastapi import FastAPI, Request, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.requests import Request as StarletteRequest  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from typing import List, Optional  # noqa: E402

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_real_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class AnalyticsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        try:
            path = request.url.path
            if path == "/" or path == "/app" or path == "/app/":
                log_event("page_view", get_real_ip(request), path)
        except Exception:
            pass
        return response


app.add_middleware(AnalyticsMiddleware)

MAX_SEARCH_RESULTS = 8

# --- Chunk 4 helpers: mirror the production food / empty-menu logic ---
NON_FOOD_CATEGORY_KEYWORDS = [
    "drink", "beverage", "wine", "beer", "cocktail",
    "liquor", "alcohol", "spirits", "juice", "soda",
    "coffee", "tea",
]
NON_FOOD_NAME_KEYWORDS = [
    "cabernet", "merlot", "pinot", "chardonnay", "sauvignon",
    "riesling", "malbec", "lager", "ipa", "pilsner", "stout", "ale",
    "rosé", "prosecco", "champagne",
    "tequila", "whiskey", "vodka", "gin", "rum", "bourbon",
]


def is_food_dish(dish: dict) -> bool:
    import re as _re
    cat = (dish.get("category") or "").lower()
    name = (dish.get("name") or "").lower()
    if any(k in cat for k in NON_FOOD_CATEGORY_KEYWORDS):
        return False
    for k in NON_FOOD_NAME_KEYWORDS:
        if _re.search(rf"\b{_re.escape(k)}\b", name):
            return False
    return True


# --- Mock data ---
# Includes deliberately non-food rows so the food-only filter can be tested.
MOCK_DISHES = [
    {"name": "Margherita Pizza", "price": 14.99, "description": "Classic tomato and mozzarella pizza with fresh basil.",
     "category": "Pizza", "restaurant_slug": "pizza-place", "restaurant_name": "Pizza Place",
     "dietary_info": ["vegetarian"]},
    # Non-food rows — should be rejected by is_food_dish (category match)
    {"name": "Glass of Cabernet", "price": 12.00, "description": "House red wine.",
     "category": "Wine", "restaurant_slug": "pizza-place", "restaurant_name": "Pizza Place",
     "dietary_info": []},
    {"name": "Pilsner Draft", "price": 8.00, "description": "Local pilsner on tap.",
     "category": "Beer", "restaurant_slug": "burger-joint", "restaurant_name": "Burger Joint",
     "dietary_info": []},
    {"name": "Iced Coffee", "price": 5.50, "description": "Cold brew with milk.",
     "category": "Beverage", "restaurant_slug": "burger-joint", "restaurant_name": "Burger Joint",
     "dietary_info": []},
    {"name": "Pepperoni Pizza", "price": 16.99, "description": "Loaded with spicy pepperoni.",
     "category": "Pizza", "restaurant_slug": "pizza-place", "restaurant_name": "Pizza Place",
     "dietary_info": []},
    {"name": "Veggie Burger", "price": 12.99, "description": "Plant-based patty with lettuce and tomato.",
     "category": "Food", "restaurant_slug": "burger-joint", "restaurant_name": "Burger Joint",
     "dietary_info": ["vegan"]},
    {"name": "Classic Cheeseburger", "price": 13.50, "description": "Beef patty with aged cheddar.",
     "category": "Food", "restaurant_slug": "burger-joint", "restaurant_name": "Burger Joint",
     "dietary_info": []},
    {"name": "Spicy Ramen", "price": 16.50, "description": "Hot and spicy noodle soup with pork belly.",
     "category": "Food", "restaurant_slug": "ramen-house", "restaurant_name": "Ramen House",
     "dietary_info": ["spicy"]},
    {"name": "Miso Ramen", "price": 15.00, "description": "Rich miso broth with soft-boiled egg.",
     "category": "Food", "restaurant_slug": "ramen-house", "restaurant_name": "Ramen House",
     "dietary_info": []},
    {"name": "Chicken Shawarma", "price": 11.50, "description": "Marinated chicken wrap with garlic sauce.",
     "category": "Food", "restaurant_slug": "shawarma-spot", "restaurant_name": "Shawarma Spot",
     "dietary_info": ["halal"]},
    {"name": "Pad Thai", "price": 13.00, "description": "Thai stir-fried rice noodles.",
     "category": "Food", "restaurant_slug": "thai-garden", "restaurant_name": "Thai Garden",
     "dietary_info": []},
    {"name": "Chicken Tikka Masala", "price": 15.50, "description": "Creamy tomato curry with tender chicken.",
     "category": "Food", "restaurant_slug": "curry-house", "restaurant_name": "Curry House",
     "dietary_info": ["indian"]},
    {"name": "Carbonara", "price": 17.00, "description": "Classic Roman pasta with eggs and guanciale.",
     "category": "Pasta", "restaurant_slug": "trattoria", "restaurant_name": "Trattoria",
     "dietary_info": []},
    {"name": "Fish Tacos", "price": 13.50, "description": "Fresh battered fish with slaw.",
     "category": "Food", "restaurant_slug": "taco-shop", "restaurant_name": "Taco Shop",
     "dietary_info": []},
    {"name": "Bibimbap", "price": 14.00, "description": "Korean rice bowl with vegetables and egg.",
     "category": "Food", "restaurant_slug": "korean-kitchen", "restaurant_name": "Korean Kitchen",
     "dietary_info": []},
    {"name": "Tiramisu", "price": 8.50, "description": "Classic Italian espresso dessert.",
     "category": "Dessert", "restaurant_slug": "trattoria", "restaurant_name": "Trattoria",
     "dietary_info": ["vegetarian"]},
    {"name": "Caesar Salad", "price": 9.99, "description": "Crisp romaine with parmesan and croutons.",
     "category": "Salad", "restaurant_slug": "salad-bar", "restaurant_name": "Salad Bar",
     "dietary_info": ["vegetarian"]},
]


class SearchRequest(BaseModel):
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    categories: Optional[List[str]] = None
    dietary: Optional[List[str]] = None
    query: Optional[str] = None
    limit: Optional[int] = 20


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    restaurant: str
    message: str
    history: List[ChatMessage] = []
    session_id: Optional[str] = None


def _filter_dishes(req: SearchRequest) -> list:
    results = MOCK_DISHES[:]
    if req.query:
        q = req.query.lower()
        filtered = [d for d in results if q in d["name"].lower() or q in d["description"].lower() or q in d.get("category", "").lower()]
        if filtered:
            results = filtered
    if req.dietary:
        results = [d for d in results if any(dt in d["dietary_info"] for dt in req.dietary)]
    if req.price_max is not None:
        results = [d for d in results if d["price"] <= req.price_max]
    if req.price_min is not None:
        results = [d for d in results if d["price"] >= req.price_min]
    return results


@app.get("/stats")
def stats_endpoint():
    return get_stats()


@app.get("/health")
def health():
    return {"status": "ok", "test_server": True}


@app.get("/filter-options")
def filter_options():
    return {
        "categories": ["Food", "Drink", "Pizza", "Salad", "Pasta", "Dessert"],
        "dietary_tags": ["vegan", "vegetarian", "gluten-free", "spicy", "halal"],
        "price_min": 0,
        "price_max": 200,
    }


@app.get("/restaurants")
def get_restaurants():
    uniq = {}
    for d in MOCK_DISHES:
        uniq[d["restaurant_slug"]] = d["restaurant_name"]
    return {
        "restaurants": [
            {
                "name": name,
                "slug": slug,
                "lat": 51.04 + (i * 0.01),
                "lng": -114.07 + (i * 0.01),
                "rating": 4.5,
                "reviews": 100 + i * 10,
                "address": f"{100 + i} Test St",
                "photos": [],
                "photo_url": None,
            }
            for i, (slug, name) in enumerate(uniq.items())
        ]
    }


@app.post("/search-dishes")
def search_dishes(req: SearchRequest, request: Request):
    # Enforce 8-result cap (matches real backend behaviour)
    if req.limit is None or req.limit > MAX_SEARCH_RESULTS:
        req.limit = MAX_SEARCH_RESULTS

    results = _filter_dishes(req)
    if not results:
        results = MOCK_DISHES[:2]
    results = results[: req.limit]

    try:
        log_event(
            "search",
            get_real_ip(request),
            "/search-dishes",
            {
                "query": req.query or "",
                "has_filters": bool(
                    req.categories or req.dietary or req.price_max or req.price_min
                ),
            },
        )
    except Exception:
        pass

    return {"dishes": results}


@app.post("/category-dishes")
def category_dishes(req: SearchRequest, request: Request):
    req.limit = MAX_SEARCH_RESULTS
    return search_dishes(req, request)


@app.get("/random-dish")
def random_dish(request: Request, max_price: Optional[float] = None):
    # Food-only filter (chunk 4): drop wine, beer, coffee, etc.
    candidates = [
        d for d in MOCK_DISHES
        if d.get("price") is not None and is_food_dish(d)
    ]
    if max_price is not None:
        candidates = [d for d in candidates if d["price"] <= max_price]
    if not candidates:
        raise HTTPException(status_code=404, detail="No dishes found")
    dish = random.choice(candidates)
    try:
        log_event("random_dish", get_real_ip(request), "/random-dish", {"max_price": max_price})
    except Exception:
        pass
    return dish


# Set of restaurant slugs that "exist" but have no menu data — used to
# exercise the chunk 4 empty-menu fallback in chat.
EMPTY_MENU_SLUGS = {"ghost-restaurant"}


@app.post("/chat")
def chat(req: ChatRequest, request: Request):
    try:
        log_event("chat", get_real_ip(request), "/chat", {"restaurant": req.restaurant})
    except Exception:
        pass

    # Empty-menu fallback (chunk 4) — mirrors backend/main.py behaviour.
    if req.restaurant in EMPTY_MENU_SLUGS:
        return {
            "reply": (
                f"I don't have {req.restaurant}'s menu loaded yet. "
                "Try searching for dishes on the main page, or check back soon."
            ),
            "session_id": None,
        }

    # Happy-path reply is intentionally plain text (no markdown) to validate
    # the chunk 4 A1 prompt rules in tests.
    return {
        "reply": (
            f"I recommend the Margherita Pizza for 14.99 — it's one of our "
            f"most popular dishes at {req.restaurant}. You could also try "
            f"the Pepperoni Pizza for 16.99 if you want something meatier."
        ),
        "session_id": None,
    }


# ─── Serve the React app from web/dist if it was built ───
# Mirrors the production backend/main.py layout so tests exercise the same
# routing: SPA at root, legacy /app/* mount, API routes excluded from catch-all.
if os.path.isdir(WEB_DIST_DIR):
    assets_dir = os.path.join(WEB_DIST_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Legacy /app/* — backward-compat for old bookmarks
    app.mount("/app", StaticFiles(directory=WEB_DIST_DIR, html=True), name="app-legacy")

    _TEST_API_PREFIXES = (
        "search-dishes", "random-dish", "category-dishes",
        "chat", "restaurants", "filter-options", "stats",
        "health", "assets",
    )

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    def serve_spa(full_path: str):
        if full_path.startswith(_TEST_API_PREFIXES):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = os.path.join(WEB_DIST_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(WEB_DIST_DIR, "index.html"))
else:
    # Fallback minimal shell (no React build present)
    STATS_SHELL = """
<!DOCTYPE html>
<html><head><title>MenuElf Test</title></head>
<body>
<div id="search"><input id="search-input" placeholder="search" /><button id="search-btn" onclick="doSearch()">Search</button><div id="results"></div></div>
<footer><div id="stats-counter"></div></footer>
<script>
async function loadStats(){try{const r=await fetch('/stats');const s=await r.json();const el=document.getElementById('stats-counter');if(s.total_visitors>0){el.innerHTML='<span data-testid=\"stats-text\">'+s.total_searches.toLocaleString()+' dishes served to '+s.total_visitors.toLocaleString()+' hungry '+(s.total_visitors===1?'Calgarian':'Calgarians')+(s.weekly_visitors>0?' · '+s.weekly_visitors+' this week':'')+'</span>';}}catch(e){}}
async function doSearch(){const q=document.getElementById('search-input').value;const r=await fetch('/search-dishes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q,limit:20})});const d=await r.json();document.getElementById('results').innerHTML=d.dishes.map(x=>'<div class=\"dish-card\" data-slug=\"'+x.restaurant_slug+'\"><strong>'+x.name+'</strong> - $'+x.price+' <button class=\"chat-btn\" onclick=\"openChat(\\''+x.restaurant_slug+'\\',\\''+x.restaurant_name+'\\')\">Chat</button></div>').join('');loadStats();}
async function openChat(s,n){await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({restaurant:s,message:'Hi!',history:[]})});loadStats();}
loadStats();
</script>
</body></html>
"""

    @app.get("/")
    def root_redirect_shell():
        return RedirectResponse(url="/app/")

    @app.get("/app")
    @app.get("/app/")
    def serve_app_shell():
        return HTMLResponse(STATS_SHELL)


if __name__ == "__main__":
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    try:
        init_db()
    except Exception as e:
        print(f"init_db failed: {e}", flush=True)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
