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

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Union, Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field, ConfigDict

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseFilterSchema,
    BaseResponseSchema,
    BaseUpdateSchema,
    BaseSchema,
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
    "SavedSearch",
    "SavedSearchExecution",
    "SavedSearchList",
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
    query: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Optional search keywords",
        examples=["boys hostel", "PG with meals"],
    )

    # Location filters
    city: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="City name",
        examples=["Mumbai", "Bangalore"],
    )
    state: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="State name",
        examples=["Maharashtra", "Karnataka"],
    )
    pincode: Union[str, None] = Field(
        default=None,
        pattern=r"^\d{6}$",
        description="6-digit Indian pincode",
        examples=["400001", "560001"],
    )

    # Geographic coordinates for proximity search
    latitude: Union[Annotated[Decimal, Field(ge=-90, le=90)], None] = Field(
        default=None,
        description="Latitude for proximity search",
        examples=[19.0760],
    )
    longitude: Union[Annotated[Decimal, Field(ge=-180, le=180)], None] = Field(
        default=None,
        description="Longitude for proximity search",
        examples=[72.8777],
    )
    radius_km: Union[Annotated[Decimal, Field(ge=0.1, le=100)], None] = Field(
        default=None,
        description="Search radius in kilometers",
        examples=[5, 10, 25],
    )

    # Hostel and room type filters
    hostel_type: Union[HostelType, None] = Field(
        default=None,
        description="Filter by hostel type (boys/girls/co-ed)",
    )
    room_types: Union[List[RoomType], None] = Field(
        default=None,
        description="Filter by room types (can select multiple)",
        examples=[["single", "double"]],
    )

    # Gender preference (for co-ed hostels)
    gender_preference: Union[Gender, None] = Field(
        default=None,
        description="Gender preference for room allocation",
    )

    # Price range filter
    min_price: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        default=None,
        description="Minimum monthly price in INR",
        examples=[5000, 10000],
    )
    max_price: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        default=None,
        description="Maximum monthly price in INR",
        examples=[20000, 30000],
    )

    # Amenities filter
    amenities: Union[List[str], None] = Field(
        default=None,
        description="Required amenities (AND logic - hostel must have all)",
        examples=[["wifi", "ac", "parking"]],
    )
    any_amenities: Union[List[str], None] = Field(
        default=None,
        description="Optional amenities (OR logic - hostel can have any)",
        examples=[["gym", "laundry", "swimming_pool"]],
    )

    # Rating filter
    min_rating: Union[Annotated[Decimal, Field(ge=0, le=5)], None] = Field(
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
    check_in_date: Union[Date, None] = Field(
        default=None,
        description="Desired check-in Date for availability check",
    )
    check_out_date: Union[Date, None] = Field(
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
    def normalize_query(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize search query."""
        if v is not None:
            normalized = " ".join(v.split())
            return normalized if normalized else None
        return v

    @field_validator("city", "state")
    @classmethod
    def normalize_location(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize location strings."""
        if v is not None:
            return v.strip().title()
        return v

    @field_validator("amenities", "any_amenities")
    @classmethod
    def normalize_amenities(cls, v: Union[List[str], None]) -> Union[List[str], None]:
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

    @computed_field  # type: ignore[prop-decorator]
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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_price_filter(self) -> bool:
        """Check if price filter is applied."""
        return self.min_price is not None or self.max_price is not None

    @computed_field  # type: ignore[prop-decorator]
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
    hostel_type: Union[HostelType, None] = Field(
        default=None,
        description="Filter by hostel type",
    )
    min_price: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        default=None,
        description="Minimum price filter",
    )
    max_price: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
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
    alert_frequency: Union[str, None] = Field(
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

    name: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated name",
    )
    search_criteria: Union[Dict[str, Any], None] = Field(
        default=None,
        description="Updated search parameters",
    )
    is_alert_enabled: Union[bool, None] = Field(
        default=None,
        description="Enable/disable alerts",
    )
    alert_frequency: Union[str, None] = Field(
        default=None,
        pattern=r"^(daily|weekly|instant)$",
        description="Alert frequency",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: Union[str, None]) -> Union[str, None]:
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
    alert_frequency: Union[str, None] = Field(default=None, description="Alert frequency")
    last_executed_at: Union[datetime, None] = Field(
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

    user_id: Union[UUID, None] = Field(
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


# NEW SCHEMAS FOR ROUTER COMPATIBILITY

class SavedSearch(SavedSearchResponse):
    """
    Alias for SavedSearchResponse to match router expectations.
    
    This provides backward compatibility with existing router code
    while maintaining the same validation and structure.
    """
    pass


class SavedSearchExecution(BaseResponseSchema):
    """
    Results from executing a saved search.
    
    Contains both the search results and execution metadata.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    # Execution metadata
    saved_search_id: UUID = Field(..., description="ID of the executed saved search")
    executed_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="When the search was executed"
    )
    execution_time_ms: int = Field(
        ...,
        ge=0,
        description="Search execution time in milliseconds"
    )
    
    # Results summary
    total_results: int = Field(
        ...,
        ge=0,
        description="Total number of results found"
    )
    new_results_count: int = Field(
        default=0,
        ge=0,
        description="Number of new results since last execution"
    )
    
    # Actual search results (imported from search_response.py)
    # Note: This creates a circular import issue that needs to be resolved
    # For now, using Any - should be List[SearchResultItem] 
    results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Search result items"
    )
    
    # Search metadata (imported from search_response.py)  
    # Note: Same circular import issue - should be SearchMetadata
    search_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Search execution metadata"
    )
    
    # Comparison with previous execution
    previous_result_count: Union[int, None] = Field(
        default=None,
        description="Result count from previous execution (for trending)"
    )
    trend_direction: Union[str, None] = Field(
        default=None,
        pattern=r"^(up|down|stable)$",
        description="Result trend since last execution"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_new_results(self) -> bool:
        """Check if there are new results since last execution."""
        return self.new_results_count > 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def result_trend(self) -> str:
        """Get human-readable result trend."""
        if self.previous_result_count is None:
            return "first_execution"
        
        if self.total_results > self.previous_result_count:
            return "increased"
        elif self.total_results < self.previous_result_count:
            return "decreased"
        else:
            return "unchanged"


class SavedSearchList(BaseSchema):
    """
    Paginated list of saved searches with metadata.
    
    Provides comprehensive listing functionality for saved searches.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )
    
    # List data
    saved_searches: List[SavedSearchResponse] = Field(
        default_factory=list,
        description="List of saved searches"
    )
    
    # Pagination metadata
    total: int = Field(
        ...,
        ge=0,
        description="Total number of saved searches"
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Current page number"
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page"
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages"
    )
    
    # List metadata
    active_searches: int = Field(
        default=0,
        ge=0,
        description="Number of active saved searches"
    )
    searches_with_alerts: int = Field(
        default=0,
        ge=0,
        description="Number of searches with alerts enabled"
    )
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_next_page(self) -> bool:
        """Check if there are more pages."""
        return self.page < self.total_pages
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_previous_page(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_empty(self) -> bool:
        """Check if list is empty."""
        return self.total == 0

    @classmethod
    def create_paginated(
        cls,
        saved_searches: List[SavedSearchResponse],
        total: int,
        page: int = 1,
        page_size: int = 20,
    ) -> "SavedSearchList":
        """
        Create paginated list with calculated metadata.
        
        Args:
            saved_searches: List of saved searches for current page
            total: Total number of saved searches
            page: Current page number
            page_size: Items per page
            
        Returns:
            SavedSearchList with calculated pagination metadata
        """
        import math
        
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        active_searches = sum(1 for search in saved_searches if search.is_alert_enabled)
        searches_with_alerts = active_searches  # Same as active for now
        
        return cls(
            saved_searches=saved_searches,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            active_searches=active_searches,
            searches_with_alerts=searches_with_alerts,
        )