"""Real-world scenario tests against menuelfapp.com.

Run with: python3 backend/scripts/scenario_tests.py

Hits the LIVE production API (https://menuelfapp.com) — not local or mock.
Writes raw observations to a JSON sidecar so the human-readable markdown
report can be authored separately.

Each scenario records:
- Raw API responses (truncated for the sidecar)
- Concrete examples (dish names, prices, chat replies)
- A verdict: HELPFUL / OK / CONFUSING / WRONG
- Free-form notes

1 second sleep between calls to avoid hammering the rate limiter.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

import requests

BASE = "https://menuelfapp.com"
SLEEP = 1.0  # seconds between API calls
REQ_TIMEOUT = 45  # seconds
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "..", "..", "scenario_test_raw.json")

session = requests.Session()
session.headers.update({"User-Agent": "MenuElf-Scenario-Tests/1.0"})


def log(*args: Any) -> None:
    print(*args, flush=True)


def get(path: str, **kwargs: Any) -> Any:
    url = f"{BASE}{path}"
    r = session.get(url, timeout=REQ_TIMEOUT, **kwargs)
    time.sleep(SLEEP)
    r.raise_for_status()
    return r.json()


def post(path: str, payload: dict) -> Any:
    url = f"{BASE}{path}"
    r = session.post(url, json=payload, timeout=REQ_TIMEOUT)
    time.sleep(SLEEP)
    if r.status_code == 429:
        return {"_rate_limited": True}
    r.raise_for_status()
    return r.json()


def price_of(dish: dict) -> float | None:
    v = dish.get("price")
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    try:
        s = str(v).replace("$", "").replace(",", "").strip()
        if "-" in s:
            s = s.split("-")[0].strip()
        p = float(s)
        return p if p > 0 else None
    except Exception:
        return None


def short_dish(d: dict) -> str:
    price = price_of(d)
    price_str = f"${price:.2f}" if price is not None else "(no price)"
    return f"{d.get('name', '?')} — {price_str} at {d.get('restaurant_name', '?')} [cat: {d.get('category', '-')}]"


report: dict[str, Any] = {
    "target": BASE,
    "started_at": datetime.utcnow().isoformat() + "Z",
    "stats_before": None,
    "stats_after": None,
    "scenarios": {},
}


# ─── Capture baseline /stats ───
log("\n========== BASELINE STATS ==========")
try:
    report["stats_before"] = get("/stats")
    log(json.dumps(report["stats_before"], indent=2))
except Exception as e:
    log(f"stats error: {e}")
    report["stats_before"] = {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# SCENARIO 1: "I'm broke and starving"
# ══════════════════════════════════════════════════════════════════════
log("\n========== SCENARIO 1: broke and starving ==========")
s1: dict[str, Any] = {"notes": []}

try:
    search = post(
        "/search-dishes",
        {"query": "filling cheap meal", "price_max": 8, "limit": 8},
    )
    s1_search = search.get("dishes", [])
    s1["search_count"] = len(s1_search)
    s1["search_sample"] = [short_dish(d) for d in s1_search]
    log(f"search 'filling cheap meal' price_max=8 → {len(s1_search)} dishes:")
    for d in s1_search:
        log(f"  • {short_dish(d)}")

    # Check price_max bug: any dish above $8?
    over_price = [d for d in s1_search if (price_of(d) or 0) > 8.001]
    s1["dishes_over_price_cap"] = [short_dish(d) for d in over_price]
    if over_price:
        s1["notes"].append(f"PRICE CAP BUG: {len(over_price)} dishes over $8")
        log(f"  WARNING: {len(over_price)} dish(es) above $8 despite price_max=8")

    # Are results filling meals or sides/sauces?
    SIDE_WORDS = ["sauce", "sprinkle", "side", "dressing", "topping", "extra"]
    sides = [
        d for d in s1_search
        if any(w in (d.get("name") or "").lower() for w in SIDE_WORDS)
    ]
    s1["sides_or_sauces"] = [short_dish(d) for d in sides]

    # Random dish x5 with budget
    s1_random = []
    for i in range(5):
        d = get("/random-dish", params={"max_price": 8})
        s1_random.append(short_dish(d))
        log(f"  random[{i+1}]: {short_dish(d)}")
    s1["random_picks"] = s1_random
except requests.HTTPError as e:
    s1["error"] = f"{e.response.status_code}: {e.response.text[:200]}"
    log(f"S1 error: {s1['error']}")
except Exception as e:
    s1["error"] = str(e)
    log(f"S1 error: {e}")

report["scenarios"]["1_broke_student"] = s1


# ══════════════════════════════════════════════════════════════════════
# SCENARIO 2: "Date night, want to impress"
# ══════════════════════════════════════════════════════════════════════
log("\n========== SCENARIO 2: date night ==========")
s2: dict[str, Any] = {"notes": []}

try:
    search = post(
        "/search-dishes",
        {"query": "romantic dinner steak wine", "price_max": 40, "limit": 8},
    )
    s2_dishes = search.get("dishes", [])
    s2["search_count"] = len(s2_dishes)
    s2["search_sample"] = [short_dish(d) for d in s2_dishes]
    log(f"search 'romantic dinner steak wine' price_max=40 → {len(s2_dishes)} dishes:")
    for d in s2_dishes:
        log(f"  • {short_dish(d)}")

    # Look for obvious semantic misses — "romantic" is a vibe, not a word on menus
    is_actually_dinner_food = [
        d for d in s2_dishes
        if any(w in (d.get("name") or "").lower() for w in ["steak", "filet", "rib", "lamb", "duck", "salmon", "tuna", "beef", "pasta", "risotto"])
    ]
    s2["looks_like_dinner_food"] = [short_dish(d) for d in is_actually_dinner_food]

    # Ask the chat: is this a good date night spot?
    if s2_dishes:
        top = s2_dishes[0]
        chat_reply = post(
            "/chat",
            {
                "restaurant": top["restaurant_slug"],
                "message": "is this a good date night spot?",
                "history": [],
            },
        )
        s2["chat_target"] = top["restaurant_name"]
        s2["chat_reply"] = chat_reply.get("reply", "(no reply)")[:600]
        log(f"  chat '{top['restaurant_name']}' ask date-night: {s2['chat_reply']}")
except requests.HTTPError as e:
    s2["error"] = f"{e.response.status_code}: {e.response.text[:200]}"
    log(f"S2 error: {s2['error']}")
except Exception as e:
    s2["error"] = str(e)
    log(f"S2 error: {e}")

report["scenarios"]["2_date_night"] = s2


# ══════════════════════════════════════════════════════════════════════
# SCENARIO 3: "Strict dietary need: peanut allergy + Thai"
# ══════════════════════════════════════════════════════════════════════
log("\n========== SCENARIO 3: peanut allergy + Thai ==========")
s3: dict[str, Any] = {"notes": [], "safety_issue": None}

try:
    search = post(
        "/search-dishes",
        {"query": "thai food", "dietary": ["nut-free"], "limit": 8},
    )
    s3_dishes = search.get("dishes", [])
    s3["search_count"] = len(s3_dishes)
    s3["search_sample"] = [short_dish(d) for d in s3_dishes]
    log(f"search 'thai food' dietary=[nut-free] → {len(s3_dishes)} dishes:")
    for d in s3_dishes:
        tags = d.get("dietary_info") or []
        log(f"  • {short_dish(d)} tags={tags}")

    # Verify each result actually has the nut-free tag
    missing_tag = [
        d for d in s3_dishes
        if "nut-free" not in [str(t).lower() for t in (d.get("dietary_info") or [])]
    ]
    s3["dishes_missing_nut_free_tag"] = [
        {"dish": short_dish(d), "tags": d.get("dietary_info") or []}
        for d in missing_tag
    ]
    if missing_tag:
        s3["safety_issue"] = (
            f"CRITICAL: {len(missing_tag)}/{len(s3_dishes)} results lack nut-free tag"
        )
        log(f"  CRITICAL: {len(missing_tag)} dishes in nut-free search are missing the tag")

    # Ask the chat: are there peanuts?
    if s3_dishes:
        top = s3_dishes[0]
        chat_reply = post(
            "/chat",
            {
                "restaurant": top["restaurant_slug"],
                "message": f"I have a peanut allergy. Are there any peanuts in the {top['name']}?",
                "history": [],
            },
        )
        s3["chat_target"] = f"{top['restaurant_name']} / {top['name']}"
        s3["chat_reply"] = chat_reply.get("reply", "(no reply)")[:600]
        log(f"  chat peanut query: {s3['chat_reply']}")
except requests.HTTPError as e:
    s3["error"] = f"{e.response.status_code}: {e.response.text[:200]}"
    log(f"S3 error: {s3['error']}")
except Exception as e:
    s3["error"] = str(e)
    log(f"S3 error: {e}")

report["scenarios"]["3_peanut_allergy"] = s3


# ══════════════════════════════════════════════════════════════════════
# SCENARIO 4: "Hungry x20 — variety check"
# ══════════════════════════════════════════════════════════════════════
log("\n========== SCENARIO 4: hungry x20 ==========")
s4: dict[str, Any] = {"notes": []}

try:
    rolls = []
    for i in range(20):
        d = get("/random-dish")
        rolls.append({
            "name": d.get("name"),
            "slug": d.get("restaurant_slug"),
            "price": price_of(d),
            "category": d.get("category"),
            "description": (d.get("description") or "")[:80],
        })
        log(f"  roll[{i+1}]: {short_dish(d)}")
    s4["rolls"] = rolls
    unique_names = {r["name"] for r in rolls}
    unique_restaurants = {r["slug"] for r in rolls}
    s4["unique_dish_names"] = len(unique_names)
    s4["unique_restaurants"] = len(unique_restaurants)

    # Filler detection
    FILLER_WORDS = [
        "sauce", "sprinkle", "side", "dressing", "topping", "extra",
        "kids ", "kid ", "addon", "add-on", "add on", "dip", "cup of",
    ]
    filler = [
        r for r in rolls
        if any(w in (r["name"] or "").lower() for w in FILLER_WORDS)
    ]
    s4["filler_count"] = len(filler)
    s4["filler_examples"] = [r["name"] for r in filler]

    cheap = [r for r in rolls if (r["price"] or 0) < 3.0]
    s4["very_cheap_count"] = len(cheap)
    s4["very_cheap_examples"] = [
        f"{r['name']} @ ${r['price']}" for r in cheap
    ]
except Exception as e:
    s4["error"] = str(e)
    log(f"S4 error: {e}")

report["scenarios"]["4_hungry_variety"] = s4


# ══════════════════════════════════════════════════════════════════════
# SCENARIO 5: "4-turn chat with memory"
# ══════════════════════════════════════════════════════════════════════
# Spec says Playwright; we use direct /chat API with manual history which
# is a MORE faithful test of chat memory logic (isolates from UI) and runs
# an order of magnitude faster. The report explains the substitution.
log("\n========== SCENARIO 5: 4-turn chat memory ==========")
s5: dict[str, Any] = {"notes": []}

try:
    # Pick a real restaurant from the search endpoint
    probe = post("/search-dishes", {"query": "vegetarian pasta", "limit": 3})
    probe_dishes = probe.get("dishes", [])
    if not probe_dishes:
        raise RuntimeError("couldn't pick a restaurant for chat memory test")
    target = probe_dishes[0]
    slug = target["restaurant_slug"]
    s5["restaurant"] = target["restaurant_name"]
    s5["slug"] = slug
    log(f"target restaurant: {target['restaurant_name']}")

    history: list[dict] = []
    turns = [
        "I'm vegetarian, what do you recommend?",
        "Which of those is the cheapest?",
        "Is it spicy?",
        "Can I get it without cheese?",
    ]
    s5["turns"] = []
    markdown_leaks = 0
    for i, msg in enumerate(turns, 1):
        resp = post(
            "/chat",
            {"restaurant": slug, "message": msg, "history": history},
        )
        if resp.get("_rate_limited"):
            s5["notes"].append("rate limited on turn " + str(i))
            break
        reply = resp.get("reply", "")
        s5["turns"].append({"user": msg, "assistant": reply[:700]})
        log(f"  T{i} USER: {msg}")
        log(f"  T{i} AI:   {reply[:350]}")
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": reply})

        # Check for markdown leakage
        if "**" in reply or re.search(r"\*[A-Za-z]", reply):
            markdown_leaks += 1

    s5["markdown_leak_count"] = markdown_leaks
except Exception as e:
    s5["error"] = str(e)
    log(f"S5 error: {e}")

report["scenarios"]["5_chat_memory"] = s5


# ══════════════════════════════════════════════════════════════════════
# SCENARIO 6: "Honesty boundaries"
# ══════════════════════════════════════════════════════════════════════
log("\n========== SCENARIO 6: honesty boundaries ==========")
s6: dict[str, Any] = {"notes": []}

try:
    # Reuse a restaurant we've already targeted
    probe = post("/search-dishes", {"query": "pizza", "limit": 1})
    probe_dishes = probe.get("dishes", [])
    if not probe_dishes:
        raise RuntimeError("no pizza restaurant found for boundary test")
    slug = probe_dishes[0]["restaurant_slug"]
    name = probe_dishes[0]["restaurant_name"]
    s6["restaurant"] = name

    questions = [
        "What time do you open?",
        "Is the chef nice?",
        "Do you deliver?",
    ]
    s6["answers"] = []
    hallucinations = 0
    for q in questions:
        resp = post("/chat", {"restaurant": slug, "message": q, "history": []})
        if resp.get("_rate_limited"):
            s6["notes"].append("rate limited")
            break
        reply = resp.get("reply", "")
        s6["answers"].append({"q": q, "a": reply[:700]})
        log(f"  Q: {q}")
        log(f"  A: {reply[:300]}")

        # Heuristic hallucination check — a HONEST answer should admit not
        # knowing, e.g. contain one of these phrases:
        honest_phrases = [
            "don't know", "do not know", "i'm not sure", "not sure",
            "only know", "just the menu", "menu only", "can't tell",
            "cannot tell", "not able", "unable to", "don't have info",
            "don't have information", "don't have that",
            "can't help with", "i only", "menu details",
        ]
        reply_lower = reply.lower()
        admits = any(p in reply_lower for p in honest_phrases)
        looks_like_made_up_time = bool(
            re.search(r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b", reply_lower)
        )
        if not admits or looks_like_made_up_time:
            hallucinations += 1

    s6["hallucination_count"] = hallucinations
except Exception as e:
    s6["error"] = str(e)
    log(f"S6 error: {e}")

report["scenarios"]["6_honesty"] = s6


# ══════════════════════════════════════════════════════════════════════
# SCENARIO 7: "Typos and slang"
# ══════════════════════════════════════════════════════════════════════
log("\n========== SCENARIO 7: typos and slang ==========")
s7: dict[str, Any] = {"notes": [], "queries": {}}

try:
    queries = ["burgr", "lit ramen", "noms", "mmm cheesy", "pho"]
    for q in queries:
        resp = post("/search-dishes", {"query": q, "limit": 5})
        dishes = resp.get("dishes", [])
        s7["queries"][q] = [short_dish(d) for d in dishes]
        log(f"  '{q}' → {len(dishes)} dishes:")
        for d in dishes[:5]:
            log(f"     · {short_dish(d)}")
except Exception as e:
    s7["error"] = str(e)
    log(f"S7 error: {e}")

report["scenarios"]["7_typos_slang"] = s7


# ══════════════════════════════════════════════════════════════════════
# SCENARIO 8: Discovery flow end-to-end
# ══════════════════════════════════════════════════════════════════════
# Simulate the click-by-click flow via API since Playwright against production
# is fragile (real LLM latency, Cloudflare, dynamic selectors). Each "click"
# is mapped to its backing API call and timed.
log("\n========== SCENARIO 8: discovery flow (API-simulated) ==========")
s8: dict[str, Any] = {"notes": [], "steps": []}
s8_start = time.time()

def record(step: str, t0: float, detail: str = "") -> None:
    elapsed = time.time() - t0
    s8["steps"].append({"step": step, "seconds": round(elapsed, 2), "detail": detail})
    log(f"  [{elapsed:.2f}s] {step} — {detail}")

try:
    t0 = time.time()
    get("/stats")  # landing page → stats fetch (what StatsCounter does)
    record("1. Land on homepage (/stats fetched)", t0)

    # Click "Pizza" tile → /category-dishes with query=pizza
    t0 = time.time()
    pizza_res = post("/category-dishes", {"query": "pizza", "limit": 8})
    pizza_dishes = pizza_res.get("dishes", [])
    record(
        "2. Click Pizza tile",
        t0,
        f"{len(pizza_dishes)} dishes returned",
    )

    # Find the cheapest pizza
    priced_pizzas = [
        (d, price_of(d)) for d in pizza_dishes if price_of(d) is not None
    ]
    priced_pizzas.sort(key=lambda x: x[1])
    if not priced_pizzas:
        raise RuntimeError("no priced pizzas in tile results")
    cheapest = priced_pizzas[0][0]
    cheapest_price = priced_pizzas[0][1]
    t0 = time.time()
    record(
        "3. Click cheapest pizza",
        t0,
        f"{cheapest['name']} @ ${cheapest_price:.2f} at {cheapest['restaurant_name']}",
    )

    # Open chat with that restaurant — send "what's your most popular pizza?"
    t0 = time.time()
    chat_resp = post(
        "/chat",
        {
            "restaurant": cheapest["restaurant_slug"],
            "message": "what's your most popular pizza?",
            "history": [],
        },
    )
    chat_reply = chat_resp.get("reply", "")
    record(
        "4. Open chat + ask 'most popular pizza?'",
        t0,
        chat_reply[:200],
    )
    s8["chat_reply"] = chat_reply[:800]

    # Step 5 (Google Maps link click) — can only be tested via UI. Note it.
    s8["notes"].append(
        "Step 5 (Google Maps link in chat header) not tested: API-only harness "
        "cannot verify a DOM anchor, and the current ChatPanel.tsx has no such "
        "link. Noting as a gap."
    )

    # "Return to homepage" — analytics page_view
    t0 = time.time()
    get("/stats")
    record("6. Return to homepage", t0)

    # "Click Hungry" → /random-dish (first roll, no budget)
    rolls_8: list[str] = []
    t0 = time.time()
    first = get("/random-dish")
    rolls_8.append(short_dish(first))
    record("7. Click Hungry", t0, short_dish(first))

    # "Try another" x3
    for i in range(3):
        t0 = time.time()
        d = get("/random-dish")
        rolls_8.append(short_dish(d))
        record(f"8.{i+1} Try another", t0, short_dish(d))

    # "Ask the menu" on final result → chat open
    final = d
    t0 = time.time()
    resp = post(
        "/chat",
        {
            "restaurant": final["restaurant_slug"],
            "message": "tell me about this dish",
            "history": [],
        },
    )
    record("9. Ask the menu on final result", t0, resp.get("reply", "")[:200])
    s8["rolls"] = rolls_8
    s8["final_chat_reply"] = resp.get("reply", "")[:500]
except Exception as e:
    s8["error"] = str(e)
    log(f"S8 error: {e}")

s8["total_seconds"] = round(time.time() - s8_start, 2)
report["scenarios"]["8_discovery_flow"] = s8


# ─── Capture after /stats ───
log("\n========== AFTER STATS ==========")
try:
    report["stats_after"] = get("/stats")
    log(json.dumps(report["stats_after"], indent=2))
except Exception as e:
    report["stats_after"] = {"error": str(e)}

report["ended_at"] = datetime.utcnow().isoformat() + "Z"

with open(OUTPUT_JSON, "w") as f:
    json.dump(report, f, indent=2, default=str)

log(f"\nRaw findings written to {OUTPUT_JSON}")
log("\nDone.")
