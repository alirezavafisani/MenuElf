import os
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

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
        key = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get(
            "SUPABASE_KEY", ""
        )
        if not url or not key:
            raise HTTPException(status_code=500, detail="Supabase not configured")
        _supabase_client = create_client(url, key)
    return _supabase_client


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
_ensured_users: set = set()


def _ensure_user_exists(user_id: str):
    if user_id in _ensured_users:
        return
    try:
        sb = _get_supabase()
        sb.auth.admin.create_user(
            {
                "id": user_id,
                "email": f"dev-{user_id[:8]}@menuelf.dev",
                "password": "menuelf-dev-auto-created",
                "email_confirm": True,
            }
        )
    except Exception:
        pass
    _ensured_users.add(user_id)


async def get_current_user_id(
    authorization: str = Header(default=""),
    x_user_id: str = Header(default=""),
) -> str:
    if x_user_id:
        _ensure_user_exists(x_user_id)
        return x_user_id
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid authorization header"
        )
    token = authorization.replace("Bearer ", "")
    try:
        sb = _get_supabase()
        user_resp = sb.auth.get_user(token)
        return str(user_resp.user.id)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CreatePlanRequest(BaseModel):
    name: str
    friend_ids: List[str]


class SendMessageRequest(BaseModel):
    content: str


class DecideRestaurantRequest(BaseModel):
    restaurant_slug: str


# ---------------------------------------------------------------------------
# AI trigger words
# ---------------------------------------------------------------------------

_AI_TRIGGER_WORDS = [
    "menuelf",
    "@menuelf",
    "suggest",
    "recommend",
    "where should we",
    "help us",
    "what do you think",
    "any ideas",
    "pick a place",
    "decide",
]

_FOOD_WORDS = [
    "eat",
    "food",
    "restaurant",
    "dinner",
    "lunch",
    "breakfast",
    "cuisine",
    "hungry",
    "meal",
    "dish",
    "menu",
    "place",
    "order",
    "spicy",
    "vegetarian",
    "vegan",
    "pizza",
    "sushi",
    "thai",
    "italian",
    "chinese",
    "indian",
    "mexican",
    "burger",
    "pasta",
    "steak",
    "ramen",
    "tacos",
]


def _should_ai_respond(content: str, is_first_message: bool) -> bool:
    """Determine if the AI coordinator should respond to this message."""
    if is_first_message:
        return True

    lower = content.lower()

    # Check trigger words
    for trigger in _AI_TRIGGER_WORDS:
        if trigger in lower:
            return True

    # Check if question with food words
    if lower.rstrip().endswith("?"):
        for word in _FOOD_WORDS:
            if word in lower:
                return True

    return False


# ---------------------------------------------------------------------------
# AI response generation
# ---------------------------------------------------------------------------

# Overridable for testing
_ai_generate_fn = None


def _generate_ai_response(
    plan_id: str, members_context: str, constraints: str, messages_context: str
) -> str:
    """Generate an AI coordinator response using OpenAI."""
    if _ai_generate_fn is not None:
        return _ai_generate_fn(
            plan_id, members_context, constraints, messages_context
        )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        system_prompt = f"""You are MenuElf, a friendly AI dining coordinator helping a group of friends decide where to eat in Calgary.

GROUP MEMBERS AND THEIR TASTES:
{members_context}

GROUP CONSTRAINTS:
{constraints}

CONVERSATION SO FAR:
{messages_context}

GUIDELINES:
- Be concise and helpful. 2-3 sentences max unless asked for detail.
- Suggest restaurants where everyone can find something they love.
- When suggesting, briefly explain why it works for each person.
- If the group is leaning toward a place, support it and suggest dishes for each person.
- Do NOT dominate the conversation. Only speak when asked or when you can genuinely help.
- Be warm and natural, like a knowledgeable friend, not a formal assistant.
- If you suggest a restaurant, mention 1 specific dish per person with price.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Please respond to the latest message in the group chat."},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        return response.choices[0].message.content or "I'm here to help when you need me!"
    except Exception as e:
        print(f"AI generation error: {e}", flush=True)
        return "I'm having trouble thinking right now. Ask me again in a moment!"


def _build_members_context(joined_members: list) -> tuple:
    """Build the members context string and constraints for AI prompt.

    Returns (members_context, constraints_text).
    """
    sb = _get_supabase()
    lines = []
    all_restrictions = set()
    price_values = []

    for member in joined_members:
        uid = member.get("user_id", "")
        profile_res = (
            sb.table("user_profiles")
            .select("display_name,username")
            .eq("id", uid)
            .execute()
        )
        name = "Unknown"
        if profile_res.data:
            name = profile_res.data[0].get("display_name") or profile_res.data[0].get("username", "Unknown")

        taste_res = (
            sb.table("user_taste_profiles")
            .select("*")
            .eq("id", uid)
            .execute()
        )
        if taste_res.data:
            tp = taste_res.data[0]
            try:
                from engines.profile_narrator import narrate_profile

                narration = narrate_profile(tp)
                lines.append(f"- {name}: {narration}")
            except Exception:
                lines.append(f"- {name}: (taste profile available)")

            restrictions = tp.get("dietary_restrictions", [])
            if isinstance(restrictions, list):
                all_restrictions.update(restrictions)
            price_values.append(tp.get("price_comfort", 0.5))
        else:
            lines.append(f"- {name}: (no taste profile yet)")

    members_context = "\n".join(lines) if lines else "No member profiles available."

    constraint_parts = []
    if all_restrictions:
        constraint_parts.append(
            f"- Dietary restrictions to respect: {', '.join(all_restrictions)}"
        )
    if price_values:
        min_p = min(price_values)
        max_p = max(price_values)
        budget_desc = "budget-conscious" if min_p < 0.3 else "moderate" if min_p < 0.7 else "happy to splurge"
        constraint_parts.append(f"- Budget range: {budget_desc}")
    constraints = "\n".join(constraint_parts) if constraint_parts else "No special constraints."

    return members_context, constraints


def _build_messages_context(plan_id: str, limit: int = 20) -> str:
    """Build a text representation of recent messages."""
    sb = _get_supabase()
    result = (
        sb.table("group_messages")
        .select("sender_type,sender_id,content")
        .eq("plan_id", plan_id)
        .order("created_at", desc=False)
        .execute()
    )
    messages = result.data or []
    recent = messages[-limit:]

    lines = []
    for msg in recent:
        if msg["sender_type"] == "ai":
            lines.append(f"MenuElf: {msg['content']}")
        else:
            # Look up sender name
            sender_name = "User"
            if msg.get("sender_id"):
                try:
                    pr = (
                        sb.table("user_profiles")
                        .select("display_name,username")
                        .eq("id", msg["sender_id"])
                        .execute()
                    )
                    if pr.data:
                        sender_name = pr.data[0].get("display_name") or pr.data[0].get("username", "User")
                except Exception:
                    pass
            lines.append(f"{sender_name}: {msg['content']}")

    return "\n".join(lines) if lines else "(No messages yet)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_plan_member(plan_id: str, user_id: str) -> bool:
    sb = _get_supabase()
    result = (
        sb.table("dining_plan_members")
        .select("id")
        .eq("plan_id", plan_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)


def _is_joined_member(plan_id: str, user_id: str) -> bool:
    sb = _get_supabase()
    result = (
        sb.table("dining_plan_members")
        .select("id")
        .eq("plan_id", plan_id)
        .eq("user_id", user_id)
        .eq("status", "joined")
        .execute()
    )
    return bool(result.data)


def _get_plan(plan_id: str) -> dict:
    sb = _get_supabase()
    result = sb.table("dining_plans").select("*").eq("id", plan_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Plan not found")
    return result.data[0]


def _get_plan_members(plan_id: str) -> list:
    sb = _get_supabase()
    result = (
        sb.table("dining_plan_members")
        .select("*")
        .eq("plan_id", plan_id)
        .execute()
    )
    return result.data or []


def _get_joined_members(plan_id: str) -> list:
    sb = _get_supabase()
    result = (
        sb.table("dining_plan_members")
        .select("*")
        .eq("plan_id", plan_id)
        .eq("status", "joined")
        .execute()
    )
    return result.data or []


# ---------------------------------------------------------------------------
# Plan Management
# ---------------------------------------------------------------------------


@router.post("/plans")
async def create_plan(
    body: CreatePlanRequest, user_id: str = Depends(get_current_user_id)
):
    try:
        if not body.name or not body.name.strip():
            raise HTTPException(status_code=400, detail="Plan name is required")
        if not body.friend_ids:
            raise HTTPException(
                status_code=400, detail="At least one friend is required"
            )

        sb = _get_supabase()

        # Create plan
        plan_row = {"creator_id": user_id, "name": body.name.strip(), "status": "active"}
        plan_result = sb.table("dining_plans").insert(plan_row).execute()
        plan = plan_result.data[0] if plan_result.data else plan_row
        plan_id = plan["id"]

        # Add creator as joined
        sb.table("dining_plan_members").insert(
            {
                "plan_id": plan_id,
                "user_id": user_id,
                "status": "joined",
                "joined_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

        # Add friends as invited
        for fid in body.friend_ids:
            if fid != user_id:
                try:
                    sb.table("dining_plan_members").insert(
                        {"plan_id": plan_id, "user_id": fid, "status": "invited"}
                    ).execute()
                except Exception:
                    pass  # Skip duplicates

        members = _get_plan_members(plan_id)
        return {"plan": plan, "members": members}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create plan: {e}")


@router.get("/plans")
async def list_plans(user_id: str = Depends(get_current_user_id)):
    try:
        sb = _get_supabase()

        # Get all plan_ids where user is a member
        member_rows = (
            sb.table("dining_plan_members")
            .select("plan_id,status")
            .eq("user_id", user_id)
            .execute()
        )
        if not member_rows.data:
            return {"plans": []}

        plans = []
        for mr in member_rows.data:
            try:
                plan_result = (
                    sb.table("dining_plans")
                    .select("*")
                    .eq("id", mr["plan_id"])
                    .execute()
                )
                if plan_result.data:
                    plan = plan_result.data[0]
                    plan["my_status"] = mr["status"]

                    # Get member profiles
                    members = _get_plan_members(mr["plan_id"])
                    member_profiles = []
                    for m in members:
                        pr = (
                            sb.table("user_profiles")
                            .select("username,display_name,avatar_emoji")
                            .eq("id", m["user_id"])
                            .execute()
                        )
                        profile = pr.data[0] if pr.data else {}
                        member_profiles.append(
                            {**m, "profile": profile}
                        )
                    plan["members"] = member_profiles
                    plans.append(plan)
            except Exception:
                continue

        return {"plans": plans}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list plans: {e}")


@router.get("/plans/{plan_id}")
async def get_plan_detail(
    plan_id: str, user_id: str = Depends(get_current_user_id)
):
    try:
        if not _is_plan_member(plan_id, user_id):
            raise HTTPException(status_code=403, detail="Not a member of this plan")

        plan = _get_plan(plan_id)
        members = _get_plan_members(plan_id)

        sb = _get_supabase()
        enriched_members = []
        for m in members:
            pr = (
                sb.table("user_profiles")
                .select("username,display_name,avatar_emoji")
                .eq("id", m["user_id"])
                .execute()
            )
            profile = pr.data[0] if pr.data else {}
            enriched_members.append({**m, "profile": profile})

        plan["members"] = enriched_members
        return {"plan": plan}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plan: {e}")


@router.post("/plans/{plan_id}/join")
async def join_plan(
    plan_id: str, user_id: str = Depends(get_current_user_id)
):
    try:
        sb = _get_supabase()

        result = (
            sb.table("dining_plan_members")
            .select("*")
            .eq("plan_id", plan_id)
            .eq("user_id", user_id)
            .eq("status", "invited")
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=404, detail="No pending invitation found"
            )

        sb.table("dining_plan_members").update(
            {
                "status": "joined",
                "joined_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("plan_id", plan_id).eq("user_id", user_id).execute()

        return {"status": "joined"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to join plan: {e}")


@router.post("/plans/{plan_id}/decline")
async def decline_plan(
    plan_id: str, user_id: str = Depends(get_current_user_id)
):
    try:
        sb = _get_supabase()

        result = (
            sb.table("dining_plan_members")
            .select("*")
            .eq("plan_id", plan_id)
            .eq("user_id", user_id)
            .eq("status", "invited")
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=404, detail="No pending invitation found"
            )

        sb.table("dining_plan_members").update({"status": "declined"}).eq(
            "plan_id", plan_id
        ).eq("user_id", user_id).execute()

        return {"status": "declined"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decline plan: {e}")


@router.post("/plans/{plan_id}/cancel")
async def cancel_plan(
    plan_id: str, user_id: str = Depends(get_current_user_id)
):
    try:
        plan = _get_plan(plan_id)
        if plan["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the creator can cancel the plan"
            )

        sb = _get_supabase()
        sb.table("dining_plans").update({"status": "cancelled"}).eq(
            "id", plan_id
        ).execute()

        return {"status": "cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel plan: {e}")


@router.post("/plans/{plan_id}/decide")
async def decide_restaurant(
    plan_id: str,
    body: DecideRestaurantRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        plan = _get_plan(plan_id)
        if plan["creator_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Only the creator can decide the restaurant"
            )

        sb = _get_supabase()
        sb.table("dining_plans").update(
            {"status": "decided", "decided_restaurant_slug": body.restaurant_slug}
        ).eq("id", plan_id).execute()

        return {"status": "decided", "restaurant_slug": body.restaurant_slug}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to decide restaurant: {e}"
        )


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@router.get("/plans/{plan_id}/messages")
async def get_messages(
    plan_id: str,
    after: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
):
    try:
        if not _is_plan_member(plan_id, user_id):
            raise HTTPException(status_code=403, detail="Not a member of this plan")

        sb = _get_supabase()
        result = (
            sb.table("group_messages")
            .select("*")
            .eq("plan_id", plan_id)
            .order("created_at", desc=False)
            .execute()
        )
        messages = result.data or []

        # Filter by timestamp if provided
        if after:
            messages = [m for m in messages if m.get("created_at", "") > after]

        # Enrich with sender profiles
        enriched = []
        for msg in messages[-50:]:
            sender_profile = None
            if msg.get("sender_id") and msg["sender_type"] == "user":
                pr = (
                    sb.table("user_profiles")
                    .select("username,display_name,avatar_emoji")
                    .eq("id", msg["sender_id"])
                    .execute()
                )
                sender_profile = pr.data[0] if pr.data else None
            enriched.append({**msg, "sender_profile": sender_profile})

        return {"messages": enriched}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {e}")


@router.post("/plans/{plan_id}/messages")
async def send_message(
    plan_id: str,
    body: SendMessageRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        if not body.content or not body.content.strip():
            raise HTTPException(status_code=400, detail="Message content is required")

        if not _is_joined_member(plan_id, user_id):
            raise HTTPException(
                status_code=403,
                detail="You must join the plan before sending messages",
            )

        plan = _get_plan(plan_id)
        if plan.get("status") == "cancelled":
            raise HTTPException(status_code=400, detail="This plan has been cancelled")

        sb = _get_supabase()

        # Check if this is the first message
        existing = (
            sb.table("group_messages")
            .select("id")
            .eq("plan_id", plan_id)
            .execute()
        )
        is_first = not existing.data

        # Save user message
        now = datetime.now(timezone.utc).isoformat()
        user_msg_row = {
            "plan_id": plan_id,
            "sender_id": user_id,
            "sender_type": "user",
            "content": body.content.strip(),
            "created_at": now,
        }
        user_msg_result = sb.table("group_messages").insert(user_msg_row).execute()
        user_msg = user_msg_result.data[0] if user_msg_result.data else user_msg_row

        # Check if AI should respond
        ai_message = None
        if _should_ai_respond(body.content, is_first):
            try:
                joined = _get_joined_members(plan_id)
                members_ctx, constraints_ctx = _build_members_context(joined)
                messages_ctx = _build_messages_context(plan_id)

                ai_text = _generate_ai_response(
                    plan_id, members_ctx, constraints_ctx, messages_ctx
                )

                ai_msg_row = {
                    "plan_id": plan_id,
                    "sender_id": None,
                    "sender_type": "ai",
                    "content": ai_text,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                ai_result = sb.table("group_messages").insert(ai_msg_row).execute()
                ai_message = ai_result.data[0] if ai_result.data else ai_msg_row
            except Exception as e:
                print(f"AI response generation failed: {e}", flush=True)

        return {
            "message": user_msg,
            "ai_response": ai_message,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {e}")


# ---------------------------------------------------------------------------
# Group Recommendations
# ---------------------------------------------------------------------------


@router.get("/plans/{plan_id}/recommendations")
async def get_group_recommendations(
    plan_id: str, user_id: str = Depends(get_current_user_id)
):
    try:
        if not _is_plan_member(plan_id, user_id):
            raise HTTPException(status_code=403, detail="Not a member of this plan")

        sb = _get_supabase()
        joined = _get_joined_members(plan_id)

        if not joined:
            return {"restaurants": []}

        # Get taste profiles for joined members
        member_profiles = []
        member_names = {}
        for m in joined:
            uid = m["user_id"]
            taste_res = (
                sb.table("user_taste_profiles")
                .select("*")
                .eq("id", uid)
                .execute()
            )
            if taste_res.data:
                member_profiles.append({"user_id": uid, "profile": taste_res.data[0]})

            pr = (
                sb.table("user_profiles")
                .select("display_name,username,avatar_emoji")
                .eq("id", uid)
                .execute()
            )
            if pr.data:
                member_names[uid] = pr.data[0]

        if not member_profiles:
            return {"restaurants": []}

        # Load all restaurant menus and score
        try:
            from engines.restaurant_scorer import (
                build_restaurant_signature,
                score_restaurant_for_user,
                find_top_dish_for_user,
            )

            import json as _json

            BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            MENUS_DIR = os.environ.get(
                "MENUS_DIR", os.path.join(BASE_DIR, "menus")
            )

            if not os.path.isdir(MENUS_DIR):
                return {"restaurants": []}

            restaurant_scores = []

            for fn in os.listdir(MENUS_DIR):
                if not fn.endswith(".json"):
                    continue
                slug = fn.replace(".json", "")
                try:
                    with open(os.path.join(MENUS_DIR, fn), "r", encoding="utf-8") as f:
                        menu = _json.load(f)

                    items = menu if isinstance(menu, list) else menu.get("items", menu.get("menu", []))
                    if not items:
                        continue

                    sig = build_restaurant_signature(items)

                    # Score for each member
                    scores = []
                    per_member = []
                    for mp in member_profiles:
                        score = score_restaurant_for_user(mp["profile"], sig)
                        scores.append(score)

                        top = find_top_dish_for_user(mp["profile"], items, sig)
                        uid = mp["user_id"]
                        info = member_names.get(uid, {})
                        per_member.append(
                            {
                                "user_id": uid,
                                "display_name": info.get("display_name")
                                or info.get("username", ""),
                                "avatar_emoji": info.get("avatar_emoji", "🧝"),
                                "top_dish": top,
                                "match_score": round(score),
                            }
                        )

                    avg_score = sum(scores) / len(scores) if scores else 0
                    restaurant_scores.append(
                        {
                            "slug": slug,
                            "name": slug.replace("-", " ").replace("_", " ").title(),
                            "group_match_score": round(avg_score),
                            "per_member": per_member,
                        }
                    )
                except Exception:
                    continue

            # Sort by group match score
            restaurant_scores.sort(
                key=lambda r: r["group_match_score"], reverse=True
            )

            return {"restaurants": restaurant_scores[:10]}

        except ImportError:
            return {"restaurants": []}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get recommendations: {e}"
        )
