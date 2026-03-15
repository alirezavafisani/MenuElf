import json
import os
from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from models.user_intelligence import (
    InteractionLogCreate,
    OnboardingAnswer,
    OnboardingRequest,
    SavedDish,
    SavedDishCreate,
    UserTasteProfile,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------
_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            raise HTTPException(status_code=500, detail="Supabase not configured")
        _supabase_client = create_client(url, key)
    return _supabase_client


# ---------------------------------------------------------------------------
# Auth helper – extracts user_id from the Authorization bearer token via
# Supabase's auth.getUser().  For now we also accept an x-user-id header
# for testing without real JWT tokens.
# ---------------------------------------------------------------------------

async def get_current_user_id(
    authorization: str = Header(default=""),
    x_user_id: str = Header(default=""),
) -> str:
    # In test / dev mode allow a plain header
    if x_user_id:
        return x_user_id

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")
    try:
        sb = _get_supabase()
        user_resp = sb.auth.get_user(token)
        return str(user_resp.user.id)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ---------------------------------------------------------------------------
# Default signals for the built-in onboarding questions
# ---------------------------------------------------------------------------

DEFAULT_ONBOARDING_QUESTIONS: List[Dict] = [
    {
        "question_index": 1,
        "option_a_label": "fiery_szechuan_dan_dan_noodles",
        "option_a_signals": {"spice_tolerance": 0.9, "adventurousness": 0.85, "cuisine_preferences.chinese": 0.8},
        "option_b_label": "classic_mac_and_cheese",
        "option_b_signals": {"spice_tolerance": 0.15, "adventurousness": 0.2, "cuisine_preferences.american": 0.8, "texture_preferences.creamy": 0.85},
    },
    {
        "question_index": 2,
        "option_a_label": "wagyu_beef_burger",
        "option_a_signals": {"protein_preference.beef": 0.9, "price_comfort": 0.8, "meal_size_preference": 0.75, "cuisine_preferences.american": 0.7, "adventurousness": 0.85},
        "option_b_label": "fresh_poke_bowl",
        "option_b_signals": {"protein_preference.fish": 0.9, "meal_size_preference": 0.3, "cuisine_preferences.japanese": 0.8, "adventurousness": 0.6},
    },
    {
        "question_index": 3,
        "option_a_label": "crispy_korean_fried_chicken",
        "option_a_signals": {"texture_preferences.crispy": 0.9, "protein_preference.chicken": 0.85, "cuisine_preferences.korean": 0.8, "spice_tolerance": 0.85, "adventurousness": 0.8},
        "option_b_label": "silky_mushroom_risotto",
        "option_b_signals": {"texture_preferences.creamy": 0.9, "protein_preference.vegetarian": 0.7, "cuisine_preferences.italian": 0.85, "meal_size_preference": 0.6, "spice_tolerance": 0.1},
    },
    {
        "question_index": 4,
        "option_a_label": "street_style_lamb_shawarma",
        "option_a_signals": {"cuisine_preferences.middle_eastern": 0.9, "adventurousness": 0.8, "protein_preference.beef": 0.6, "price_comfort": 0.3, "spice_tolerance": 0.85},
        "option_b_label": "lobster_thermidor",
        "option_b_signals": {"cuisine_preferences.french": 0.9, "price_comfort": 0.95, "protein_preference.fish": 0.7, "adventurousness": 0.4, "texture_preferences.creamy": 0.7, "spice_tolerance": 0.15},
    },
    {
        "question_index": 5,
        "option_a_label": "loaded_bbq_brisket_plate",
        "option_a_signals": {"protein_preference.beef": 0.95, "meal_size_preference": 0.9, "spice_tolerance": 0.85, "cuisine_preferences.american": 0.75, "adventurousness": 0.75, "price_comfort": 0.5},
        "option_b_label": "rainbow_buddha_bowl",
        "option_b_signals": {"protein_preference.vegetarian": 0.9, "protein_preference.vegan": 0.8, "meal_size_preference": 0.2, "adventurousness": 0.5, "sweetness_preference": 0.4, "spice_tolerance": 0.2},
    },
]


def _compute_taste_profile(answers: List[OnboardingAnswer]) -> dict:
    """Pure-math, deterministic scoring from 5 onboarding answers.

    For each taste dimension, we collect every signal from the chosen options,
    then average them.  Dimensions not covered by any answer stay at 0.5.
    """
    # Build question lookup
    q_lookup = {q["question_index"]: q for q in DEFAULT_ONBOARDING_QUESTIONS}

    # Accumulators  dimension -> list of signal values
    dimension_signals: Dict[str, List[float]] = {}

    for ans in answers:
        q = q_lookup.get(ans.question_index)
        if q is None:
            continue

        signals = q[f"option_{ans.chosen_option}_signals"]
        for dim, val in signals.items():
            dimension_signals.setdefault(dim, []).append(val)

    # Compute averages – start from defaults
    profile: dict = {
        "spice_tolerance": 0.5,
        "sweetness_preference": 0.5,
        "adventurousness": 0.5,
        "price_comfort": 0.5,
        "meal_size_preference": 0.5,
    }

    # Nested JSON dimensions (cuisine_preferences.japanese etc.)
    nested_updates: Dict[str, Dict[str, float]] = {}

    for dim, vals in dimension_signals.items():
        avg = sum(vals) / len(vals)
        if "." in dim:
            parent, child = dim.split(".", 1)
            nested_updates.setdefault(parent, {})[child] = avg
        else:
            profile[dim] = avg

    # Merge nested updates
    if nested_updates:
        for parent, children in nested_updates.items():
            profile[parent] = children

    return profile


# ---------------------------------------------------------------------------
# Load onboarding questions from JSON (with image URLs for the frontend)
# ---------------------------------------------------------------------------
_QUESTIONS_JSON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "onboarding_questions.json"
)
_onboarding_questions_cache: list | None = None


def _load_onboarding_questions() -> list:
    global _onboarding_questions_cache
    if _onboarding_questions_cache is not None:
        return _onboarding_questions_cache
    try:
        with open(_QUESTIONS_JSON_PATH, "r") as f:
            _onboarding_questions_cache = json.load(f)
    except FileNotFoundError:
        _onboarding_questions_cache = []
    return _onboarding_questions_cache


# ===================================================================
# Endpoints
# ===================================================================

# ── Onboarding ──

@router.get("/onboarding/questions")
async def get_onboarding_questions():
    """Return active onboarding questions with labels and images only.
    Signals are never exposed to the frontend."""
    questions = _load_onboarding_questions()
    safe_questions = []
    for q in questions:
        if not q.get("is_active", True):
            continue
        safe_questions.append({
            "question_index": q["question_index"],
            "option_a": {
                "image_url": q["option_a_image_url"],
                "label": q["option_a_label"],
            },
            "option_b": {
                "image_url": q["option_b_image_url"],
                "label": q["option_b_label"],
            },
        })
    return {"questions": safe_questions}


@router.post("/onboarding/complete")
async def complete_onboarding(
    req: OnboardingRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        computed = _compute_taste_profile(req.answers)

        row = {
            "id": user_id,
            "spice_tolerance": computed.get("spice_tolerance", 0.5),
            "sweetness_preference": computed.get("sweetness_preference", 0.5),
            "adventurousness": computed.get("adventurousness", 0.5),
            "price_comfort": computed.get("price_comfort", 0.5),
            "meal_size_preference": computed.get("meal_size_preference", 0.5),
            "onboarding_completed": True,
        }

        # Handle nested preference dicts
        for key in ("cuisine_preferences", "protein_preference", "texture_preferences"):
            if key in computed and isinstance(computed[key], dict):
                # Merge with defaults rather than replacing entirely
                from models.user_intelligence import UserTasteProfile
                defaults = UserTasteProfile(id=user_id).__dict__[key]
                merged = {**defaults, **computed[key]}
                row[key] = merged

        sb = _get_supabase()
        result = sb.table("user_taste_profiles").upsert(row).execute()

        # Also log each onboarding choice as an interaction
        q_lookup = {q["question_index"]: q for q in DEFAULT_ONBOARDING_QUESTIONS}
        for ans in req.answers:
            q = q_lookup.get(ans.question_index)
            if q is None:
                continue
            chosen_label = q[f"option_{ans.chosen_option}_label"]
            rejected_option = "b" if ans.chosen_option == "a" else "a"
            rejected_label = q[f"option_{rejected_option}_label"]
            sb.table("interaction_logs").insert({
                "user_id": user_id,
                "interaction_type": "onboarding_choice",
                "payload": {
                    "question_index": ans.question_index,
                    "chosen_option": chosen_label,
                    "rejected_option": rejected_label,
                    "dimension_signals": q[f"option_{ans.chosen_option}_signals"],
                },
            }).execute()

        return {"status": "ok", "profile": row}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete onboarding: {e}")


# ── Taste Profile ──

@router.get("/profile/taste")
async def get_taste_profile(user_id: str = Depends(get_current_user_id)):
    try:
        sb = _get_supabase()
        result = sb.table("user_taste_profiles").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Taste profile not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get taste profile: {e}")


# ── Interaction Logging ──

@router.post("/interactions/log")
async def log_interaction(
    req: InteractionLogCreate,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    try:
        sb = _get_supabase()
        row = {
            "user_id": user_id,
            "interaction_type": req.interaction_type.value,
            "payload": req.payload,
        }
        result = sb.table("interaction_logs").insert(row).execute()

        # Kick off preference engine in the background (non-blocking)
        from engines.preference_engine import process_and_update_profile
        background_tasks.add_task(
            process_and_update_profile,
            user_id,
            req.interaction_type.value,
            req.payload,
            sb,
        )

        return {"status": "ok", "id": result.data[0]["id"] if result.data else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log interaction: {e}")


# ── Saved Dishes ──

@router.get("/dishes/saved")
async def get_saved_dishes(user_id: str = Depends(get_current_user_id)):
    try:
        sb = _get_supabase()
        result = sb.table("saved_dishes").select("*").eq("user_id", user_id).order("saved_at", desc=True).execute()
        return {"dishes": result.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get saved dishes: {e}")


@router.post("/dishes/save")
async def save_dish(
    req: SavedDishCreate,
    user_id: str = Depends(get_current_user_id),
):
    try:
        sb = _get_supabase()
        row = {
            "user_id": user_id,
            "dish_name": req.dish_name,
            "restaurant_slug": req.restaurant_slug,
            "restaurant_name": req.restaurant_name,
            "price": req.price,
            "category": req.category,
            "dietary_info": req.dietary_info,
            "notes": req.notes,
        }
        result = sb.table("saved_dishes").insert(row).execute()
        return {"status": "ok", "dish": result.data[0] if result.data else None}
    except Exception as e:
        error_msg = str(e)
        if "duplicate" in error_msg.lower() or "unique" in error_msg.lower() or "23505" in error_msg:
            raise HTTPException(status_code=409, detail="Dish already saved")
        raise HTTPException(status_code=500, detail=f"Failed to save dish: {e}")


# ── Personalized Restaurants ──

def _get_menu_items_for_slug(slug: str) -> list[dict]:
    """Load menu items for a restaurant slug from the global MENU_INDEX."""
    try:
        from main import MENU_INDEX
        return [item for item in MENU_INDEX if item.get("restaurant_slug") == slug]
    except Exception:
        return []


@router.get("/restaurants/personalized")
async def get_personalized_restaurants(
    user_id: str = Depends(get_current_user_id),
):
    try:
        from engines.restaurant_scorer import (
            get_cached_signature,
            score_restaurant_for_user,
            find_top_dish_for_user,
        )
        from main import RESTAURANT_LIST, REVERSE_MAPPING, PLACES_DATA, MENU_INDEX

        # Fetch user profile
        sb = _get_supabase()
        result = sb.table("user_taste_profiles").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Taste profile not found. Complete onboarding first.")
        user_profile = result.data[0]

        # Pre-group menu items by slug for O(n) lookup
        items_by_slug: dict[str, list[dict]] = {}
        for item in MENU_INDEX:
            s = item.get("restaurant_slug")
            if s:
                items_by_slug.setdefault(s, []).append(item)

        restaurants = []
        for display_name in RESTAURANT_LIST:
            slug = REVERSE_MAPPING.get(display_name.lower())
            if not slug:
                continue

            rest_info: dict = {
                "name": display_name, "slug": slug,
                "lat": None, "lng": None, "rating": None,
                "reviews": None, "address": None,
            }
            if slug in PLACES_DATA:
                pdata = PLACES_DATA[slug]
                if "error" not in pdata:
                    rest_info["lat"] = pdata.get("lat")
                    rest_info["lng"] = pdata.get("lng")
                    rest_info["rating"] = pdata.get("rating")
                    rest_info["reviews"] = pdata.get("user_ratings_total")
                    rest_info["address"] = pdata.get("address")

            menu_items = items_by_slug.get(slug, [])
            sig = get_cached_signature(slug, menu_items)
            rest_info["match_score"] = score_restaurant_for_user(user_profile, sig)
            rest_info["top_dish"] = find_top_dish_for_user(user_profile, menu_items, sig)
            restaurants.append(rest_info)

        restaurants.sort(key=lambda r: r.get("match_score", 0), reverse=True)
        return {"restaurants": restaurants}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get personalized restaurants: {e}")


@router.get("/restaurants/{slug}/personalized")
async def get_personalized_restaurant_detail(
    slug: str,
    user_id: str = Depends(get_current_user_id),
):
    try:
        from engines.restaurant_scorer import (
            get_cached_signature,
            score_restaurant_for_user,
            find_top_n_dishes_for_user,
            find_avoid_dishes,
        )
        from main import NAME_MAPPING, PLACES_DATA

        if slug not in NAME_MAPPING:
            raise HTTPException(status_code=404, detail="Restaurant not found")

        sb = _get_supabase()
        result = sb.table("user_taste_profiles").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Taste profile not found")
        user_profile = result.data[0]

        menu_items = _get_menu_items_for_slug(slug)
        sig = get_cached_signature(slug, menu_items)

        display_name = NAME_MAPPING[slug]
        rest_info: dict = {
            "name": display_name, "slug": slug,
            "lat": None, "lng": None, "rating": None,
            "reviews": None, "address": None,
        }
        if slug in PLACES_DATA:
            pdata = PLACES_DATA[slug]
            if "error" not in pdata:
                rest_info["lat"] = pdata.get("lat")
                rest_info["lng"] = pdata.get("lng")
                rest_info["rating"] = pdata.get("rating")
                rest_info["reviews"] = pdata.get("user_ratings_total")
                rest_info["address"] = pdata.get("address")

        rest_info["match_score"] = score_restaurant_for_user(user_profile, sig)
        rest_info["top_3_dishes"] = find_top_n_dishes_for_user(user_profile, menu_items, n=3)
        rest_info["avoid_dishes"] = find_avoid_dishes(user_profile, menu_items)

        return rest_info

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get restaurant details: {e}")


@router.delete("/dishes/save/{dish_id}")
async def delete_saved_dish(
    dish_id: str,
    user_id: str = Depends(get_current_user_id),
):
    try:
        sb = _get_supabase()
        result = sb.table("saved_dishes").delete().eq("id", dish_id).eq("user_id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Saved dish not found")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete saved dish: {e}")
