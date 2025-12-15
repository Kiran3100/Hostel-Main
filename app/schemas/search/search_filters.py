# --- File: app/schemas/search/search_filters.py ---
"""
Reusable search filter schemas.

Provides modular, composable filter schemas for advanced search functionality.
"""

from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import List, Optional, Annotated

from pydantic import Field, field_validator, model_validator, computed_field, ConfigDict

from app.schemas.common.base import BaseFilterSchema
from app.schemas.common.enums import HostelType, RoomType

__all__ = [
    "PriceFilter",
    "RatingFilter",
    "AmenityFilter",
    "LocationFilter",
    "AvailabilityFilter",
    "SearchFilterSet",
]


class PriceFilter(BaseFilterSchema):
    """
    Price range filter with validation.

    Ensures min_price <= max_price and both are non-negative.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    min_price: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Minimum price in INR",
        examples=[5000, 10000],
    )
    max_price: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Maximum price in INR",
        examples=[20000, 30000],
    )

    @model_validator(mode="after")
    def validate_price_range(self) -> "PriceFilter":
        """Ensure min_price is not greater than max_price."""
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError(
                f"min_price ({self.min_price}) cannot be greater than "
                f"max_price ({self.max_price})"
            )
        return self

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if price filter is active."""
        return self.min_price is not None or self.max_price is not None


class RatingFilter(BaseFilterSchema):
    """
    Rating range filter with validation.

    Ensures ratings are within valid range (0-5).
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    min_rating: Optional[Annotated[Decimal, Field(ge=0, le=5)]] = Field(
        default=None,
        description="Minimum average rating (0-5 scale)",
        examples=[3.5, 4.0, 4.5],
    )
    max_rating: Optional[Annotated[Decimal, Field(ge=0, le=5)]] = Field(
        default=None,
        description="Maximum average rating (0-5 scale)",
        examples=[5.0],
    )

    @model_validator(mode="after")
    def validate_rating_range(self) -> "RatingFilter":
        """Ensure min_rating is not greater than max_rating."""
        if (
            self.min_rating is not None
            and self.max_rating is not None
            and self.min_rating > self.max_rating
        ):
            raise ValueError(
                f"min_rating ({self.min_rating}) cannot be greater than "
                f"max_rating ({self.max_rating})"
            )
        return self

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if rating filter is active."""
        return self.min_rating is not None or self.max_rating is not None


class AmenityFilter(BaseFilterSchema):
    """
    Amenity filter with AND/OR logic support.

    - `required_amenities`: ALL must be present (AND logic)
    - `optional_amenities`: ANY can be present (OR logic)
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    required_amenities: Optional[List[str]] = Field(
        default=None,
        description="All of these amenities must be present (AND logic)",
        examples=[["wifi", "ac", "parking"]],
    )
    optional_amenities: Optional[List[str]] = Field(
        default=None,
        description="Any of these amenities can be present (OR logic)",
        examples=[["gym", "swimming_pool", "laundry"]],
    )
    excluded_amenities: Optional[List[str]] = Field(
        default=None,
        description="None of these amenities should be present",
        examples=[["smoking_allowed"]],
    )

    @field_validator("required_amenities", "optional_amenities", "excluded_amenities")
    @classmethod
    def normalize_amenities(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """
        Normalize amenity list.

        - Convert to lowercase
        - Remove duplicates
        - Strip whitespace
        - Preserve order
        """
        if v is not None:
            seen = set()
            normalized = []
            for amenity in v:
                amenity_clean = amenity.lower().strip()
                if amenity_clean and amenity_clean not in seen:
                    seen.add(amenity_clean)
                    normalized.append(amenity_clean)
            return normalized if normalized else None
        return v

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if amenity filter is active."""
        return (
            self.required_amenities is not None
            or self.optional_amenities is not None
            or self.excluded_amenities is not None
        )


class LocationFilter(BaseFilterSchema):
    """
    Location-based filter with multiple filter types.

    Supports:
    - Text-based location (city, state, pincode)
    - Proximity-based (lat/lon + radius)
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Text-based location
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
        description="6-digit pincode",
        examples=["400001", "560001"],
    )

    # Proximity-based location
    latitude: Optional[Annotated[Decimal, Field(ge=-90, le=90)]] = Field(
        default=None,
        description="Latitude for proximity search",
    )
    longitude: Optional[Annotated[Decimal, Field(ge=-180, le=180)]] = Field(
        default=None,
        description="Longitude for proximity search",
    )
    radius_km: Optional[Annotated[Decimal, Field(ge=0.1, le=100)]] = Field(
        default=None,
        description="Search radius in kilometers",
        examples=[5, 10, 25],
    )

    @field_validator("city", "state")
    @classmethod
    def normalize_location(cls, v: Optional[str]) -> Optional[str]:
        """Normalize location strings to title case."""
        if v is not None:
            return v.strip().title()
        return v

    @model_validator(mode="after")
    def validate_proximity_requirements(self) -> "LocationFilter":
        """Ensure radius requires both latitude and longitude."""
        if self.radius_km is not None:
            if self.latitude is None or self.longitude is None:
                raise ValueError(
                    "Both latitude and longitude are required when using radius_km"
                )
        return self

    @computed_field
    @property
    def is_text_location(self) -> bool:
        """Check if text-based location filter is active."""
        return any([self.city, self.state, self.pincode])

    @computed_field
    @property
    def is_proximity_location(self) -> bool:
        """Check if proximity-based location filter is active."""
        return self.latitude is not None and self.longitude is not None

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if any location filter is active."""
        return self.is_text_location or self.is_proximity_location


class AvailabilityFilter(BaseFilterSchema):
    """
    Availability and booking filters.

    Filters based on bed availability and booking requirements.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    available_only: bool = Field(
        default=False,
        description="Show only hostels with available beds",
    )
    min_available_beds: Optional[int] = Field(
        default=None,
        ge=1,
        description="Minimum number of available beds required",
        examples=[1, 2, 5],
    )

    # Date-based availability
    check_in_date: Optional[Date] = Field(
        default=None,
        description="Desired check-in Date",
    )
    check_out_date: Optional[Date] = Field(
        default=None,
        description="Desired check-out Date",
    )

    # Booking preferences
    instant_booking_only: bool = Field(
        default=False,
        description="Show only hostels with instant booking enabled",
    )
    verified_only: bool = Field(
        default=False,
        description="Show only verified hostels",
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "AvailabilityFilter":
        """Validate check-in and check-out Date logic."""
        if self.check_in_date and self.check_out_date:
            if self.check_in_date >= self.check_out_date:
                raise ValueError(
                    "check_in_date must be before check_out_date"
                )

            # Validate dates are not in the past
            today = Date.today()
            if self.check_in_date < today:
                raise ValueError("check_in_date cannot be in the past")

        return self

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if any availability filter is active."""
        return (
            self.available_only
            or self.min_available_beds is not None
            or self.check_in_date is not None
            or self.instant_booking_only
            or self.verified_only
        )


class SearchFilterSet(BaseFilterSchema):
    """
    Composite filter set combining all filter types.

    Provides a convenient way to apply multiple filters together.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Core filters
    price: Optional[PriceFilter] = Field(
        default=None,
        description="Price range filter",
    )
    rating: Optional[RatingFilter] = Field(
        default=None,
        description="Rating range filter",
    )
    amenities: Optional[AmenityFilter] = Field(
        default=None,
        description="Amenity filters",
    )
    location: Optional[LocationFilter] = Field(
        default=None,
        description="Location filters",
    )
    availability: Optional[AvailabilityFilter] = Field(
        default=None,
        description="Availability filters",
    )

    # Type filters
    hostel_types: Optional[List[HostelType]] = Field(
        default=None,
        description="Filter by hostel types",
        examples=[["boys", "girls"]],
    )
    room_types: Optional[List[RoomType]] = Field(
        default=None,
        description="Filter by room types",
        examples=[["single", "double"]],
    )

    @computed_field
    @property
    def active_filters(self) -> List[str]:
        """Get list of active filter names."""
        active = []
        if self.price and self.price.is_active:
            active.append("price")
        if self.rating and self.rating.is_active:
            active.append("rating")
        if self.amenities and self.amenities.is_active:
            active.append("amenities")
        if self.location and self.location.is_active:
            active.append("location")
        if self.availability and self.availability.is_active:
            active.append("availability")
        if self.hostel_types:
            active.append("hostel_types")
        if self.room_types:
            active.append("room_types")
        return active

    @computed_field
    @property
    def filter_count(self) -> int:
        """Get count of active filters."""
        return len(self.active_filters)

    @computed_field
    @property
    def has_filters(self) -> bool:
        """Check if any filter is active."""
        return self.filter_count > 0