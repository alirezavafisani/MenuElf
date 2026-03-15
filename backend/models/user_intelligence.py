from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class InteractionType(str, Enum):
    CHAT_MESSAGE = "chat_message"
    DISH_VIEW = "dish_view"
    DISH_SAVE = "dish_save"
    DISH_UNSAVE = "dish_unsave"
    RESTAURANT_TAP = "restaurant_tap"
    RESTAURANT_CHAT_OPEN = "restaurant_chat_open"
    SEARCH_QUERY = "search_query"
    FILTER_APPLY = "filter_apply"
    ONBOARDING_CHOICE = "onboarding_choice"


# ── Taste Profile ──

class UserTasteProfile(BaseModel):
    id: UUID
    spice_tolerance: float = 0.5
    sweetness_preference: float = 0.5
    adventurousness: float = 0.5
    price_comfort: float = 0.5
    protein_preference: Dict[str, float] = Field(default_factory=lambda: {
        "beef": 0.5, "chicken": 0.5, "pork": 0.5,
        "fish": 0.5, "vegetarian": 0.5, "vegan": 0.3,
    })
    cuisine_preferences: Dict[str, float] = Field(default_factory=lambda: {
        "italian": 0.5, "mexican": 0.5, "japanese": 0.5, "chinese": 0.5,
        "indian": 0.5, "thai": 0.5, "korean": 0.5, "mediterranean": 0.5,
        "american": 0.5, "french": 0.5, "vietnamese": 0.5, "middle_eastern": 0.5,
    })
    dietary_restrictions: List[str] = Field(default_factory=list)
    texture_preferences: Dict[str, float] = Field(default_factory=lambda: {
        "crispy": 0.5, "creamy": 0.5, "crunchy": 0.5, "soupy": 0.5, "chewy": 0.5,
    })
    meal_size_preference: float = 0.5
    onboarding_completed: bool = False
    profile_version: int = 1
    last_updated: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ── Interaction Log ──

class InteractionLog(BaseModel):
    id: Optional[UUID] = None
    user_id: UUID
    interaction_type: InteractionType
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class InteractionLogCreate(BaseModel):
    interaction_type: InteractionType
    payload: Dict[str, Any] = Field(default_factory=dict)


# ── Saved Dish ──

class SavedDish(BaseModel):
    id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    dish_name: str
    restaurant_slug: str
    restaurant_name: str
    price: Optional[float] = None
    category: Optional[str] = None
    dietary_info: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    saved_at: Optional[datetime] = None


class SavedDishCreate(BaseModel):
    dish_name: str
    restaurant_slug: str
    restaurant_name: str
    price: Optional[float] = None
    category: Optional[str] = None
    dietary_info: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


# ── Chat Session ──

class ChatSessionMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None


class ChatSession(BaseModel):
    id: Optional[UUID] = None
    user_id: UUID
    restaurant_slug: str
    messages: List[ChatSessionMessage] = Field(default_factory=list)
    preference_signals_extracted: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Onboarding ──

class OnboardingQuestion(BaseModel):
    id: Optional[int] = None
    question_index: int
    option_a_image_url: str
    option_a_label: str
    option_a_signals: Dict[str, float]
    option_b_image_url: str
    option_b_label: str
    option_b_signals: Dict[str, float]
    is_active: bool = True
    created_at: Optional[datetime] = None


class OnboardingAnswer(BaseModel):
    question_index: int
    chosen_option: str  # "a" or "b"
    question_id: Optional[int] = None


class OnboardingRequest(BaseModel):
    answers: List[OnboardingAnswer] = Field(..., min_length=5, max_length=5)
