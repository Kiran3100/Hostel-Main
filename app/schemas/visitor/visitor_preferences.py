# --- File: app/schemas/visitor/visitor_preferences.py ---
"""
Visitor preferences schemas for detailed preference management.

This module defines schemas for comprehensive visitor preferences including
room preferences, budget, location, amenities, dietary preferences,
and saved search criteria.
"""

from __future__ import annotations

from datetime import datetime
from datetime import date as Date
from decimal import Decimal
from typing import Annotated, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common.base import BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import (
    DietaryPreference,
    HostelType,
    RoomType,
)

__all__ = [
    "VisitorPreferences",
    "PreferenceUpdate",
    "SearchPreferences",
    "SavedSearch",
]


class VisitorPreferences(BaseSchema):
    """
    Complete visitor preferences schema.
    
    Comprehensive preferences including room type, budget, location,
    amenities, facilities, dietary requirements, move-in details,
    and notification settings.
    """

    # Room Preferences
    preferred_room_type: Optional[RoomType] = Field(
        default=None,
        description="Preferred room type (single, double, dormitory, etc.)",
    )
    preferred_hostel_type: Optional[HostelType] = Field(
        default=None,
        description="Preferred hostel type (boys, girls, co-ed)",
    )

    # Budget Constraints - Updated for Pydantic v2
    budget_min: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        default=None,
        description="Minimum monthly budget in local currency",
    )
    budget_max: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        default=None,
        description="Maximum monthly budget in local currency",
    )

    # Location Preferences
    preferred_cities: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="List of preferred cities",
    )
    preferred_areas: List[str] = Field(
        default_factory=list,
        max_length=30,
        description="Preferred areas/localities within cities",
    )
    max_distance_from_work_km: Optional[Annotated[Decimal, Field(ge=0, le=50)]] = Field(
        default=None,
        description="Maximum acceptable distance from workplace in km",
    )

    # Amenities (must-have vs nice-to-have)
    required_amenities: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Must-have amenities (deal-breakers)",
    )
    preferred_amenities: List[str] = Field(
        default_factory=list,
        max_length=30,
        description="Nice-to-have amenities (preferences)",
    )

    # Facility Requirements
    need_parking: bool = Field(
        default=False,
        description="Requires parking facility",
    )
    need_gym: bool = Field(
        default=False,
        description="Requires gym facility",
    )
    need_laundry: bool = Field(
        default=False,
        description="Requires laundry facility",
    )
    need_mess: bool = Field(
        default=False,
        description="Requires mess/dining facility",
    )

    # Dietary Preferences
    dietary_preference: Optional[DietaryPreference] = Field(
        default=None,
        description="Dietary preference (vegetarian, non-vegetarian, vegan, jain)",
    )

    # Move-in Details
    earliest_move_in_date: Optional[Date] = Field(
        default=None,
        description="Earliest date willing to move in",
    )
    preferred_lease_duration_months: Optional[int] = Field(
        default=None,
        ge=1,
        le=24,
        description="Preferred lease duration in months (1-24)",
    )

    # Notification Preferences
    email_notifications: bool = Field(
        default=True,
        description="Enable email notifications",
    )
    sms_notifications: bool = Field(
        default=True,
        description="Enable SMS notifications",
    )
    push_notifications: bool = Field(
        default=True,
        description="Enable push notifications",
    )

    # Specific Notification Types
    notify_on_price_drop: bool = Field(
        default=True,
        description="Notify when saved hostel reduces price",
    )
    notify_on_availability: bool = Field(
        default=True,
        description="Notify when saved hostel has new availability",
    )
    notify_on_new_listings: bool = Field(
        default=True,
        description="Notify about new hostels matching preferences",
    )

    @field_validator("budget_min", "budget_max")
    @classmethod
    def validate_budget_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure budget values are positive."""
        if v is not None and v < 0:
            raise ValueError("Budget must be a positive value")
        return v

    @model_validator(mode="after")
    def validate_budget_range(self) -> "VisitorPreferences":
        """Validate that budget_max >= budget_min."""
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_max < self.budget_min
        ):
            raise ValueError(
                f"Maximum budget (₹{self.budget_max}) must be greater than or "
                f"equal to minimum budget (₹{self.budget_min})"
            )
        return self

    @field_validator("earliest_move_in_date")
    @classmethod
    def validate_move_in_date(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate move-in date is not in the past."""
        if v is not None and v < Date.today():
            raise ValueError("Move-in date cannot be in the past")
        return v

    @field_validator("preferred_cities", "preferred_areas")
    @classmethod
    def normalize_location_list(cls, v: List[str]) -> List[str]:
        """Normalize and deduplicate location lists."""
        if not v:
            return v

        seen = set()
        normalized = []
        for item in v:
            item_clean = item.strip().title()
            if item_clean and item_clean not in seen:
                seen.add(item_clean)
                normalized.append(item_clean)

        return normalized

    @field_validator("required_amenities", "preferred_amenities")
    @classmethod
    def normalize_amenities_list(cls, v: List[str]) -> List[str]:
        """Normalize and deduplicate amenity lists."""
        if not v:
            return v

        seen = set()
        normalized = []
        for item in v:
            item_clean = item.strip().lower()
            if item_clean and item_clean not in seen:
                seen.add(item_clean)
                normalized.append(item_clean)

        return normalized

    @model_validator(mode="after")
    def validate_notification_settings(self) -> "VisitorPreferences":
        """Ensure at least one notification channel is enabled if specific alerts are on."""
        specific_alerts_enabled = (
            self.notify_on_price_drop
            or self.notify_on_availability
            or self.notify_on_new_listings
        )

        all_channels_disabled = not (
            self.email_notifications
            or self.sms_notifications
            or self.push_notifications
        )

        if specific_alerts_enabled and all_channels_disabled:
            raise ValueError(
                "At least one notification channel (email/SMS/push) must be "
                "enabled to receive alerts"
            )

        return self


class PreferenceUpdate(BaseUpdateSchema):
    """
    Schema for updating visitor preferences.
    
    All fields are optional, allowing partial updates.
    """

    # Room Preferences
    preferred_room_type: Optional[RoomType] = Field(
        default=None,
        description="Update preferred room type",
    )
    preferred_hostel_type: Optional[HostelType] = Field(
        default=None,
        description="Update preferred hostel type",
    )

    # Budget - Updated for Pydantic v2
    budget_min: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        default=None,
        description="Update minimum budget",
    )
    budget_max: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        default=None,
        description="Update maximum budget",
    )

    # Location
    preferred_cities: Optional[List[str]] = Field(
        default=None,
        description="Update preferred cities",
    )
    preferred_areas: Optional[List[str]] = Field(
        default=None,
        description="Update preferred areas",
    )

    # Amenities
    required_amenities: Optional[List[str]] = Field(
        default=None,
        description="Update required amenities",
    )
    preferred_amenities: Optional[List[str]] = Field(
        default=None,
        description="Update preferred amenities",
    )

    # Dietary
    dietary_preference: Optional[DietaryPreference] = Field(
        default=None,
        description="Update dietary preference",
    )

    # Notification Toggles
    email_notifications: Optional[bool] = Field(
        default=None,
        description="Update email notification setting",
    )
    sms_notifications: Optional[bool] = Field(
        default=None,
        description="Update SMS notification setting",
    )
    push_notifications: Optional[bool] = Field(
        default=None,
        description="Update push notification setting",
    )
    notify_on_price_drop: Optional[bool] = Field(
        default=None,
        description="Update price drop alert setting",
    )
    notify_on_availability: Optional[bool] = Field(
        default=None,
        description="Update availability alert setting",
    )
    notify_on_new_listings: Optional[bool] = Field(
        default=None,
        description="Update new listings alert setting",
    )

    @field_validator("budget_min", "budget_max")
    @classmethod
    def validate_budget_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure budget values are positive if provided."""
        if v is not None and v < 0:
            raise ValueError("Budget must be a positive value")
        return v

    @model_validator(mode="after")
    def validate_budget_range(self) -> "PreferenceUpdate":
        """Validate budget range if both values provided."""
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_max < self.budget_min
        ):
            raise ValueError(
                f"Maximum budget (₹{self.budget_max}) must be greater than or "
                f"equal to minimum budget (₹{self.budget_min})"
            )
        return self


class SearchPreferences(BaseSchema):
    """
    Saved search preferences for recurring searches.
    
    Allows visitors to save specific search criteria and receive
    notifications when new matches are found.
    """

    search_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Descriptive name for this saved search",
    )

    # Search Criteria
    cities: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Cities to search in",
    )
    room_types: List[RoomType] = Field(
        default_factory=list,
        max_length=5,
        description="Room types to include",
    )
    min_price: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Minimum price filter",
    )
    max_price: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Maximum price filter",
    )
    amenities: List[str] = Field(
        default_factory=list,
        max_length=15,
        description="Required amenities",
    )

    # Alert Settings
    notify_on_new_matches: bool = Field(
        default=True,
        description="Send notifications when new hostels match this search",
    )
    notification_frequency: str = Field(
        default="daily",
        pattern=r"^(instant|daily|weekly)$",
        description="How often to send notifications: instant, daily, or weekly",
    )

    @field_validator("search_name")
    @classmethod
    def validate_search_name(cls, v: str) -> str:
        """Validate and normalize search name."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Search name must be at least 3 characters")
        if len(v) > 100:
            raise ValueError("Search name must not exceed 100 characters")
        return v

    @model_validator(mode="after")
    def validate_price_range(self) -> "SearchPreferences":
        """Validate price range if both values provided."""
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.max_price < self.min_price
        ):
            raise ValueError(
                f"Maximum price (₹{self.max_price}) must be greater than or "
                f"equal to minimum price (₹{self.min_price})"
            )
        return self

    @model_validator(mode="after")
    def validate_has_criteria(self) -> "SearchPreferences":
        """Ensure at least one search criterion is specified."""
        has_criteria = (
            len(self.cities) > 0
            or len(self.room_types) > 0
            or self.min_price is not None
            or self.max_price is not None
            or len(self.amenities) > 0
        )

        if not has_criteria:
            raise ValueError(
                "At least one search criterion must be specified "
                "(cities, room types, price range, or amenities)"
            )

        return self


class SavedSearch(BaseSchema):
    """
    Saved search with ID and statistics.
    
    Represents a persisted search preference with tracking
    of matches and last check timestamp.
    """

    id: UUID = Field(
        ...,
        description="Unique identifier for this saved search",
    )
    visitor_id: UUID = Field(
        ...,
        description="Visitor who created this search",
    )
    search_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Name of the saved search",
    )
    criteria: Dict = Field(
        ...,
        description="Search criteria stored as JSON object",
    )
    notify_on_new_matches: bool = Field(
        ...,
        description="Whether to send notifications for new matches",
    )
    notification_frequency: str = Field(
        ...,
        pattern=r"^(instant|daily|weekly)$",
        description="Notification frequency",
    )

    # Statistics
    total_matches: int = Field(
        default=0,
        ge=0,
        description="Current number of hostels matching this search",
    )
    new_matches_since_last_check: int = Field(
        default=0,
        ge=0,
        description="Number of new matches since last notification",
    )

    # Timestamps
    created_at: datetime = Field(
        ...,
        description="When this search was saved",
    )
    last_checked: Optional[datetime] = Field(
        default=None,
        description="When this search was last executed",
    )

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, v: Dict) -> Dict:
        """Validate criteria dictionary is not empty."""
        if not v:
            raise ValueError("Search criteria cannot be empty")
        return v