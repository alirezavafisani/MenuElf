#!/usr/bin/env python3
"""Trim no-price dishes and fold in newly scraped restaurants, cheaply.

The 461 shipped restaurants exist only as the prebuilt menu_db.json plus its
aligned menu_embeddings.npz, not as local menu files, so we never rebuild from
scratch. Instead we treat the prebuilt pair as the base, drop every dish with no
usable price (slicing the existing embeddings, no API cost), then append only the
restaurants in menus/ that are not already in the base and embed only those new
dishes. Existing embeddings are reused verbatim, so the OpenAI bill is
proportional to new dishes alone.

    OPENAI_API_KEY=sk-... python3 scripts/refresh_data.py
"""

import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
MENUS_DIR = BACKEND_DIR / "menus"
NAME_MAPPING_FILE = BACKEND_DIR / "name_mapping.json"
MENU_DB_FILE = BACKEND_DIR / "menu_db.json"
EMBEDDINGS_FILE = BACKEND_DIR / "menu_embeddings.npz"

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 3072
BATCH_SIZE = 100


import re

# High precision only. These catch obvious non-dishes (promo lines, gift cards)
# that the scraper sometimes lifts off a menu page. Deliberately narrow so a real
# dish is never dropped.
_JUNK_NAME = re.compile(
    r"(\d+\s*%\s*off|gift\s*card|gift\s*certificate|e-?gift|\bvoucher\b|"
    r"delivery\s*fee|service\s*charge|^\s*subtotal\b|^\s*total\b)",
    re.IGNORECASE,
)


def is_junk(item) -> bool:
    name = str(item.get("name", "")).strip()
    if len(name) < 2:
        return True
    return bool(_JUNK_NAME.search(name))


def usable_price(p):
    """A price we can show and filter on. None, empty, or zero means drop it."""
    if p is None or p == "":
        return None
    if isinstance(p, (int, float)):
        return float(p) if p > 0 else None
    cleaned = "".join(c for c in str(p) if c.isdigit() or c == ".")
    try:
        v = float(cleaned)
        return v if v > 0 else None
    except ValueError:
        return None


def make_embedding_text(item: dict) -> str:
    """Same recipe the original embeddings used, so new rows sit in the same space."""
    parts = [item.get("name", ""), item.get("description", ""), item.get("category", "")]
    dietary = item.get("dietary_info", [])
    if dietary:
        parts.append(" ".join(dietary))
    return " ".join(p for p in parts if p).strip()


def load_base():
    with open(MENU_DB_FILE) as f:
        db = json.load(f)
    emb = np.load(EMBEDDINGS_FILE)["embeddings"]
    if len(db) != emb.shape[0]:
        sys.exit("base db (%d) and embeddings (%d) are misaligned, refusing to run"
                 % (len(db), emb.shape[0]))
    return db, emb


def trim_base(db, emb):
    """Keep only priced dishes, carrying their existing embedding rows across untouched."""
    keep_idx = [i for i, d in enumerate(db)
                if usable_price(d.get("price")) is not None and not is_junk(d)]
    kept_db = [db[i] for i in keep_idx]
    kept_emb = emb[keep_idx]
    return kept_db, kept_emb, len(db) - len(keep_idx)


def collect_new(existing_slugs):
    """Priced dishes from menus/ for restaurants not already in the base."""
    with open(NAME_MAPPING_FILE) as f:
        name_mapping = json.load(f)
    new_items = []
    new_restaurants = set()
    for fname in sorted(os.listdir(MENUS_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        with open(MENUS_DIR / fname) as f:
            data = json.load(f)
        slug = data.get("restaurant", fname[:-5])
        if slug in existing_slugs:
            continue
        display_name = name_mapping.get(slug, slug)
        added_here = 0
        for idx, item in enumerate(data.get("items", [])):
            price = usable_price(item.get("price"))
            if price is None or is_junk(item):
                continue
            new_items.append({
                "id": "%s_%d" % (slug, idx),
                "name": item.get("name", ""),
                "price": price,
                "description": item.get("description") or item.get("simplified_description") or "",
                "category": item.get("category") or "OTHER",
                "restaurant_slug": slug,
                "restaurant_name": display_name,
                "dietary_info": item.get("dietary_info", []),
            })
            added_here += 1
        if added_here:
            new_restaurants.add(slug)
    return new_items, new_restaurants


def embed(items):
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY not set, cannot embed the new dishes")
    client = OpenAI(api_key=api_key)
    texts = [make_embedding_text(it) for it in items]
    out = np.zeros((len(texts), EMBEDDING_DIMENSIONS), dtype=np.float32)
    batches = math.ceil(len(texts) / BATCH_SIZE)
    for b in range(batches):
        s, e = b * BATCH_SIZE, min((b + 1) * BATCH_SIZE, len(texts))
        print("  embedding new batch %d/%d..." % (b + 1, batches), flush=True)
        for attempt in range(3):
            try:
                resp = client.embeddings.create(
                    input=texts[s:e], model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)
                for i, d in enumerate(resp.data):
                    out[s + i] = d.embedding
                break
            except Exception as ex:
                if attempt == 2:
                    sys.exit("embedding failed after retries: %s" % ex)
                time.sleep(2)
        if b < batches - 1:
            time.sleep(0.4)
    return out


def main():
    db, emb = load_base()
    base_restaurants = {d["restaurant_slug"] for d in db}
    print("base: %d dishes, %d restaurants" % (len(db), len(base_restaurants)))

    kept_db, kept_emb, dropped = trim_base(db, emb)
    print("trimmed: dropped %d no-price dishes, %d priced remain" % (dropped, len(kept_db)))

    new_items, new_restaurants = collect_new(base_restaurants)
    print("new: %d priced dishes across %d new restaurants" % (len(new_items), len(new_restaurants)))

    if new_items:
        new_emb = embed(new_items).astype(np.float16)
        final_db = kept_db + new_items
        final_emb = np.vstack([kept_emb.astype(np.float16), new_emb])
    else:
        final_db = kept_db
        final_emb = kept_emb.astype(np.float16)

    if len(final_db) != final_emb.shape[0]:
        sys.exit("final db/embeddings misaligned, not saving")

    with open(MENU_DB_FILE, "w") as f:
        json.dump(final_db, f, ensure_ascii=False)
    np.savez_compressed(EMBEDDINGS_FILE, embeddings=final_emb)

    final_restaurants = {d["restaurant_slug"] for d in final_db}
    print("---")
    print("final: %d dishes, %d restaurants" % (len(final_db), len(final_restaurants)))
    print("saved menu_db.json and menu_embeddings.npz")


if __name__ == "__main__":
    main()
