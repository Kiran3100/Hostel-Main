# --- File: app/schemas/hostel/hostel_filter.py ---
"""
Hostel filter and sort schemas with advanced filtering options.
"""

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, List, Union
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
    search: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Search in name, description, city",
    )

    # Location
    city: Union[str, None] = Field(
        default=None,
        description="Filter by city",
    )
    state: Union[str, None] = Field(
        default=None,
        description="Filter by state",
    )
    cities: Union[List[str], None] = Field(
        default=None,
        description="Filter by multiple cities",
    )

    # Type
    hostel_type: Union[HostelType, None] = Field(
        default=None,
        description="Filter by hostel type",
    )
    hostel_types: Union[List[HostelType], None] = Field(
        default=None,
        description="Filter by multiple hostel types",
    )

    # Status
    status: Union[HostelStatus, None] = Field(
        default=None,
        description="Filter by operational status",
    )
    is_active: Union[bool, None] = Field(
        default=None,
        description="Filter by active status",
    )
    is_public: Union[bool, None] = Field(
        default=None,
        description="Filter by public visibility",
    )
    is_featured: Union[bool, None] = Field(
        default=None,
        description="Filter by featured status",
    )
    is_verified: Union[bool, None] = Field(
        default=None,
        description="Filter by verification status",
    )

    # Price range
    price_min: Union[Annotated[
        Decimal,
        Field(ge=0, description="Minimum monthly price")
    ], None] = None
    price_max: Union[Annotated[
        Decimal,
        Field(ge=0, description="Maximum monthly price")
    ], None] = None

    # Rating
    min_rating: Union[Annotated[
        Decimal,
        Field(ge=0, le=5, description="Minimum average rating")
    ], None] = None

    # Availability
    has_availability: Union[bool, None] = Field(
        default=None,
        description="Filter by bed availability",
    )
    min_available_beds: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Minimum available beds required",
    )

    # Amenities
    amenities: Union[List[str], None] = Field(
        default=None,
        description="Required amenities (all must be present)",
    )

    # Admin filters
    admin_id: Union[UUID, None] = Field(
        default=None,
        description="Filter by assigned admin (admin only)",
    )
    has_subscription: Union[bool, None] = Field(
        default=None,
        description="Filter by subscription status (admin only)",
    )

    @field_validator("price_max")
    @classmethod
    def validate_price_range(cls, v: Union[Decimal, None], info) -> Union[Decimal, None]:
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
    created_after: Union[Date, None] = Field(
        default=None,
        description="Filter hostels created after this Date",
    )
    created_before: Union[Date, None] = Field(
        default=None,
        description="Filter hostels created before this Date",
    )

    # Occupancy
    occupancy_min: Union[Annotated[
        Decimal,
        Field(ge=0, le=100, description="Minimum occupancy percentage")
    ], None] = None
    occupancy_max: Union[Annotated[
        Decimal,
        Field(ge=0, le=100, description="Maximum occupancy percentage")
    ], None] = None

    # Reviews
    min_reviews: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Minimum number of reviews",
    )

    # Rooms
    min_rooms: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Minimum number of rooms",
    )
    max_rooms: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Maximum number of rooms",
    )

    # Revenue (admin only)
    revenue_min: Union[Annotated[
        Decimal,
        Field(ge=0, description="Minimum monthly revenue (admin only)")
    ], None] = None
    revenue_max: Union[Annotated[
        Decimal,
        Field(ge=0, description="Maximum monthly revenue (admin only)")
    ], None] = None

    @field_validator("created_before")
    @classmethod
    def validate_date_range(cls, v: Union[Date, None], info) -> Union[Date, None]:
        """Validate Date range."""
        if v is not None:
            created_after = info.data.get("created_after")
            if created_after is not None and v < created_after:
                raise ValueError("created_before must be after or equal to created_after")
        return v

    @field_validator("occupancy_max")
    @classmethod
    def validate_occupancy_range(cls, v: Union[Decimal, None], info) -> Union[Decimal, None]:
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
    filters: Union[HostelFilterParams, None] = Field(
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