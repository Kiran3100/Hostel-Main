# --- File: app/schemas/visitor/visitor_preferences.py ---
"""
Visitor preferences schemas for detailed preference management.

This module defines schemas for comprehensive visitor preferences including
room preferences, budget, location, amenities, dietary preferences,
and saved search criteria.
"""

from datetime import datetime, date as Date, time as Time
from decimal import Decimal
from typing import Annotated, Dict, List, Union
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
    "PreferencesUpdate",  # Alternative naming
    "NotificationPreferences",
    "PrivacyPreferences",
    "DisplayPreferences",
    "SearchPreferences",
    "SavedSearch",
]


class NotificationPreferences(BaseSchema):
    """
    Notification preferences for various channels and types.
    """

    # Channel preferences
    email_enabled: bool = Field(
        default=True,
        description="Enable email notifications",
    )
    push_enabled: bool = Field(
        default=True,
        description="Enable push notifications",
    )
    sms_enabled: bool = Field(
        default=False,
        description="Enable SMS notifications",
    )

    # Notification types
    booking_updates: bool = Field(
        default=True,
        description="Receive booking status updates",
    )
    price_alerts: bool = Field(
        default=True,
        description="Receive price drop alerts for saved hostels",
    )
    availability_alerts: bool = Field(
        default=True,
        description="Receive availability alerts for saved hostels",
    )
    new_listings: bool = Field(
        default=True,
        description="Receive notifications for new hostel listings",
    )
    promotional: bool = Field(
        default=False,
        description="Receive promotional offers and deals",
    )
    weekly_digest: bool = Field(
        default=True,
        description="Receive weekly summary digest",
    )

    # Frequency and timing
    notification_frequency: str = Field(
        default="instant",
        pattern="^(instant|hourly|daily|weekly)$",
        description="Notification frequency for non-urgent notifications",
    )
    quiet_hours_enabled: bool = Field(
        default=False,
        description="Enable quiet hours (no notifications)",
    )
    quiet_hours_start: Union[Time, None] = Field(
        default=None,
        description="Start time for quiet hours (e.g., 22:00)",
    )
    quiet_hours_end: Union[Time, None] = Field(
        default=None,
        description="End time for quiet hours (e.g., 08:00)",
    )

    @model_validator(mode="after")
    def validate_quiet_hours(self) -> "NotificationPreferences":
        """Validate quiet hours configuration."""
        if self.quiet_hours_enabled:
            if not self.quiet_hours_start or not self.quiet_hours_end:
                raise ValueError(
                    "Quiet hours start and end times are required when quiet hours are enabled"
                )
        return self


class PrivacyPreferences(BaseSchema):
    """
    Privacy and data sharing preferences.
    """

    # Profile visibility
    profile_visibility: str = Field(
        default="public",
        pattern="^(public|private|friends_only)$",
        description="Profile visibility setting",
    )
    show_real_name: bool = Field(
        default=True,
        description="Show real name in public profile",
    )
    show_location: bool = Field(
        default=True,
        description="Show location in public profile",
    )

    # Data sharing
    analytics_opt_in: bool = Field(
        default=True,
        description="Allow anonymous analytics data collection",
    )
    marketing_opt_in: bool = Field(
        default=False,
        description="Opt-in to marketing communications",
    )
    third_party_sharing: bool = Field(
        default=False,
        description="Allow data sharing with trusted partners",
    )

    # Activity privacy
    show_activity: bool = Field(
        default=True,
        description="Show activity status to other users",
    )
    show_reviews: bool = Field(
        default=True,
        description="Make reviews publicly visible",
    )
    show_favorites: bool = Field(
        default=False,
        description="Make favorite hostels publicly visible",
    )

    # Communication preferences
    allow_messages: bool = Field(
        default=True,
        description="Allow messages from other users",
    )
    allow_connection_requests: bool = Field(
        default=True,
        description="Allow connection requests from other users",
    )


class DisplayPreferences(BaseSchema):
    """
    UI and display preferences for the application.
    """

    # Theme and appearance
    theme: str = Field(
        default="auto",
        pattern="^(light|dark|auto)$",
        description="Color theme preference",
    )
    language: str = Field(
        default="en",
        min_length=2,
        max_length=5,
        description="Language code (e.g., 'en', 'es', 'fr')",
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="Preferred currency code",
    )

    # List and grid preferences
    default_view_mode: str = Field(
        default="list",
        pattern="^(list|grid|map)$",
        description="Default view mode for hostel listings",
    )
    items_per_page: int = Field(
        default=20,
        ge=10,
        le=100,
        description="Number of items to show per page",
    )

    # Map preferences
    map_default_zoom: int = Field(
        default=12,
        ge=1,
        le=20,
        description="Default zoom level for map views",
    )
    map_style: str = Field(
        default="standard",
        pattern="^(standard|satellite|terrain)$",
        description="Default map style",
    )

    # Accessibility
    high_contrast: bool = Field(
        default=False,
        description="Enable high contrast mode",
    )
    large_text: bool = Field(
        default=False,
        description="Enable larger text size",
    )
    reduced_motion: bool = Field(
        default=False,
        description="Reduce animations and motion",
    )

    # Data and performance
    auto_load_images: bool = Field(
        default=True,
        description="Automatically load images",
    )
    cache_enabled: bool = Field(
        default=True,
        description="Enable local caching for better performance",
    )

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate language code."""
        v = v.lower().strip()
        if not v.replace('-', '').isalpha():
            raise ValueError("Invalid language code format")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency code."""
        v = v.upper().strip()
        if len(v) != 3 or not v.isalpha():
            raise ValueError("Currency code must be exactly 3 alphabetic characters")
        return v


class VisitorPreferences(BaseSchema):
    """
    Complete visitor preferences schema.
    
    Comprehensive preferences including room type, budget, location,
    amenities, facilities, dietary requirements, move-in details,
    and notification settings.
    """

    # Room Preferences
    preferred_room_type: Union[RoomType, None] = Field(
        default=None,
        description="Preferred room type (single, double, dormitory, etc.)",
    )
    preferred_hostel_type: Union[HostelType, None] = Field(
        default=None,
        description="Preferred hostel type (boys, girls, co-ed)",
    )

    # Budget Constraints - Updated for Pydantic v2
    budget_min: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        default=None,
        description="Minimum monthly budget in local currency",
    )
    budget_max: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
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
    max_distance_from_work_km: Union[Annotated[Decimal, Field(ge=0, le=50)], None] = Field(
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
    dietary_preference: Union[DietaryPreference, None] = Field(
        default=None,
        description="Dietary preference (vegetarian, non-vegetarian, vegan, jain)",
    )

    # Move-in Details
    earliest_move_in_date: Union[Date, None] = Field(
        default=None,
        description="Earliest Date willing to move in",
    )
    preferred_lease_duration_months: Union[int, None] = Field(
        default=None,
        ge=1,
        le=24,
        description="Preferred lease duration in months (1-24)",
    )

    # Embedded preferences
    notifications: NotificationPreferences = Field(
        default_factory=NotificationPreferences,
        description="Notification preferences",
    )
    privacy: PrivacyPreferences = Field(
        default_factory=PrivacyPreferences,
        description="Privacy preferences",
    )
    display: DisplayPreferences = Field(
        default_factory=DisplayPreferences,
        description="Display preferences",
    )

    @field_validator("budget_min", "budget_max")
    @classmethod
    def validate_budget_positive(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
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
    def validate_move_in_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate move-in Date is not in the past."""
        if v is not None and v < Date.today():
            raise ValueError("Move-in Date cannot be in the past")
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


class PreferenceUpdate(BaseUpdateSchema):
    """
    Schema for updating visitor preferences.
    
    All fields are optional, allowing partial updates.
    """

    # Room Preferences
    preferred_room_type: Union[RoomType, None] = Field(
        default=None,
        description="Update preferred room type",
    )
    preferred_hostel_type: Union[HostelType, None] = Field(
        default=None,
        description="Update preferred hostel type",
    )

    # Budget - Updated for Pydantic v2
    budget_min: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        default=None,
        description="Update minimum budget",
    )
    budget_max: Union[Annotated[Decimal, Field(ge=0, decimal_places=2)], None] = Field(
        default=None,
        description="Update maximum budget",
    )

    # Location
    preferred_cities: Union[List[str], None] = Field(
        default=None,
        description="Update preferred cities",
    )
    preferred_areas: Union[List[str], None] = Field(
        default=None,
        description="Update preferred areas",
    )

    # Amenities
    required_amenities: Union[List[str], None] = Field(
        default=None,
        description="Update required amenities",
    )
    preferred_amenities: Union[List[str], None] = Field(
        default=None,
        description="Update preferred amenities",
    )

    # Dietary
    dietary_preference: Union[DietaryPreference, None] = Field(
        default=None,
        description="Update dietary preference",
    )

    # Embedded preferences (partial updates)
    notifications: Union[NotificationPreferences, None] = Field(
        default=None,
        description="Update notification preferences",
    )
    privacy: Union[PrivacyPreferences, None] = Field(
        default=None,
        description="Update privacy preferences",
    )
    display: Union[DisplayPreferences, None] = Field(
        default=None,
        description="Update display preferences",
    )

    @field_validator("budget_min", "budget_max")
    @classmethod
    def validate_budget_positive(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
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


# Alias for alternative naming convention used in API
PreferencesUpdate = PreferenceUpdate


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
    min_price: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        default=None,
        description="Minimum price filter",
    )
    max_price: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
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
    last_checked: Union[datetime, None] = Field(
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