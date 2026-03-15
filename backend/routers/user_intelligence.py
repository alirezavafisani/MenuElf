import os
from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

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
        "option_a_label": "spicy_ramen",
        "option_a_signals": {"spice_tolerance": 0.8, "adventurousness": 0.7, "cuisine_preferences.japanese": 0.9},
        "option_b_label": "caesar_salad",
        "option_b_signals": {"spice_tolerance": 0.2, "adventurousness": 0.3, "cuisine_preferences.italian": 0.7},
    },
    {
        "question_index": 2,
        "option_a_label": "sushi_platter",
        "option_a_signals": {"adventurousness": 0.8, "cuisine_preferences.japanese": 0.9, "protein_preference.fish": 0.8},
        "option_b_label": "burger_and_fries",
        "option_b_signals": {"adventurousness": 0.3, "cuisine_preferences.american": 0.9, "protein_preference.beef": 0.8, "price_comfort": 0.3},
    },
    {
        "question_index": 3,
        "option_a_label": "pad_thai",
        "option_a_signals": {"spice_tolerance": 0.6, "cuisine_preferences.thai": 0.9, "adventurousness": 0.6},
        "option_b_label": "mac_and_cheese",
        "option_b_signals": {"spice_tolerance": 0.1, "adventurousness": 0.2, "texture_preferences.creamy": 0.9, "price_comfort": 0.2},
    },
    {
        "question_index": 4,
        "option_a_label": "tikka_masala",
        "option_a_signals": {"spice_tolerance": 0.7, "cuisine_preferences.indian": 0.9, "adventurousness": 0.6},
        "option_b_label": "grilled_chicken",
        "option_b_signals": {"spice_tolerance": 0.2, "adventurousness": 0.2, "protein_preference.chicken": 0.9, "price_comfort": 0.4},
    },
    {
        "question_index": 5,
        "option_a_label": "bibimbap",
        "option_a_signals": {"adventurousness": 0.8, "cuisine_preferences.korean": 0.9, "spice_tolerance": 0.6},
        "option_b_label": "pepperoni_pizza",
        "option_b_signals": {"adventurousness": 0.2, "cuisine_preferences.italian": 0.8, "price_comfort": 0.3},
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


# ===================================================================
# Endpoints
# ===================================================================

# ── Onboarding ──

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
