# --- File: app/schemas/review/review_filters.py ---
"""
Review filter and search schemas with advanced filtering options.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- field_validator and model_validator already use v2 syntax
- Rating fields use max_digits=2, decimal_places=1 for 1.0-5.0 range
- All validators properly handle Optional types
"""

from datetime import date as Date
from decimal import Decimal
from typing import Annotated, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseFilterSchema

__all__ = [
    "ReviewFilterParams",
    "ReviewSearchRequest",
    "ReviewSortOptions",
    "ReviewExportRequest",
]


class ReviewFilterParams(BaseFilterSchema):
    """
    Comprehensive review filtering parameters.
    
    Supports filtering by hostel, ratings, verification, dates, and more.
    """
    
    # Hostel filters
    hostel_id: Union[UUID, None] = Field(
        default=None,
        description="Filter by specific hostel",
    )
    hostel_ids: Union[List[UUID], None] = Field(
        default=None,
        max_length=50,
        description="Filter by multiple hostels (max 50)",
    )
    
    # Rating filters with proper Decimal constraints
    min_rating: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1.0"),
                le=Decimal("5.0"),
                max_digits=2,
                decimal_places=1,
                description="Minimum overall rating",
            ),
        ],
        None,
    ] = None
    max_rating: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1.0"),
                le=Decimal("5.0"),
                max_digits=2,
                decimal_places=1,
                description="Maximum overall rating",
            ),
        ],
        None,
    ] = None
    rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Exact rating (1-5 stars)",
    )
    
    # Verification filters
    verified_only: Union[bool, None] = Field(
        default=None,
        description="Show only verified stay reviews",
    )
    
    # Date filters
    posted_date_from: Union[Date, None] = Field(
        default=None,
        description="Reviews posted on or after this Date",
    )
    posted_date_to: Union[Date, None] = Field(
        default=None,
        description="Reviews posted on or before this Date",
    )
    
    # Status filters
    approved_only: bool = Field(
        default=True,
        description="Show only approved/published reviews",
    )
    flagged_only: Union[bool, None] = Field(
        default=None,
        description="Show only flagged reviews",
    )
    
    # Response filter
    with_hostel_response: Union[bool, None] = Field(
        default=None,
        description="Filter by presence of hostel response",
    )
    
    # Engagement filters
    min_helpful_count: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Minimum helpful vote count",
    )
    
    # Media filter
    with_photos_only: Union[bool, None] = Field(
        default=None,
        description="Show only reviews with photos",
    )
    
    @field_validator("hostel_ids")
    @classmethod
    def validate_hostel_ids(cls, v: Union[List[UUID], None]) -> Union[List[UUID], None]:
        """Validate hostel IDs list."""
        if v is not None and len(v) > 50:
            raise ValueError("Maximum 50 hostel IDs allowed")
        return v
    
    @model_validator(mode="after")
    def validate_rating_range(self) -> "ReviewFilterParams":
        """
        Validate that max_rating >= min_rating.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.max_rating is not None and self.min_rating is not None:
            if self.max_rating < self.min_rating:
                raise ValueError("max_rating must be greater than or equal to min_rating")
        return self
    
    @model_validator(mode="after")
    def validate_date_range(self) -> "ReviewFilterParams":
        """
        Validate that posted_date_to >= posted_date_from.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.posted_date_to is not None and self.posted_date_from is not None:
            if self.posted_date_to < self.posted_date_from:
                raise ValueError(
                    "posted_date_to must be on or after posted_date_from"
                )
        return self


class ReviewSearchRequest(BaseFilterSchema):
    """
    Full-text search request for reviews.
    
    Supports searching in titles and content with advanced options.
    """
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query",
        examples=["clean rooms", "friendly staff"],
    )
    hostel_id: Union[UUID, None] = Field(
        default=None,
        description="Limit search to specific hostel",
    )
    
    # Search scope
    search_in_title: bool = Field(
        default=True,
        description="Include review titles in search",
    )
    search_in_content: bool = Field(
        default=True,
        description="Include review text in search",
    )
    
    # Additional filters with proper Decimal constraints
    min_rating: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1.0"),
                le=Decimal("5.0"),
                max_digits=2,
                decimal_places=1,
                description="Filter by minimum rating",
            ),
        ],
        None,
    ] = None
    verified_only: Union[bool, None] = Field(
        default=None,
        description="Show only verified reviews",
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
    
    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate and clean search query."""
        v = v.strip()
        if not v:
            raise ValueError("Search query cannot be empty")
        return v
    
    @model_validator(mode="after")
    def validate_search_scope(self) -> "ReviewSearchRequest":
        """
        Ensure at least one search scope is selected.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if not self.search_in_title and not self.search_in_content:
            raise ValueError(
                "At least one search scope must be enabled "
                "(title or content)"
            )
        return self


class ReviewSortOptions(BaseFilterSchema):
    """
    Review sorting options with multiple strategies.
    
    Supports various sorting methods including helpful votes and recency.
    """
    
    sort_by: str = Field(
        default="helpful",
        pattern=r"^(helpful|recent|rating_high|rating_low|verified|oldest)$",
        description="Sort method",
    )
    
    # Priority options
    verified_first: bool = Field(
        default=True,
        description="Prioritize verified reviews in results",
    )
    with_photos_first: bool = Field(
        default=False,
        description="Prioritize reviews with photos",
    )
    with_response_first: bool = Field(
        default=False,
        description="Prioritize reviews with hostel responses",
    )
    
    @field_validator("sort_by")
    @classmethod
    def normalize_sort_by(cls, v: str) -> str:
        """Normalize sort_by value to lowercase."""
        return v.lower().strip()


class ReviewExportRequest(BaseFilterSchema):
    """
    Export reviews to various formats.
    
    Supports CSV, Excel, and PDF exports with customizable content.
    """
    
    hostel_id: UUID = Field(
        ...,
        description="Hostel to export reviews for",
    )
    filters: Union[ReviewFilterParams, None] = Field(
        default=None,
        description="Additional filters to apply",
    )
    
    # Export format
    format: str = Field(
        default="csv",
        pattern=r"^(csv|excel|pdf|json)$",
        description="Export format",
    )
    
    # Content options
    include_detailed_ratings: bool = Field(
        default=True,
        description="Include aspect-specific ratings",
    )
    include_hostel_responses: bool = Field(
        default=True,
        description="Include hostel responses to reviews",
    )
    include_voter_stats: bool = Field(
        default=False,
        description="Include helpful vote statistics",
    )
    include_reviewer_info: bool = Field(
        default=True,
        description="Include reviewer name and verification status",
    )
    
    # Date range for export
    date_from: Union[Date, None] = Field(
        default=None,
        description="Export reviews from this Date onwards",
    )
    date_to: Union[Date, None] = Field(
        default=None,
        description="Export reviews up to this Date",
    )
    
    @field_validator("format")
    @classmethod
    def normalize_format(cls, v: str) -> str:
        """Normalize format to lowercase."""
        return v.lower().strip()
    
    @model_validator(mode="after")
    def validate_date_range(self) -> "ReviewExportRequest":
        """
        Validate export Date range.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.date_to is not None and self.date_from is not None:
            if self.date_to < self.date_from:
                raise ValueError("date_to must be on or after date_from")
        return self