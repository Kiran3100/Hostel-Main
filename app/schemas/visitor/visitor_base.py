# --- File: app/schemas/visitor/visitor_base.py ---
"""
Visitor base schemas with comprehensive validation and documentation.

This module defines the core visitor schemas for profile management,
preferences, and notification settings.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import RoomType

__all__ = [
    "VisitorBase",
    "VisitorCreate",
    "VisitorUpdate",
]


class VisitorBase(BaseSchema):
    """
    Base visitor schema with preferences and notification settings.
    
    This schema contains all common fields used across visitor operations
    including room preferences, budget constraints, location preferences,
    and notification settings.
    """

    user_id: UUID = Field(
        ...,
        description="Unique identifier of the associated user account",
    )

    # Room Preferences
    preferred_room_type: Optional[RoomType] = Field(
        default=None,
        description="Preferred room type (single, double, triple, etc.)",
    )

    # Budget Constraints - Updated for Pydantic v2
    budget_min: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        default=None,
        description="Minimum budget per month in local currency",
    )
    budget_max: Optional[Annotated[Decimal, Field(ge=0, decimal_places=2)]] = Field(
        default=None,
        description="Maximum budget per month in local currency",
    )

    # Location Preferences
    preferred_cities: List[str] = Field(
        default_factory=list,
        description="List of preferred cities for hostel search",
        max_length=20,
    )

    # Amenity Preferences
    preferred_amenities: List[str] = Field(
        default_factory=list,
        description="List of must-have amenities (WiFi, AC, Mess, etc.)",
        max_length=30,
    )

    # Saved/Favorite Hostels
    favorite_hostel_ids: List[UUID] = Field(
        default_factory=list,
        description="List of favorite/saved hostel IDs",
        max_length=100,
    )

    # Notification Preferences
    email_notifications: bool = Field(
        default=True,
        description="Enable/disable email notifications",
    )
    sms_notifications: bool = Field(
        default=True,
        description="Enable/disable SMS notifications",
    )
    push_notifications: bool = Field(
        default=True,
        description="Enable/disable push notifications",
    )

    @field_validator("budget_min", "budget_max")
    @classmethod
    def validate_budget_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure budget values are positive if provided."""
        if v is not None and v < 0:
            raise ValueError("Budget must be a positive value")
        return v

    @model_validator(mode="after")
    def validate_budget_range(self) -> "VisitorBase":
        """Validate that budget_max is greater than or equal to budget_min."""
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_max < self.budget_min
        ):
            raise ValueError(
                f"Maximum budget ({self.budget_max}) must be greater than or "
                f"equal to minimum budget ({self.budget_min})"
            )
        return self

    @field_validator("preferred_cities")
    @classmethod
    def validate_cities(cls, v: List[str]) -> List[str]:
        """Validate and normalize city names."""
        if not v:
            return v

        # Remove duplicates while preserving order
        seen = set()
        unique_cities = []
        for city in v:
            city_normalized = city.strip().title()
            if city_normalized and city_normalized not in seen:
                seen.add(city_normalized)
                unique_cities.append(city_normalized)

        if len(unique_cities) > 20:
            raise ValueError("Maximum 20 preferred cities allowed")

        return unique_cities

    @field_validator("preferred_amenities")
    @classmethod
    def validate_amenities(cls, v: List[str]) -> List[str]:
        """Validate and normalize amenity names."""
        if not v:
            return v

        # Remove duplicates and normalize
        seen = set()
        unique_amenities = []
        for amenity in v:
            amenity_normalized = amenity.strip().lower()
            if amenity_normalized and amenity_normalized not in seen:
                seen.add(amenity_normalized)
                unique_amenities.append(amenity_normalized)

        if len(unique_amenities) > 30:
            raise ValueError("Maximum 30 preferred amenities allowed")

        return unique_amenities

    @field_validator("favorite_hostel_ids")
    @classmethod
    def validate_favorites(cls, v: List[UUID]) -> List[UUID]:
        """Validate favorite hostel IDs list."""
        if not v:
            return v

        # Remove duplicates while preserving order
        seen = set()
        unique_favorites = []
        for hostel_id in v:
            if hostel_id not in seen:
                seen.add(hostel_id)
                unique_favorites.append(hostel_id)

        if len(unique_favorites) > 100:
            raise ValueError("Maximum 100 favorite hostels allowed")

        return unique_favorites

    @property
    def has_budget_preference(self) -> bool:
        """Check if visitor has set any budget preference."""
        return self.budget_min is not None or self.budget_max is not None

    @property
    def has_location_preference(self) -> bool:
        """Check if visitor has set location preferences."""
        return len(self.preferred_cities) > 0

    @property
    def notification_enabled_count(self) -> int:
        """Count how many notification channels are enabled."""
        return sum(
            [
                self.email_notifications,
                self.sms_notifications,
                self.push_notifications,
            ]
        )


class VisitorCreate(VisitorBase, BaseCreateSchema):
    """
    Schema for creating a new visitor profile.
    
    Inherits all fields from VisitorBase. All fields are optional
    at creation except user_id, allowing visitors to gradually
    build their preferences.
    """

    # Override to make fields optional at creation
    preferred_cities: List[str] = Field(
        default_factory=list,
        description="List of preferred cities (can be added later)",
    )
    preferred_amenities: List[str] = Field(
        default_factory=list,
        description="List of preferred amenities (can be added later)",
    )
    favorite_hostel_ids: List[UUID] = Field(
        default_factory=list,
        description="Initially empty, populated as user saves hostels",
    )


class VisitorUpdate(BaseUpdateSchema):
    """
    Schema for updating visitor profile.
    
    All fields are optional, allowing partial updates.
    Only provided fields will be updated.
    """

    # Room Preferences
    preferred_room_type: Optional[RoomType] = Field(
        default=None,
        description="Update preferred room type",
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
        description="Update preferred cities list",
    )

    # Amenities
    preferred_amenities: Optional[List[str]] = Field(
        default=None,
        description="Update preferred amenities list",
    )

    # Notification Preferences
    email_notifications: Optional[bool] = Field(
        default=None,
        description="Enable/disable email notifications",
    )
    sms_notifications: Optional[bool] = Field(
        default=None,
        description="Enable/disable SMS notifications",
    )
    push_notifications: Optional[bool] = Field(
        default=None,
        description="Enable/disable push notifications",
    )

    @field_validator("budget_min", "budget_max")
    @classmethod
    def validate_budget_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure budget values are positive if provided."""
        if v is not None and v < 0:
            raise ValueError("Budget must be a positive value")
        return v

    @model_validator(mode="after")
    def validate_budget_range(self) -> "VisitorUpdate":
        """Validate that budget_max is greater than or equal to budget_min if both provided."""
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_max < self.budget_min
        ):
            raise ValueError(
                f"Maximum budget ({self.budget_max}) must be greater than or "
                f"equal to minimum budget ({self.budget_min})"
            )
        return self

    @field_validator("preferred_cities")
    @classmethod
    def validate_cities(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and normalize city names."""
        if v is None:
            return v

        # Remove duplicates while preserving order
        seen = set()
        unique_cities = []
        for city in v:
            city_normalized = city.strip().title()
            if city_normalized and city_normalized not in seen:
                seen.add(city_normalized)
                unique_cities.append(city_normalized)

        if len(unique_cities) > 20:
            raise ValueError("Maximum 20 preferred cities allowed")

        return unique_cities

    @field_validator("preferred_amenities")
    @classmethod
    def validate_amenities(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and normalize amenity names."""
        if v is None:
            return v

        # Remove duplicates and normalize
        seen = set()
        unique_amenities = []
        for amenity in v:
            amenity_normalized = amenity.strip().lower()
            if amenity_normalized and amenity_normalized not in seen:
                seen.add(amenity_normalized)
                unique_amenities.append(amenity_normalized)

        if len(unique_amenities) > 30:
            raise ValueError("Maximum 30 preferred amenities allowed")

        return unique_amenities