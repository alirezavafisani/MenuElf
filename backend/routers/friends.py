import os
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter()

# ---------------------------------------------------------------------------
# Supabase client helper (same pattern as user_intelligence)
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
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")


class ProfileSetupRequest(BaseModel):
    username: str
    display_name: Optional[str] = None
    avatar_emoji: Optional[str] = "🧝"

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3-20 characters, lowercase alphanumeric and underscores only"
            )
        return v


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_emoji: Optional[str] = None


class FriendRequestCreate(BaseModel):
    username: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_friends_of(user_id: str) -> list:
    """Return list of friend user IDs for a given user."""
    sb = _get_supabase()
    rows_a = (
        sb.table("friendships").select("user_b_id").eq("user_a_id", user_id).execute()
    )
    rows_b = (
        sb.table("friendships").select("user_a_id").eq("user_b_id", user_id).execute()
    )
    friend_ids = [r["user_b_id"] for r in (rows_a.data or [])]
    friend_ids += [r["user_a_id"] for r in (rows_b.data or [])]
    return friend_ids


def _are_friends(user_a: str, user_b: str) -> bool:
    """Check if two users are friends."""
    a, b = sorted([user_a, user_b])
    sb = _get_supabase()
    result = (
        sb.table("friendships")
        .select("id")
        .eq("user_a_id", a)
        .eq("user_b_id", b)
        .execute()
    )
    return len(result.data or []) > 0


# ---------------------------------------------------------------------------
# Profile Management
# ---------------------------------------------------------------------------


@router.post("/profile/setup")
async def setup_profile(
    body: ProfileSetupRequest, user_id: str = Depends(get_current_user_id)
):
    try:
        sb = _get_supabase()

        # Check if user already has a profile
        existing = (
            sb.table("user_profiles").select("id").eq("id", user_id).execute()
        )
        if existing.data:
            raise HTTPException(status_code=409, detail="Profile already exists")

        # Check if username is taken
        taken = (
            sb.table("user_profiles")
            .select("id")
            .eq("username", body.username)
            .execute()
        )
        if taken.data:
            raise HTTPException(status_code=409, detail="Username already taken")

        profile = {
            "id": user_id,
            "username": body.username,
            "display_name": body.display_name or body.username,
            "avatar_emoji": body.avatar_emoji or "🧝",
        }
        result = sb.table("user_profiles").insert(profile).execute()
        return {"profile": result.data[0] if result.data else profile}

    except HTTPException:
        raise
    except Exception as e:
        if "23505" in str(e):
            raise HTTPException(status_code=409, detail="Username already taken")
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {e}")


@router.get("/profile/me")
async def get_my_profile(user_id: str = Depends(get_current_user_id)):
    try:
        sb = _get_supabase()
        result = (
            sb.table("user_profiles").select("*").eq("id", user_id).execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"profile": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {e}")


@router.put("/profile/me")
async def update_my_profile(
    body: ProfileUpdateRequest, user_id: str = Depends(get_current_user_id)
):
    try:
        sb = _get_supabase()
        updates = {}
        if body.display_name is not None:
            updates["display_name"] = body.display_name
        if body.avatar_emoji is not None:
            updates["avatar_emoji"] = body.avatar_emoji
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        result = (
            sb.table("user_profiles").update(updates).eq("id", user_id).execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"profile": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {e}")


@router.get("/profile/{username}")
async def get_profile_by_username(username: str):
    try:
        sb = _get_supabase()
        result = (
            sb.table("user_profiles")
            .select("id,username,display_name,avatar_emoji")
            .eq("username", username.lower())
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        return {"profile": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {e}")


# ---------------------------------------------------------------------------
# Friend Requests
# ---------------------------------------------------------------------------


@router.post("/friends/request")
async def send_friend_request(
    body: FriendRequestCreate, user_id: str = Depends(get_current_user_id)
):
    try:
        sb = _get_supabase()

        # Look up target user by username
        target = (
            sb.table("user_profiles")
            .select("id,username")
            .eq("username", body.username.lower().strip())
            .execute()
        )
        if not target.data:
            raise HTTPException(status_code=404, detail="User not found")

        target_id = target.data[0]["id"]

        # Cannot friend yourself
        if target_id == user_id:
            raise HTTPException(
                status_code=400, detail="Cannot send a friend request to yourself"
            )

        # Check if already friends
        if _are_friends(user_id, target_id):
            raise HTTPException(
                status_code=400, detail="You are already friends with this user"
            )

        # Check for existing pending request in either direction
        existing_out = (
            sb.table("friend_requests")
            .select("id,status")
            .eq("from_user_id", user_id)
            .eq("to_user_id", target_id)
            .execute()
        )
        for req in existing_out.data or []:
            if req["status"] == "pending":
                raise HTTPException(
                    status_code=409, detail="Friend request already sent"
                )

        existing_in = (
            sb.table("friend_requests")
            .select("id,status")
            .eq("from_user_id", target_id)
            .eq("to_user_id", user_id)
            .execute()
        )
        for req in existing_in.data or []:
            if req["status"] == "pending":
                raise HTTPException(
                    status_code=409,
                    detail="This user already sent you a request. Check your incoming requests.",
                )

        request_row = {
            "from_user_id": user_id,
            "to_user_id": target_id,
            "status": "pending",
        }
        result = sb.table("friend_requests").insert(request_row).execute()
        return {"request": result.data[0] if result.data else request_row}

    except HTTPException:
        raise
    except Exception as e:
        if "23505" in str(e):
            raise HTTPException(status_code=409, detail="Friend request already sent")
        raise HTTPException(
            status_code=500, detail=f"Failed to send friend request: {e}"
        )


@router.get("/friends/requests/incoming")
async def get_incoming_requests(user_id: str = Depends(get_current_user_id)):
    try:
        sb = _get_supabase()
        result = (
            sb.table("friend_requests")
            .select("*")
            .eq("to_user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        requests = result.data or []

        # Enrich with sender profiles
        enriched = []
        for req in requests:
            profile_result = (
                sb.table("user_profiles")
                .select("username,display_name,avatar_emoji")
                .eq("id", req["from_user_id"])
                .execute()
            )
            sender_profile = profile_result.data[0] if profile_result.data else {}
            enriched.append({**req, "from_profile": sender_profile})

        return {"requests": enriched}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get incoming requests: {e}"
        )


@router.get("/friends/requests/outgoing")
async def get_outgoing_requests(user_id: str = Depends(get_current_user_id)):
    try:
        sb = _get_supabase()
        result = (
            sb.table("friend_requests")
            .select("*")
            .eq("from_user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        requests = result.data or []

        # Enrich with recipient profiles
        enriched = []
        for req in requests:
            profile_result = (
                sb.table("user_profiles")
                .select("username,display_name,avatar_emoji")
                .eq("id", req["to_user_id"])
                .execute()
            )
            recipient_profile = (
                profile_result.data[0] if profile_result.data else {}
            )
            enriched.append({**req, "to_profile": recipient_profile})

        return {"requests": enriched}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get outgoing requests: {e}"
        )


@router.post("/friends/requests/{request_id}/accept")
async def accept_friend_request(
    request_id: str, user_id: str = Depends(get_current_user_id)
):
    try:
        sb = _get_supabase()

        # Get the request
        result = (
            sb.table("friend_requests")
            .select("*")
            .eq("id", request_id)
            .eq("to_user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=404, detail="Friend request not found or already handled"
            )

        req = result.data[0]
        from_id = req["from_user_id"]

        # Update request status
        sb.table("friend_requests").update({"status": "accepted"}).eq(
            "id", request_id
        ).execute()

        # Create friendship (enforce ordering a < b)
        a, b = sorted([user_id, from_id])
        sb.table("friendships").insert(
            {"user_a_id": a, "user_b_id": b}
        ).execute()

        return {"status": "accepted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to accept request: {e}"
        )


@router.post("/friends/requests/{request_id}/decline")
async def decline_friend_request(
    request_id: str, user_id: str = Depends(get_current_user_id)
):
    try:
        sb = _get_supabase()

        result = (
            sb.table("friend_requests")
            .select("*")
            .eq("id", request_id)
            .eq("to_user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=404, detail="Friend request not found or already handled"
            )

        sb.table("friend_requests").update({"status": "declined"}).eq(
            "id", request_id
        ).execute()

        return {"status": "declined"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to decline request: {e}"
        )


# ---------------------------------------------------------------------------
# Friends List
# ---------------------------------------------------------------------------


@router.get("/friends")
async def get_friends(user_id: str = Depends(get_current_user_id)):
    try:
        sb = _get_supabase()
        friend_ids = _get_friends_of(user_id)

        friends = []
        for fid in friend_ids:
            # Get profile
            profile_result = (
                sb.table("user_profiles")
                .select("id,username,display_name,avatar_emoji")
                .eq("id", fid)
                .execute()
            )
            profile = profile_result.data[0] if profile_result.data else None
            if not profile:
                continue

            # Get taste profile summary
            taste_result = (
                sb.table("user_taste_profiles")
                .select("cuisine_preferences,dietary_restrictions")
                .eq("id", fid)
                .execute()
            )
            taste_summary = {}
            if taste_result.data:
                tp = taste_result.data[0]
                cuisines = tp.get("cuisine_preferences", {})
                if isinstance(cuisines, dict):
                    top_cuisines = sorted(
                        cuisines.items(), key=lambda x: x[1], reverse=True
                    )[:3]
                    taste_summary["top_cuisines"] = [
                        c[0] for c in top_cuisines
                    ]
                taste_summary["dietary_restrictions"] = tp.get(
                    "dietary_restrictions", []
                )

            friends.append({**profile, "taste_summary": taste_summary})

        return {"friends": friends}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get friends: {e}")


@router.delete("/friends/{friend_user_id}")
async def remove_friend(
    friend_user_id: str, user_id: str = Depends(get_current_user_id)
):
    try:
        sb = _get_supabase()
        a, b = sorted([user_id, friend_user_id])

        result = (
            sb.table("friendships")
            .select("id")
            .eq("user_a_id", a)
            .eq("user_b_id", b)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Friendship not found")

        sb.table("friendships").delete().eq("user_a_id", a).eq(
            "user_b_id", b
        ).execute()

        return {"status": "removed"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove friend: {e}")


# ---------------------------------------------------------------------------
# User Search
# ---------------------------------------------------------------------------


@router.get("/users/search")
async def search_users(
    q: str = "", user_id: str = Depends(get_current_user_id)
):
    try:
        if not q or len(q.strip()) < 1:
            return {"users": []}

        sb = _get_supabase()
        query = q.strip().lower()

        # Get all profiles (in production, use ilike/text search)
        result = sb.table("user_profiles").select("id,username,display_name,avatar_emoji").execute()
        all_profiles = result.data or []

        # Filter by prefix match on username
        matches = [
            p
            for p in all_profiles
            if p.get("username", "").startswith(query) and p["id"] != user_id
        ]

        # Exclude existing friends and pending requests
        friend_ids = set(_get_friends_of(user_id))

        pending_out = (
            sb.table("friend_requests")
            .select("to_user_id")
            .eq("from_user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        pending_in = (
            sb.table("friend_requests")
            .select("from_user_id")
            .eq("to_user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        pending_ids = set(
            [r["to_user_id"] for r in (pending_out.data or [])]
            + [r["from_user_id"] for r in (pending_in.data or [])]
        )

        exclude_ids = friend_ids | pending_ids
        filtered = [p for p in matches if p["id"] not in exclude_ids]

        return {"users": filtered[:10]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


# ---------------------------------------------------------------------------
# DELETE /profile/account — Account deletion (App Store requirement)
# ---------------------------------------------------------------------------


@router.delete("/profile/account")
async def delete_account(user_id: str = Depends(get_current_user_id)):
    """Permanently delete the user's account and all associated data."""
    try:
        sb = _get_supabase()

        # Delete user profile
        sb.table("user_profiles").delete().eq("id", user_id).execute()

        # Delete taste profile
        sb.table("user_taste_profiles").delete().eq("id", user_id).execute()

        # Delete interaction logs
        sb.table("interaction_logs").delete().eq("user_id", user_id).execute()

        # Delete saved dishes
        sb.table("saved_dishes").delete().eq("user_id", user_id).execute()

        # Delete chat sessions
        sb.table("chat_sessions").delete().eq("user_id", user_id).execute()

        # Delete friend requests (both directions)
        sb.table("friend_requests").delete().eq("from_user_id", user_id).execute()
        sb.table("friend_requests").delete().eq("to_user_id", user_id).execute()

        # Delete friendships
        sb.table("friendships").delete().eq("user_id", user_id).execute()
        sb.table("friendships").delete().eq("friend_id", user_id).execute()

        # Remove from dining plans
        sb.table("plan_members").delete().eq("user_id", user_id).execute()
        sb.table("plan_messages").delete().eq("sender_id", user_id).execute()

        # Delete plans created by this user
        sb.table("dining_plans").delete().eq("creator_id", user_id).execute()

        # Delete the auth user via admin API
        try:
            sb.auth.admin.delete_user(user_id)
        except Exception:
            pass  # Auth deletion may fail if using service key without admin access

        return {"status": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Account deletion failed: {e}")
