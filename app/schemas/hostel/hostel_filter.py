# --- File: app/schemas/hostel/hostel_filter.py ---
"""
Hostel filter and sort schemas with advanced filtering options.
"""

from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common.base import BaseFilterSchema
from app.schemas.common.enums import HostelStatus, HostelType

__all__ = [
    "HostelFilterParams",
    "HostelSortOptions",
    "AdvancedFilters",
    "BulkFilterParams",
]


class HostelFilterParams(BaseFilterSchema):
    """
    Hostel listing filter parameters.
    
    Provides comprehensive filtering options for hostel queries.
    """
    model_config = ConfigDict(from_attributes=True)

    # Text search
    search: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Search in name, description, city",
    )

    # Location
    city: Optional[str] = Field(
        default=None,
        description="Filter by city",
    )
    state: Optional[str] = Field(
        default=None,
        description="Filter by state",
    )
    cities: Optional[List[str]] = Field(
        default=None,
        description="Filter by multiple cities",
    )

    # Type
    hostel_type: Optional[HostelType] = Field(
        default=None,
        description="Filter by hostel type",
    )
    hostel_types: Optional[List[HostelType]] = Field(
        default=None,
        description="Filter by multiple hostel types",
    )

    # Status
    status: Optional[HostelStatus] = Field(
        default=None,
        description="Filter by operational status",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Filter by active status",
    )
    is_public: Optional[bool] = Field(
        default=None,
        description="Filter by public visibility",
    )
    is_featured: Optional[bool] = Field(
        default=None,
        description="Filter by featured status",
    )
    is_verified: Optional[bool] = Field(
        default=None,
        description="Filter by verification status",
    )

    # Price range
    price_min: Optional[Annotated[
        Decimal,
        Field(ge=0, description="Minimum monthly price")
    ]] = None
    price_max: Optional[Annotated[
        Decimal,
        Field(ge=0, description="Maximum monthly price")
    ]] = None

    # Rating
    min_rating: Optional[Annotated[
        Decimal,
        Field(ge=0, le=5, description="Minimum average rating")
    ]] = None

    # Availability
    has_availability: Optional[bool] = Field(
        default=None,
        description="Filter by bed availability",
    )
    min_available_beds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum available beds required",
    )

    # Amenities
    amenities: Optional[List[str]] = Field(
        default=None,
        description="Required amenities (all must be present)",
    )

    # Admin filters
    admin_id: Optional[UUID] = Field(
        default=None,
        description="Filter by assigned admin (admin only)",
    )
    has_subscription: Optional[bool] = Field(
        default=None,
        description="Filter by subscription status (admin only)",
    )

    @field_validator("price_max")
    @classmethod
    def validate_price_range(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        """Validate price range."""
        if v is not None:
            price_min = info.data.get("price_min")
            if price_min is not None and v < price_min:
                raise ValueError("price_max must be greater than or equal to price_min")
        return v


class HostelSortOptions(BaseFilterSchema):
    """
    Hostel sorting options.
    
    Defines available sort criteria and order.
    """
    model_config = ConfigDict(from_attributes=True)

    sort_by: str = Field(
        default="created_at",
        pattern=r"^(name|city|price|rating|occupancy|created_at|updated_at)$",
        description="Field to sort by",
    )
    sort_order: str = Field(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="Sort order (ascending/descending)",
    )

    @field_validator("sort_order")
    @classmethod
    def normalize_sort_order(cls, v: str) -> str:
        """Normalize sort order to lowercase."""
        return v.lower()


class AdvancedFilters(BaseFilterSchema):
    """
    Advanced filtering options.
    
    Provides additional filtering criteria for complex queries.
    """
    model_config = ConfigDict(from_attributes=True)

    # Date filters
    created_after: Optional[Date] = Field(
        default=None,
        description="Filter hostels created after this Date",
    )
    created_before: Optional[Date] = Field(
        default=None,
        description="Filter hostels created before this Date",
    )

    # Occupancy
    occupancy_min: Optional[Annotated[
        Decimal,
        Field(ge=0, le=100, description="Minimum occupancy percentage")
    ]] = None
    occupancy_max: Optional[Annotated[
        Decimal,
        Field(ge=0, le=100, description="Maximum occupancy percentage")
    ]] = None

    # Reviews
    min_reviews: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum number of reviews",
    )

    # Rooms
    min_rooms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum number of rooms",
    )
    max_rooms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum number of rooms",
    )

    # Revenue (admin only)
    revenue_min: Optional[Annotated[
        Decimal,
        Field(ge=0, description="Minimum monthly revenue (admin only)")
    ]] = None
    revenue_max: Optional[Annotated[
        Decimal,
        Field(ge=0, description="Maximum monthly revenue (admin only)")
    ]] = None

    @field_validator("created_before")
    @classmethod
    def validate_date_range(cls, v: Optional[Date], info) -> Optional[Date]:
        """Validate Date range."""
        if v is not None:
            created_after = info.data.get("created_after")
            if created_after is not None and v < created_after:
                raise ValueError("created_before must be after or equal to created_after")
        return v

    @field_validator("occupancy_max")
    @classmethod
    def validate_occupancy_range(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        """Validate occupancy range."""
        if v is not None:
            occupancy_min = info.data.get("occupancy_min")
            if occupancy_min is not None and v < occupancy_min:
                raise ValueError("occupancy_max must be >= occupancy_min")
        return v


class BulkFilterParams(BaseFilterSchema):
    """
    Bulk operation filter parameters.
    
    Allows filtering hostels for bulk operations.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of hostel IDs (max 100)",
    )

    # Or use filters
    use_filters: bool = Field(
        default=False,
        description="Use filter criteria instead of explicit IDs",
    )
    filters: Optional[HostelFilterParams] = Field(
        default=None,
        description="Filter criteria (if use_filters is True)",
    )

    @field_validator("hostel_ids")
    @classmethod
    def validate_unique_ids(cls, v: List[UUID]) -> List[UUID]:
        """Ensure hostel IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Hostel IDs must be unique")
        return v