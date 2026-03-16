#!/usr/bin/env python3
"""Audit restaurant menu data for quality issues."""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
MENUS_DIR = BACKEND_DIR / "menus"
NAME_MAPPING_FILE = BACKEND_DIR / "name_mapping.json"


def is_slug(name: str) -> bool:
    """Check if a restaurant name looks like a URL slug."""
    if not name:
        return False
    # If it's all lowercase with no spaces, or contains hyphens/underscores → slug
    if name == name.lower() and " " not in name:
        return True
    if "-" in name and name == name.lower():
        return True
    if "_" in name and name == name.lower():
        return True
    return False


def has_markdown(text: str) -> bool:
    """Check for markdown formatting in text."""
    if not text:
        return False
    return bool(re.search(r"\*\*|__|##|\[.*?\]\(.*?\)|```|~~", text))


def has_urls(text: str) -> bool:
    """Check for raw URLs in text."""
    if not text:
        return False
    return bool(re.search(r"https?://|www\.", text))


def has_html(text: str) -> bool:
    """Check for HTML tags or entities in text."""
    if not text:
        return False
    return bool(re.search(r"<br>|<p>|</?div>|</?span>|&amp;|&nbsp;|&quot;|&#\d+;|</?[a-z]+[^>]*>", text, re.I))


def bad_price(price) -> str | None:
    """Check if a price is suspicious. Returns issue description or None."""
    if price is None:
        return None
    if isinstance(price, str):
        return f"string price: {price!r}"
    if not isinstance(price, (int, float)):
        return f"non-numeric: {type(price).__name__}"
    if price < 0:
        return f"negative: {price}"
    if price > 500:
        return f"over $500: {price}"
    if price == 0:
        return f"zero price"
    return None


def audit():
    # Load name mapping
    with open(NAME_MAPPING_FILE) as f:
        name_mapping = json.load(f)

    total_restaurants = 0
    total_items = 0
    slug_names = 0
    slug_no_mapping = 0
    markdown_descs = 0
    url_descs = 0
    html_descs = 0
    long_descs = 0
    suspicious_names = 0
    bad_prices_count = 0

    issues_by_restaurant = defaultdict(list)
    worst_items = []

    for fname in sorted(os.listdir(MENUS_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue

        with open(MENUS_DIR / fname) as f:
            data = json.load(f)

        rest_name = data.get("restaurant", fname.replace(".json", ""))
        total_restaurants += 1
        rest_issues = 0

        # Check restaurant name
        if is_slug(rest_name):
            slug_names += 1
            rest_issues += 1
            if rest_name not in name_mapping:
                slug_no_mapping += 1
                issues_by_restaurant[rest_name].append("slug name, NO mapping")
            else:
                issues_by_restaurant[rest_name].append("slug name (has mapping)")

        for item in data.get("items", []):
            total_items += 1
            item_issues = []

            desc = item.get("description") or ""
            name = item.get("name") or ""
            price = item.get("price")

            # Description checks
            if has_markdown(desc):
                markdown_descs += 1
                rest_issues += 1
                item_issues.append("markdown")

            if has_urls(desc):
                url_descs += 1
                rest_issues += 1
                item_issues.append("URLs")

            if has_html(desc):
                html_descs += 1
                rest_issues += 1
                item_issues.append("HTML")

            if len(desc) > 500:
                long_descs += 1
                rest_issues += 1
                item_issues.append(f"long ({len(desc)} chars)")

            # Name checks
            if len(name) > 80:
                suspicious_names += 1
                rest_issues += 1
                item_issues.append(f"long name ({len(name)} chars)")

            if has_markdown(name):
                suspicious_names += 1
                rest_issues += 1
                item_issues.append("markdown in name")

            # Price checks
            price_issue = bad_price(price)
            if price_issue:
                bad_prices_count += 1
                rest_issues += 1
                item_issues.append(f"price: {price_issue}")

            if item_issues:
                issues_by_restaurant[rest_name].extend(item_issues)
                worst_items.append((rest_name, name, item_issues))

    # Sort worst offenders by issue count
    restaurant_issue_counts = {
        r: len(issues) for r, issues in issues_by_restaurant.items()
    }
    top_offenders = sorted(
        restaurant_issue_counts.items(), key=lambda x: -x[1]
    )[:20]

    # Print report
    print("=" * 70)
    print("MENUELF DATA AUDIT REPORT")
    print("=" * 70)
    print()
    print(f"Total restaurants:           {total_restaurants}")
    print(f"Total menu items:            {total_items}")
    print()
    print("── Issues Found ──")
    print(f"Slug restaurant names:       {slug_names}")
    print(f"  └─ Without name mapping:   {slug_no_mapping}")
    print(f"Markdown in descriptions:    {markdown_descs}")
    print(f"URLs in descriptions:        {url_descs}")
    print(f"HTML in descriptions:        {html_descs}")
    print(f"Long descriptions (>500ch):  {long_descs}")
    print(f"Suspicious item names:       {suspicious_names}")
    print(f"Bad prices:                  {bad_prices_count}")
    print()
    print(f"TOTAL ISSUES:                {slug_names + markdown_descs + url_descs + html_descs + long_descs + suspicious_names + bad_prices_count}")
    print()
    print("── Top 20 Worst Offenders ──")
    for rank, (rest, count) in enumerate(top_offenders, 1):
        sample_issues = issues_by_restaurant[rest][:5]
        print(f"  {rank:2d}. {rest} ({count} issues)")
        for issue in sample_issues:
            print(f"      - {issue}")
    print()

    return {
        "slug_names": slug_names,
        "markdown_descs": markdown_descs,
        "url_descs": url_descs,
        "html_descs": html_descs,
        "bad_prices": bad_prices_count,
        "long_descs": long_descs,
        "suspicious_names": suspicious_names,
    }


if __name__ == "__main__":
    audit()
