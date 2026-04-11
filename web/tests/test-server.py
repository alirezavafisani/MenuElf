"""Lightweight test server for Playwright analytics tests.

Imports the real analytics module and exposes:
- GET /stats        — real stats from analytics.db
- POST /search-dishes — mock search that logs analytics events
- POST /chat        — mock chat that logs analytics events
- GET /app, GET /app/ — serves a minimal HTML page with StatsCounter-like footer
- GET /              — redirects to /app/
"""
import os
import sys
import json
import tempfile

# Use a temporary DB for testing
TEST_DB = os.path.join(tempfile.gettempdir(), "menuelf_test_analytics.db")
os.environ["ANALYTICS_DB_PATH"] = TEST_DB
os.environ["ANALYTICS_SALT"] = "test-salt-playwright"

# Add backend to path so we can import analytics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from analytics import log_event, get_stats, init_db

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from pydantic import BaseModel
from typing import List, Optional

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
                ip = request.client.host if request.client else "unknown"
                log_event("page_view", ip, path)
        except Exception:
            pass
        return response


app.add_middleware(AnalyticsMiddleware)

# --- Mock data ---
MOCK_DISHES = [
    {"name": "Margherita Pizza", "price": 14.99, "description": "Classic pizza", "category": "Pizza",
     "restaurant_slug": "pizza-place", "restaurant_name": "Pizza Place", "dietary_info": []},
    {"name": "Veggie Burger", "price": 12.99, "description": "Plant-based burger", "category": "Food",
     "restaurant_slug": "burger-joint", "restaurant_name": "Burger Joint", "dietary_info": ["vegan"]},
    {"name": "Spicy Ramen", "price": 16.50, "description": "Hot and spicy noodle soup", "category": "Food",
     "restaurant_slug": "ramen-house", "restaurant_name": "Ramen House", "dietary_info": ["spicy"]},
    {"name": "Caesar Salad", "price": 9.99, "description": "Crisp romaine with dressing", "category": "Salad",
     "restaurant_slug": "salad-bar", "restaurant_name": "Salad Bar", "dietary_info": ["vegetarian"]},
    {"name": "Fish Tacos", "price": 13.50, "description": "Fresh fish tacos", "category": "Food",
     "restaurant_slug": "taco-shop", "restaurant_name": "Taco Shop", "dietary_info": []},
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


@app.get("/stats")
def stats_endpoint():
    return get_stats()


@app.get("/health")
def health():
    return {"status": "ok", "test_server": True}


@app.get("/filter-options")
def filter_options():
    return {
        "categories": ["Food", "Drink", "Pizza", "Salad"],
        "dietary_tags": ["vegan", "vegetarian", "gluten-free", "spicy"],
        "price_min": 0,
        "price_max": 200,
    }


@app.get("/restaurants")
def get_restaurants():
    return {"restaurants": [
        {"name": "Pizza Place", "slug": "pizza-place", "lat": 51.0447, "lng": -114.0719,
         "rating": 4.5, "reviews": 120, "address": "123 Main St", "photos": [], "photo_url": None},
        {"name": "Burger Joint", "slug": "burger-joint", "lat": 51.0450, "lng": -114.0700,
         "rating": 4.2, "reviews": 85, "address": "456 1st Ave", "photos": [], "photo_url": None},
        {"name": "Ramen House", "slug": "ramen-house", "lat": 51.0460, "lng": -114.0680,
         "rating": 4.7, "reviews": 200, "address": "789 2nd St", "photos": [], "photo_url": None},
    ]}


@app.post("/search-dishes")
def search_dishes(req: SearchRequest, request: Request):
    results = MOCK_DISHES[:]
    if req.query:
        q = req.query.lower()
        results = [d for d in results if q in d["name"].lower() or q in d["description"].lower()]
    if req.dietary:
        results = [d for d in results if any(dt in d["dietary_info"] for dt in req.dietary)]
    if req.price_max is not None:
        results = [d for d in results if d["price"] <= req.price_max]
    if not results:
        results = MOCK_DISHES[:2]

    try:
        ip = request.client.host if request.client else "unknown"
        log_event("search", ip, "/search-dishes", {"query": req.query or "", "has_filters": bool(req.categories or req.dietary or req.price_max or req.price_min)})
    except Exception:
        pass

    return {"dishes": results[:req.limit or 20]}


@app.post("/chat")
def chat(req: ChatRequest, request: Request):
    try:
        ip = request.client.host if request.client else "unknown"
        log_event("chat", ip, "/chat", {"restaurant": req.restaurant})
    except Exception:
        pass
    return {"reply": f"Great choice! I recommend the Margherita Pizza at {req.restaurant}. It's our most popular dish!", "session_id": None}


STATS_COUNTER_HTML = """
<!DOCTYPE html>
<html>
<head><title>MenuElf Test</title></head>
<body>
  <div id="root">
    <section id="search" style="padding:20px">
      <input id="search-input" type="text" placeholder="What are you craving?" />
      <button id="search-btn" onclick="doSearch()">Search</button>
      <div id="results"></div>
    </section>
    <footer id="about" style="padding:20px;text-align:center">
      <div id="stats-counter"></div>
      <p>MenuElf - AI Restaurant Discovery</p>
    </footer>
  </div>
  <script>
    async function loadStats() {
      try {
        const r = await fetch('/stats');
        const s = await r.json();
        const el = document.getElementById('stats-counter');
        if (s.total_visitors > 0) {
          el.innerHTML = '<span data-testid="stats-text">' +
            s.total_searches.toLocaleString() + ' dishes served to ' +
            s.total_visitors.toLocaleString() + ' hungry Calgarians' +
            (s.weekly_visitors > 0 ? ' <span class="text-accent"> &middot; ' + s.weekly_visitors + ' this week</span>' : '') +
            '</span>';
        }
      } catch(e) {}
    }
    async function doSearch() {
      const q = document.getElementById('search-input').value;
      const r = await fetch('/search-dishes', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({query: q, limit: 20})
      });
      const data = await r.json();
      const el = document.getElementById('results');
      el.innerHTML = data.dishes.map(d =>
        '<div class="dish-card" data-slug="' + d.restaurant_slug + '">' +
        '<strong>' + d.name + '</strong> - $' + d.price +
        ' <button class="chat-btn" onclick="openChat(\\'' + d.restaurant_slug + '\\',\\'' + d.restaurant_name + '\\')">Chat</button>' +
        '</div>'
      ).join('');
      loadStats();
    }
    async function openChat(slug, name) {
      const r = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({restaurant: slug, message: 'Hi! What do you recommend?', history: []})
      });
      const data = await r.json();
      alert('Chat: ' + data.reply);
      loadStats();
    }
    loadStats();
  </script>
</body>
</html>
"""

@app.get("/")
def root_redirect():
    return RedirectResponse(url="/app/")

@app.get("/app")
@app.get("/app/")
def serve_app():
    return HTMLResponse(STATS_COUNTER_HTML)


if __name__ == "__main__":
    # Clean up old test DB
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
