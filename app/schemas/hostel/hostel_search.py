# --- File: app/schemas/hostel/hostel_search.py ---
"""
Hostel search schemas with comprehensive search and filtering.
"""

from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common.base import BaseFilterSchema, BaseSchema
from app.schemas.common.enums import HostelType, RoomType
from app.schemas.hostel.hostel_public import PublicHostelCard

__all__ = [
    "HostelSearchRequest",
    "HostelSearchResponse",
    "SearchFacets",
    "FacetItem",
    "PriceRangeFacet",
    "RatingFacet",
    "HostelSearchFilters",
]


class HostelSearchRequest(BaseFilterSchema):
    """
    Hostel search request with comprehensive filtering.
    
    Supports text search, location-based search, and various filters.
    """
    model_config = ConfigDict(from_attributes=True)

    # Text search
    query: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Search query (name, description, city)",
    )

    # Location filters
    city: Optional[str] = Field(
        default=None,
        description="Filter by city name",
    )
    state: Optional[str] = Field(
        default=None,
        description="Filter by state name",
    )
    pincode: Optional[str] = Field(
        default=None,
        pattern=r"^\d{6}$",
        description="Filter by 6-digit pincode",
    )

    # Location-based search (radius)
    latitude: Optional[Annotated[
        Decimal,
        Field(ge=-90, le=90, description="Latitude for radius search")
    ]] = None
    longitude: Optional[Annotated[
        Decimal,
        Field(ge=-180, le=180, description="Longitude for radius search")
    ]] = None
    radius_km: Optional[Annotated[
        Decimal,
        Field(ge=0, le=50, description="Search radius in kilometers")
    ]] = None

    # Type filter
    hostel_type: Optional[HostelType] = Field(
        default=None,
        description="Filter by hostel type",
    )

    # Price filter
    min_price: Optional[Annotated[
        Decimal,
        Field(ge=0, description="Minimum monthly price")
    ]] = None
    max_price: Optional[Annotated[
        Decimal,
        Field(ge=0, description="Maximum monthly price")
    ]] = None

    # Room type
    room_type: Optional[RoomType] = Field(
        default=None,
        description="Preferred room type",
    )

    # Amenities filter
    amenities: Optional[List[str]] = Field(
        default=None,
        max_length=10,
        description="Required amenities (all must be present)",
    )

    # Availability
    available_beds_min: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum available beds required",
    )

    # Rating filter
    min_rating: Optional[Annotated[
        Decimal,
        Field(ge=0, le=5, description="Minimum average rating")
    ]] = None

    # Features
    verified_only: bool = Field(
        default=False,
        description="Show only verified hostels",
    )
    featured_only: bool = Field(
        default=False,
        description="Show only featured hostels",
    )

    # Sort
    sort_by: str = Field(
        default="relevance",
        pattern=r"^(relevance|price_low|price_high|rating|distance|newest)$",
        description="Sort criteria",
    )

    # Pagination
    page: int = Field(
        default=1,
        ge=1,
        description="Page number",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Results per page",
    )

    @model_validator(mode="after")
    def validate_location_search(self) -> "HostelSearchRequest":
        """Validate location-based search parameters."""
        # If radius search, both lat/lon and radius are required
        has_lat = self.latitude is not None
        has_lon = self.longitude is not None
        has_radius = self.radius_km is not None

        if any([has_lat, has_lon, has_radius]):
            if not all([has_lat, has_lon, has_radius]):
                raise ValueError(
                    "For radius search, latitude, longitude, and radius_km "
                    "are all required"
                )
        return self

    @field_validator("max_price")
    @classmethod
    def validate_price_range(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        """Validate price range."""
        if v is not None:
            min_price = info.data.get("min_price")
            if min_price is not None and v < min_price:
                raise ValueError("max_price must be >= min_price")
        return v


class FacetItem(BaseSchema):
    """
    Facet item with count.
    
    Represents a filter option with result count.
    """
    model_config = ConfigDict(from_attributes=True)

    value: str = Field(..., description="Facet value")
    label: str = Field(..., description="Display label")
    count: int = Field(
        ...,
        ge=0,
        description="Number of results with this value",
    )


class PriceRangeFacet(BaseSchema):
    """
    Price range facet.
    
    Represents a price range filter option.
    """
    model_config = ConfigDict(from_attributes=True)

    min_price: Annotated[Decimal, Field(ge=0, description="Range minimum")]
    max_price: Annotated[Decimal, Field(ge=0, description="Range maximum")]
    label: str = Field(..., description="Display label")
    count: int = Field(
        ...,
        ge=0,
        description="Number of results in range",
    )


class RatingFacet(BaseSchema):
    """
    Rating facet.
    
    Represents a rating filter option.
    """
    model_config = ConfigDict(from_attributes=True)

    min_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Minimum rating")
    ]
    label: str = Field(..., description="Display label")
    count: int = Field(
        ...,
        ge=0,
        description="Number of results",
    )


class SearchFacets(BaseSchema):
    """
    Search facets for filtering.
    
    Provides available filter options with counts.
    """
    model_config = ConfigDict(from_attributes=True)

    cities: List[FacetItem] = Field(
        default_factory=list,
        description="Available cities with result counts",
    )
    hostel_types: List[FacetItem] = Field(
        default_factory=list,
        description="Hostel types with result counts",
    )
    price_ranges: List[PriceRangeFacet] = Field(
        default_factory=list,
        description="Price ranges with result counts",
    )
    amenities: List[FacetItem] = Field(
        default_factory=list,
        description="Available amenities with result counts",
    )
    ratings: List[RatingFacet] = Field(
        default_factory=list,
        description="Rating distribution",
    )


class HostelSearchResponse(BaseSchema):
    """
    Hostel search response.
    
    Complete search results with metadata and facets.
    """
    model_config = ConfigDict(from_attributes=True)

    results: List[PublicHostelCard] = Field(
        ...,
        description="Search results",
    )
    total_results: int = Field(
        ...,
        ge=0,
        description="Total matching hostels",
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )
    current_page: int = Field(
        ...,
        ge=1,
        description="Current page number",
    )
    filters_applied: dict = Field(
        default_factory=dict,
        description="Summary of applied filters",
    )
    facets: SearchFacets = Field(
        ...,
        description="Available filter facets",
    )


class HostelSearchFilters(BaseFilterSchema):
    """
    Advanced search filters.
    
    Additional filtering options for hostel search.
    """
    model_config = ConfigDict(from_attributes=True)

    # Gender
    gender: Optional[str] = Field(
        default=None,
        pattern=r"^(boys|girls|co_ed)$",
        description="Gender preference",
    )

    # Facilities (boolean filters)
    has_wifi: Optional[bool] = Field(
        default=None,
        description="Has WiFi",
    )
    has_ac: Optional[bool] = Field(
        default=None,
        description="Has AC",
    )
    has_laundry: Optional[bool] = Field(
        default=None,
        description="Has laundry facility",
    )
    has_parking: Optional[bool] = Field(
        default=None,
        description="Has parking",
    )
    has_gym: Optional[bool] = Field(
        default=None,
        description="Has gym/fitness center",
    )
    has_mess: Optional[bool] = Field(
        default=None,
        description="Has mess/canteen",
    )

    # Security
    has_cctv: Optional[bool] = Field(
        default=None,
        description="Has CCTV surveillance",
    )
    has_security_guard: Optional[bool] = Field(
        default=None,
        description="Has security guard",
    )

    # Rules
    allow_visitors: Optional[bool] = Field(
        default=None,
        description="Allows visitors",
    )

    # Availability
    check_in_date: Optional[Date] = Field(
        default=None,
        description="Desired check-in Date",
    )

    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate check-in Date is not in the past."""
        if v is not None:
            from datetime import date as dt
            if v < dt.today():
                raise ValueError("Check-in Date cannot be in the past")
        return v