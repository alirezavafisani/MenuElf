#!/usr/bin/env python3
"""Fix dish descriptions, names, and prices in restaurant menu JSON files."""

import json
import os
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
MENUS_DIR = BACKEND_DIR / "menus"


def clean_description(desc: str) -> str | None:
    """Clean a dish description by removing markdown, URLs, HTML, etc."""
    if not desc or not desc.strip():
        return None

    text = desc

    # Remove markdown code blocks: ```code``` → code
    text = re.sub(r"```[\s\S]*?```", "", text)

    # Remove markdown links: [text](url) → text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)

    # Remove markdown bold: **text** → text (paired)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Remove unpaired ** (leftover bold markers)
    text = text.replace("**", "")

    # Remove markdown bold with underscores: __text__ → text
    text = re.sub(r"__(.+?)__", r"\1", text)

    # Remove markdown headers: ## Header → Header, ### Header → Header
    text = re.sub(r"#{1,6}\s*", "", text)

    # Remove markdown italic: *text* → text (but not bullet points like "* item")
    text = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"\1", text)
    # Also _text_ italic (careful with underscores in words)
    text = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"\1", text)
    # Remove any remaining stray asterisks that look like markdown artifacts
    # (trailing *** or leading ***)
    text = re.sub(r"\*{2,}", "", text)

    # Remove markdown strikethrough: ~~text~~ → text
    text = re.sub(r"~~(.+?)~~", r"\1", text)

    # Remove raw URLs
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)

    # Remove HTML tags
    text = re.sub(r"</?(?:br|p|div|span|a|b|i|em|strong|ul|ol|li|h[1-6]|img|table|tr|td|th)[^>]*>", " ", text, flags=re.I)

    # Decode HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&apos;", "'")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    # Numeric HTML entities
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)

    # Remove markdown bullet points at the start: * item → item
    text = re.sub(r"^\s*\*\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*-\s+", "", text, flags=re.MULTILINE)

    # Remove the "…" price pattern like "… $8.00"
    text = re.sub(r"\s*…\s*\$[\d.]+", "", text)

    # Remove leading/trailing punctuation artifacts
    text = re.sub(r"^[\s|/\-–—:;,.*]+", "", text)
    text = re.sub(r"[\s|/\-–—:;,.*]+$", "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # If empty after cleanup, return None
    if not text or len(text) < 2:
        return None

    # Truncate at 300 chars on sentence boundary
    if len(text) > 300:
        # Find last sentence-ending punctuation before 300
        truncated = text[:300]
        last_period = max(
            truncated.rfind(". "),
            truncated.rfind("! "),
            truncated.rfind("? "),
            truncated.rfind(".\n"),
        )
        if last_period > 50:
            text = text[: last_period + 1]
        else:
            # Just cut at 300 and add ellipsis
            last_space = truncated.rfind(" ")
            if last_space > 200:
                text = text[:last_space] + "..."
            else:
                text = truncated + "..."

    return text


def clean_name(name: str) -> str:
    """Clean a dish name."""
    if not name:
        return name

    text = name

    # Remove markdown: **bold** → bold, [text](url) → text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = text.replace("**", "")
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    # Remove trailing/leading asterisks
    text = re.sub(r"\*{2,}", "", text)
    text = text.strip("*")

    # Remove strikethrough: ~~text~~ → ""
    text = re.sub(r"~~[^~]*~~", "", text)

    # Remove price noise patterns: "Original price was: $X.Current price is: $Y."
    text = re.sub(r"Original price was:.*?Current price is:.*?\.", "", text)

    # Remove price strings at the end: "Burger $15.99" → "Burger"
    text = re.sub(r"\s*\$\d+\.?\d*\s*$", "", text)
    # Remove multiple price strings: "$15.99$12.99"
    text = re.sub(r"(\$\d+\.?\d*\s*){2,}", "", text)

    # Fix common encoding issues (UTF-8 mojibake)
    encoding_fixes = {
        "Ã©": "é", "Ã¨": "è", "Ã¡": "á", "Ã ": "à",
        "Ã¼": "ü", "Ã¶": "ö", "Ã¤": "ä", "Ã±": "ñ",
        "Ã§": "ç", "Ã®": "î", "Ã´": "ô", "Ã¢": "â",
        "Ã»": "û", "Ã¯": "ï", "Ã«": "ë", "Ãª": "ê",
    }
    for bad, good in encoding_fixes.items():
        text = text.replace(bad, good)

    # Strip whitespace
    text = text.strip()

    return text


def fix_price(price) -> float | None:
    """Fix a price value."""
    if price is None:
        return None

    if isinstance(price, str):
        # Extract number from string like "$15.99" or "15.99"
        match = re.search(r"[\d]+\.?\d*", price)
        if match:
            price = float(match.group())
        else:
            return None

    if not isinstance(price, (int, float)):
        return None

    price = float(price)

    if price < 0:
        return None
    if price == 0:
        return None
    if price > 200:
        return None

    return price


def fix_descriptions():
    descs_cleaned = 0
    names_cleaned = 0
    prices_fixed = 0
    files_modified = 0

    for fname in sorted(os.listdir(MENUS_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue

        filepath = MENUS_DIR / fname
        with open(filepath) as f:
            data = json.load(f)

        modified = False

        for item in data.get("items", []):
            # Clean description
            original_desc = item.get("description")
            if original_desc:
                cleaned = clean_description(original_desc)
                if cleaned != original_desc:
                    item["description"] = cleaned
                    descs_cleaned += 1
                    modified = True

            # Clean simplified_description too
            original_simp = item.get("simplified_description")
            if original_simp:
                cleaned_simp = clean_description(original_simp)
                if cleaned_simp != original_simp:
                    item["simplified_description"] = cleaned_simp
                    modified = True

            # Clean name
            original_name = item.get("name", "")
            cleaned_name = clean_name(original_name)
            if cleaned_name != original_name:
                item["name"] = cleaned_name
                names_cleaned += 1
                modified = True

            # Fix price
            original_price = item.get("price")
            fixed_price = fix_price(original_price)
            if fixed_price != original_price:
                item["price"] = fixed_price
                prices_fixed += 1
                modified = True

        if modified:
            files_modified += 1
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

    print("=" * 50)
    print("DESCRIPTION/NAME/PRICE CLEANUP SUMMARY")
    print("=" * 50)
    print(f"Files modified:       {files_modified}")
    print(f"Descriptions cleaned: {descs_cleaned}")
    print(f"Names cleaned:        {names_cleaned}")
    print(f"Prices fixed:         {prices_fixed}")


if __name__ == "__main__":
    fix_descriptions()
