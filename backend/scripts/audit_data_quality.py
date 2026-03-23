#!/usr/bin/env python3
"""Audit data quality across all restaurant menu JSON files."""

import json
import os
from pathlib import Path

MENUS_DIR = Path(__file__).parent.parent / "menus"


def audit():
    restaurants = []
    total_items = 0
    total_missing_price = 0
    total_empty_desc = 0
    total_missing_category = 0
    total_zero_price = 0

    for f in sorted(MENUS_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, Exception) as e:
            print(f"ERROR reading {f.name}: {e}")
            continue

        items = data.get("items", [])
        count = len(items)
        missing_price = sum(1 for i in items if i.get("price") is None)
        zero_price = sum(1 for i in items if i.get("price") == 0)
        empty_desc = sum(
            1
            for i in items
            if not i.get("description") or i.get("description") is None
        )
        missing_cat = sum(
            1
            for i in items
            if not i.get("category") or i.get("category") is None
        )

        issues = missing_price + zero_price + empty_desc + missing_cat
        restaurants.append(
            {
                "file": f.name,
                "restaurant": data.get("restaurant", f.stem),
                "total_items": count,
                "missing_price": missing_price,
                "zero_price": zero_price,
                "empty_desc": empty_desc,
                "missing_category": missing_cat,
                "total_issues": issues,
            }
        )

        total_items += count
        total_missing_price += missing_price
        total_empty_desc += empty_desc
        total_missing_category += missing_cat
        total_zero_price += zero_price

    # Summary
    print("=" * 70)
    print("MENU DATA QUALITY AUDIT")
    print("=" * 70)
    print(f"Total restaurants scanned: {len(restaurants)}")
    print(f"Total menu items: {total_items}")
    print()
    print(f"Missing/null price:    {total_missing_price:>5} ({total_missing_price/total_items*100:.1f}%)" if total_items else "No items")
    print(f"Zero price:            {total_zero_price:>5} ({total_zero_price/total_items*100:.1f}%)" if total_items else "")
    print(f"Empty/null description: {total_empty_desc:>5} ({total_empty_desc/total_items*100:.1f}%)" if total_items else "")
    print(f"Missing category:      {total_missing_category:>5} ({total_missing_category/total_items*100:.1f}%)" if total_items else "")
    print()

    # Top 20 worst
    worst = sorted(restaurants, key=lambda r: r["total_issues"], reverse=True)[:20]
    print("TOP 20 WORST RESTAURANTS BY DATA QUALITY:")
    print("-" * 70)
    print(f"{'Restaurant':<35} {'Items':>5} {'NoPrice':>7} {'$0':>4} {'NoDesc':>6} {'NoCat':>5} {'Issues':>6}")
    print("-" * 70)
    for r in worst:
        print(
            f"{r['restaurant'][:35]:<35} {r['total_items']:>5} "
            f"{r['missing_price']:>7} {r['zero_price']:>4} "
            f"{r['empty_desc']:>6} {r['missing_category']:>5} {r['total_issues']:>6}"
        )
    print("=" * 70)


if __name__ == "__main__":
    audit()
