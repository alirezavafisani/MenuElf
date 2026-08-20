"""The chat has to read the menu from the same place the list does.

Found live on 2026-08-20. "Ask the kitchen" on a Calgary Honest dish answered
"I can't provide specific recommendations without the menu details" while
/menu/calgaryhonest returned 124 dishes for the same restaurant.

The cause was two sources of truth. The prompt was built from load_menu, which
reads a per restaurant JSON file off disk, and those files are absent on this
deployment, so it returned None. The emptiness guard checks MENU_INDEX instead,
found 124 dishes, and let the request through. The model was handed the literal
string null as its menu.

The guard and the prompt now read the same index, which is the property these
tests hold down.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-dummy")

import main
from main import _menu_for_prompt, _menu_is_empty, _build_menu_system_prompt


ROWS = [
    {"restaurant_slug": "calgaryhonest", "name": "Veg. Chilli Garlic Noodles",
     "price": 13.95, "category": "Noodles", "description": "wok tossed"},
    {"restaurant_slug": "calgaryhonest", "name": "Schezwan Noodles",
     "price": 14.5, "category": "Noodles", "description": ""},
    {"restaurant_slug": "someplaceelse", "name": "Not This One", "price": 9.0},
]


def _with_index(monkeypatch, rows):
    monkeypatch.setattr(main, "MENU_INDEX", rows)
    # The old file reader must never be what makes this pass.
    monkeypatch.setattr(main, "load_menu", lambda *_a, **_k: None)


def test_the_prompt_menu_comes_from_the_index(monkeypatch):
    _with_index(monkeypatch, ROWS)
    menu = _menu_for_prompt("calgaryhonest", "Calgary Honest")
    assert menu, "the index had dishes and the prompt menu came back empty"
    assert {d["name"] for d in menu} == {"Veg. Chilli Garlic Noodles", "Schezwan Noodles"}


def test_dishes_from_other_restaurants_stay_out(monkeypatch):
    _with_index(monkeypatch, ROWS)
    names = {d["name"] for d in _menu_for_prompt("calgaryhonest", "Calgary Honest")}
    assert "Not This One" not in names


def test_the_model_is_never_handed_null(monkeypatch):
    """The exact failure. A non empty index must never produce a null menu."""
    _with_index(monkeypatch, ROWS)
    menu = _menu_for_prompt("calgaryhonest", "Calgary Honest")
    prompt = _build_menu_system_prompt("Calgary Honest", menu)
    assert "MENU JSON:\nnull" not in prompt
    assert "Veg. Chilli Garlic Noodles" in prompt


def test_the_guard_and_the_prompt_agree(monkeypatch):
    """If the guard says there is a menu, the prompt must contain one."""
    _with_index(monkeypatch, ROWS)
    menu = _menu_for_prompt("calgaryhonest", "Calgary Honest")
    assert _menu_is_empty(menu, "calgaryhonest") is False


def test_an_unknown_restaurant_still_reports_empty(monkeypatch):
    _with_index(monkeypatch, ROWS)
    menu = _menu_for_prompt("nowhere", "Nowhere")
    assert _menu_is_empty(menu, "nowhere") is True


def test_the_prompt_is_capped(monkeypatch):
    many = [{"restaurant_slug": "big", "name": f"Dish {i}", "price": 1.0} for i in range(400)]
    _with_index(monkeypatch, many)
    assert len(_menu_for_prompt("big", "Big")) == main.PROMPT_MENU_CAP
