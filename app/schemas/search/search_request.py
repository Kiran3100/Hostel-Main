# --- File: app/schemas/search/search_request.py ---
"""
Search request schemas with comprehensive validation and type safety.

Provides schemas for:
- Basic keyword search
- Advanced search with multiple filters
- Nearby/proximity search
- Saved searches
- Search history
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field, ConfigDict

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseFilterSchema,
    BaseResponseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import Gender, HostelType, RoomType

__all__ = [
    "BasicSearchRequest",
    "AdvancedSearchRequest",
    "NearbySearchRequest",
    "SavedSearchCreate",
    "SavedSearchUpdate",
    "SavedSearchResponse",
    "SearchHistoryResponse",
]


class BasicSearchRequest(BaseFilterSchema):
    """
    Simple keyword-based search request.

    Optimized for quick searches with minimal parameters.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    query: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Search query string",
        examples=["hostels in Mumbai", "PG near me"],
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )

    @field_validator("query")
    @classmethod
    def validate_and_normalize_query(cls, v: str) -> str:
        """
        Normalize search query.

        - Strips whitespace
        - Removes excessive spaces
        - Validates non-empty after normalization
        """
        # Strip and normalize whitespace
        normalized = " ".join(v.split())

        if not normalized:
            raise ValueError("Search query cannot be empty or only whitespace")

        return normalized


class AdvancedSearchRequest(BaseFilterSchema):
    """
    Advanced search request with comprehensive filtering options.

    Supports:
    - Text search
    - Geographic filtering
    - Price range
    - Amenity filtering
    - Rating filters
    - Availability filters
    - Sorting and pagination
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Search query
    query: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional search keywords",
        examples=["boys hostel", "PG with meals"],
    )

    # Location filters
    city: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="City name",
        examples=["Mumbai", "Bangalore"],
    )
    state: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="State name",
        examples=["Maharashtra", "Karnataka"],
    )
    pincode: Optional[str] = Field(
        default=None,
        pattern=r"^\d{6}$",
        description="6-digit Indian pincode",
        examples=["400001", "560001"],
    )

    # Geographic coordinates for proximity search
    latitude: Optional[Annotated[Decimal, Field(ge=-90, le=90)]] = Field(
        default=None,
        description="Latitude for proximity search",
        examples=[19.0760],
    )
    longitude: Optional[Annotated[Decimal, Field(ge=-180, le=180)]] = Field(
        default=None,
        description="Longitude for proximity search",
        examples=[72.8777],
    )
    radius_km: Optional[Annotated[Decimal, Field(ge=0.1, le=100)]] = Field(
        default=None,
        description="Search radius in kilometers",
        examples=[5, 10, 25],
    )

    # Hostel and room type filters
    hostel_type: Optional[HostelType] = Field(
        default=None,
        description="Filter by hostel type (boys/girls/co-ed)",
    )
    room_types: Optional[List[RoomType]] = Field(
        default=None,
        description="Filter by room types (can select multiple)",
        examples=[["single", "double"]],
    )

    # Gender preference (for co-ed hostels)
    gender_preference: Optional[Gender] = Field(
        default=None,
        description="Gender preference for room allocation",
    )

    # Price range filter
    min_price: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Minimum monthly price in INR",
        examples=[5000, 10000],
    )
    max_price: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Maximum monthly price in INR",
        examples=[20000, 30000],
    )

    # Amenities filter
    amenities: Optional[List[str]] = Field(
        default=None,
        description="Required amenities (AND logic - hostel must have all)",
        examples=[["wifi", "ac", "parking"]],
    )
    any_amenities: Optional[List[str]] = Field(
        default=None,
        description="Optional amenities (OR logic - hostel can have any)",
        examples=[["gym", "laundry", "swimming_pool"]],
    )

    # Rating filter
    min_rating: Optional[Annotated[Decimal, Field(ge=0, le=5)]] = Field(
        default=None,
        description="Minimum average rating (0-5)",
        examples=[3.5, 4.0],
    )

    # Availability filters
    verified_only: bool = Field(
        default=False,
        description="Show only verified hostels",
    )
    available_only: bool = Field(
        default=False,
        description="Show only hostels with available beds",
    )
    instant_booking: bool = Field(
        default=False,
        description="Show only hostels with instant booking enabled",
    )

    # Date-based availability
    check_in_date: Optional[Date] = Field(
        default=None,
        description="Desired check-in Date for availability check",
    )
    check_out_date: Optional[Date] = Field(
        default=None,
        description="Desired check-out Date for availability check",
    )

    # Sorting options
    sort_by: str = Field(
        default="relevance",
        pattern=r"^(relevance|price_asc|price_desc|rating_desc|distance_asc|newest|popular)$",
        description="Sort criterion",
    )

    # Pagination
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Results per page",
    )

    # Advanced options
    include_nearby_cities: bool = Field(
        default=False,
        description="Include results from nearby cities",
    )
    boost_featured: bool = Field(
        default=True,
        description="Boost featured/promoted hostels in results",
    )

    @field_validator("query")
    @classmethod
    def normalize_query(cls, v: Optional[str]) -> Optional[str]:
        """Normalize search query."""
        if v is not None:
            normalized = " ".join(v.split())
            return normalized if normalized else None
        return v

    @field_validator("city", "state")
    @classmethod
    def normalize_location(cls, v: Optional[str]) -> Optional[str]:
        """Normalize location strings."""
        if v is not None:
            return v.strip().title()
        return v

    @field_validator("amenities", "any_amenities")
    @classmethod
    def normalize_amenities(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Normalize amenity list (lowercase, deduplicate)."""
        if v is not None:
            # Convert to lowercase and remove duplicates while preserving order
            seen = set()
            normalized = []
            for amenity in v:
                amenity_lower = amenity.lower().strip()
                if amenity_lower and amenity_lower not in seen:
                    seen.add(amenity_lower)
                    normalized.append(amenity_lower)
            return normalized if normalized else None
        return v

    @model_validator(mode="after")
    def validate_location_consistency(self) -> "AdvancedSearchRequest":
        """
        Validate location-related fields consistency.

        - Ensure radius is provided only with coordinates
        - Validate price range
        - Validate Date range
        """
        # Validate radius requires coordinates
        if self.radius_km is not None:
            if self.latitude is None or self.longitude is None:
                raise ValueError(
                    "Both latitude and longitude are required when using radius_km"
                )

        # Validate price range
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot be greater than max_price")

        # Validate Date range
        if self.check_in_date and self.check_out_date:
            if self.check_in_date >= self.check_out_date:
                raise ValueError("check_in_date must be before check_out_date")

            # Validate dates are not in the past
            today = Date.today()
            if self.check_in_date < today:
                raise ValueError("check_in_date cannot be in the past")

        return self

    @computed_field
    @property
    def has_location_filter(self) -> bool:
        """Check if any location filter is applied."""
        return any(
            [
                self.city,
                self.state,
                self.pincode,
                self.latitude and self.longitude,
            ]
        )

    @computed_field
    @property
    def has_price_filter(self) -> bool:
        """Check if price filter is applied."""
        return self.min_price is not None or self.max_price is not None

    @computed_field
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size


class NearbySearchRequest(BaseFilterSchema):
    """
    Proximity-based search request.

    Optimized for "near me" searches and location-based discovery.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    latitude: Annotated[Decimal, Field(ge=-90, le=90)] = Field(
        ...,
        description="Current latitude",
    )
    longitude: Annotated[Decimal, Field(ge=-180, le=180)] = Field(
        ...,
        description="Current longitude",
    )
    radius_km: Annotated[Decimal, Field(ge=0.1, le=50)] = Field(
        default=5.0,
        description="Search radius in kilometers",
    )

    # Optional filters
    hostel_type: Optional[HostelType] = Field(
        default=None,
        description="Filter by hostel type",
    )
    min_price: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Minimum price filter",
    )
    max_price: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Maximum price filter",
    )
    available_only: bool = Field(
        default=True,
        description="Show only hostels with available beds",
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results",
    )

    @model_validator(mode="after")
    def validate_price_range(self) -> "NearbySearchRequest":
        """Validate price range."""
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot be greater than max_price")
        return self


class SavedSearchCreate(BaseCreateSchema):
    """
    Create saved search for user.

    Allows users to save frequently used search criteria.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User-friendly name for the saved search",
        examples=["My Daily Commute Search", "Budget Hostels in Mumbai"],
    )
    search_criteria: Dict[str, Any] = Field(
        ...,
        description="Serialized search parameters (AdvancedSearchRequest as dict)",
    )
    is_alert_enabled: bool = Field(
        default=False,
        description="Enable notifications when new matching hostels are added",
    )
    alert_frequency: Optional[str] = Field(
        default=None,
        pattern=r"^(daily|weekly|instant)$",
        description="Alert notification frequency",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Normalize search name."""
        normalized = " ".join(v.split())
        if not normalized:
            raise ValueError("Search name cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_alert_settings(self) -> "SavedSearchCreate":
        """Validate alert configuration."""
        if self.is_alert_enabled and not self.alert_frequency:
            raise ValueError(
                "alert_frequency is required when is_alert_enabled is True"
            )
        if not self.is_alert_enabled and self.alert_frequency:
            self.alert_frequency = None  # Clear frequency if alerts disabled
        return self


class SavedSearchUpdate(BaseUpdateSchema):
    """Update saved search configuration."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated name",
    )
    search_criteria: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Updated search parameters",
    )
    is_alert_enabled: Optional[bool] = Field(
        default=None,
        description="Enable/disable alerts",
    )
    alert_frequency: Optional[str] = Field(
        default=None,
        pattern=r"^(daily|weekly|instant)$",
        description="Alert frequency",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: Optional[str]) -> Optional[str]:
        """Normalize search name."""
        if v is not None:
            normalized = " ".join(v.split())
            return normalized if normalized else None
        return v


class SavedSearchResponse(BaseResponseSchema):
    """Saved search response schema."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    user_id: UUID = Field(..., description="User ID who owns this search")
    name: str = Field(..., description="Search name")
    search_criteria: Dict[str, Any] = Field(..., description="Search parameters")
    is_alert_enabled: bool = Field(..., description="Alert status")
    alert_frequency: Optional[str] = Field(default=None, description="Alert frequency")
    last_executed_at: Optional[datetime] = Field(
        default=None,
        description="Last time this search was executed",
    )
    result_count: int = Field(
        default=0,
        ge=0,
        description="Number of results from last execution",
    )


class SearchHistoryResponse(BaseResponseSchema):
    """Search history entry response."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    user_id: Optional[UUID] = Field(
        default=None,
        description="User ID (null for anonymous searches)",
    )
    query: str = Field(..., description="Search query")
    search_criteria: Dict[str, Any] = Field(
        ...,
        description="Complete search parameters",
    )
    result_count: int = Field(
        ...,
        ge=0,
        description="Number of results returned",
    )
    execution_time_ms: int = Field(
        ...,
        ge=0,
        description="Query execution time in milliseconds",
    )
    clicked_result_ids: List[UUID] = Field(
        default_factory=list,
        description="IDs of hostels clicked from this search",
    )