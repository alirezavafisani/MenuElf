#!/usr/bin/env python3
"""Build menu_db.json and menu_embeddings.npy from restaurant JSON files.

Usage:
    OPENAI_API_KEY=sk-... python backend/scripts/build_vector_db.py

Requires: openai, numpy
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


def build_menu_index() -> list[dict]:
    """Build flat menu index from restaurant JSON files."""
    with open(NAME_MAPPING_FILE) as f:
        name_mapping = json.load(f)

    menu_index = []

    for fname in sorted(os.listdir(MENUS_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue

        with open(MENUS_DIR / fname) as f:
            data = json.load(f)

        slug = data.get("restaurant", fname.replace(".json", ""))
        display_name = name_mapping.get(slug, slug)

        for idx, item in enumerate(data.get("items", [])):
            entry = {
                "id": f"{slug}_{idx}",
                "name": item.get("name", ""),
                "price": item.get("price"),
                "description": item.get("description")
                or item.get("simplified_description")
                or "",
                "category": item.get("category", "OTHER"),
                "restaurant_slug": slug,
                "restaurant_name": display_name,
                "dietary_info": item.get("dietary_info", []),
            }
            menu_index.append(entry)

    return menu_index


def make_embedding_text(item: dict) -> str:
    """Create the text string to embed for a menu item."""
    parts = [
        item.get("name", ""),
        item.get("description", ""),
        item.get("category", ""),
    ]
    dietary = item.get("dietary_info", [])
    if dietary:
        parts.append(" ".join(dietary))
    return " ".join(p for p in parts if p).strip()


def build_embeddings(menu_index: list[dict]) -> np.ndarray:
    """Generate embeddings for all menu items using OpenAI API."""
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    texts = [make_embedding_text(item) for item in menu_index]
    total_batches = math.ceil(len(texts) / BATCH_SIZE)
    all_embeddings = np.zeros((len(texts), EMBEDDING_DIMENSIONS), dtype=np.float32)

    for batch_num in range(total_batches):
        start = batch_num * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(texts))
        batch_texts = texts[start:end]

        print(
            f"Embedding batch {batch_num + 1}/{total_batches}... ",
            end="",
            flush=True,
        )

        for attempt in range(2):
            try:
                response = client.embeddings.create(
                    input=batch_texts,
                    model=EMBEDDING_MODEL,
                    dimensions=EMBEDDING_DIMENSIONS,
                )
                for i, embedding_data in enumerate(response.data):
                    all_embeddings[start + i] = embedding_data.embedding
                print("done")
                break
            except Exception as e:
                if attempt == 0:
                    print(f"failed ({e}), retrying...")
                    time.sleep(2)
                else:
                    print(f"FAILED after retry ({e}), skipping batch")
                    # Leave zeros for this batch — they won't match well
                    # but won't crash the system

        # Small delay between batches to respect rate limits
        if batch_num < total_batches - 1:
            time.sleep(0.5)

    return all_embeddings


def main():
    print("Building menu index...")
    menu_index = build_menu_index()
    print(f"  {len(menu_index)} items from {len(set(e['restaurant_slug'] for e in menu_index))} restaurants")

    # Save menu_db.json
    with open(MENU_DB_FILE, "w") as f:
        json.dump(menu_index, f, ensure_ascii=False)
    print(f"Saved {MENU_DB_FILE}")

    # Build embeddings
    print("Generating embeddings...")
    embeddings = build_embeddings(menu_index)

    # Save embeddings as compressed npz (stays under GitHub 100MB limit)
    np.savez_compressed(EMBEDDINGS_FILE, embeddings=embeddings)
    print(f"Saved {EMBEDDINGS_FILE}")
    print(f"Built embeddings for {len(menu_index)} items. Saved to menu_embeddings.npz")


if __name__ == "__main__":
    main()
