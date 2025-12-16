# --- File: app/schemas/search/search_response.py ---
"""
Search response schemas with comprehensive result metadata.

Provides schemas for:
- Search result items
- Faceted search responses
- Search metadata and diagnostics
- Search suggestions

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with max_digits/decimal_places constraints
- Union[X, None] instead of Optional[X] for compatibility
- @computed_field with @property decorator for computed properties
- All field validators use v2 syntax (none present in this schema)
"""

from decimal import Decimal
from typing import Annotated, Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseSchema

__all__ = [
    "SearchResultItem",
    "SearchMetadata",
    "FacetBucket",
    "SearchSuggestion",
    "FacetedSearchResponse",
]


class SearchResultItem(BaseSchema):
    """
    Individual search result item.

    Wraps hostel data with search-specific metadata like relevance score.
    """

    # Hostel identifier
    hostel_id: UUID = Field(
        ...,
        description="Unique hostel identifier",
    )

    # Basic hostel information (denormalized for performance)
    name: str = Field(..., description="Hostel name")
    slug: str = Field(..., description="URL-friendly slug")
    hostel_type: str = Field(..., description="Hostel type")

    # Location
    city: str = Field(..., description="City")
    state: str = Field(..., description="State")
    address_line1: str = Field(..., description="Primary address")

    # Pricing - Using Decimal with precision constraints for currency values
    min_price: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Minimum monthly price across all rooms",
        ),
    ]
    max_price: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Maximum monthly price across all rooms",
        ),
    ]

    # Ratings and reviews
    # Pydantic v2: For Union[Decimal, None] with constraints, use Annotated pattern
    average_rating: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                le=5,
                max_digits=3,
                decimal_places=2,
                description="Average rating (0-5)",
            ),
        ],
        None,
    ] = None
    total_reviews: int = Field(
        default=0,
        ge=0,
        description="Total number of reviews",
    )

    # Availability
    available_beds: int = Field(
        default=0,
        ge=0,
        description="Number of currently available beds",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total bed capacity",
    )

    # Media
    thumbnail_url: Union[str, None] = Field(
        default=None,
        description="Primary image URL",
    )
    image_urls: List[str] = Field(
        default_factory=list,
        description="Additional image URLs",
    )

    # Amenities (top/featured only for performance)
    featured_amenities: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Top featured amenities",
    )

    # Verification and quality indicators
    is_verified: bool = Field(
        default=False,
        description="Hostel verification status",
    )
    is_featured: bool = Field(
        default=False,
        description="Featured/promoted status",
    )

    # Search-specific metadata
    relevance_score: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=4,
            description="Relevance score from search engine (higher = more relevant)",
        ),
    ]
    distance_km: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Distance from search location (if proximity search)",
            ),
        ],
        None,
    ] = None

    # Highlighting (search term matches)
    highlights: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Highlighted snippets showing search term matches",
        examples=[{"name": ["Best <em>Hostel</em> in Mumbai"]}],
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def occupancy_rate(self) -> Decimal:
        """Calculate current occupancy rate as percentage."""
        if self.total_beds == 0:
            return Decimal("0")
        occupied = self.total_beds - self.available_beds
        return Decimal(occupied / self.total_beds * 100).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_availability(self) -> bool:
        """Check if hostel has any available beds."""
        return self.available_beds > 0


class SearchMetadata(BaseSchema):
    """
    Search execution metadata and diagnostics.

    Provides insights into search performance and result quality.
    """

    # Result counts
    total_results: int = Field(
        ...,
        ge=0,
        description="Total number of matching results",
    )
    returned_results: int = Field(
        ...,
        ge=0,
        description="Number of results in current page",
    )

    # Pagination
    page: int = Field(
        ...,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        ...,
        ge=1,
        description="Results per page",
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )

    # Performance metrics
    query_time_ms: int = Field(
        ...,
        ge=0,
        description="Search execution time in milliseconds",
    )
    fetch_time_ms: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Data fetch time in milliseconds",
    )

    # Query information
    applied_filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Filters that were applied to this search",
    )
    sort_criteria: str = Field(
        ...,
        description="Sort order applied",
    )

    # Result quality indicators
    # Pydantic v2: Union[Decimal, None] with constraints uses Annotated pattern
    max_score: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=4,
                description="Highest relevance score in results",
            ),
        ],
        None,
    ] = None
    min_score: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=4,
                description="Lowest relevance score in results",
            ),
        ],
        None,
    ] = None

    # Debug information (optional, for development)
    debug_info: Union[Dict[str, Any], None] = Field(
        default=None,
        description="Debug information (available in development mode)",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_next_page(self) -> bool:
        """Check if there are more pages available."""
        return self.page < self.total_pages

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_previous_page(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1


class FacetBucket(BaseSchema):
    """
    Single facet value with count.

    Used in faceted search to show available filter options.
    """

    value: str = Field(
        ...,
        description="Facet value (e.g., 'Mumbai' for city facet)",
    )
    label: str = Field(
        ...,
        description="Human-readable label",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of results with this facet value",
    )
    is_selected: bool = Field(
        default=False,
        description="Whether this facet is currently selected/active",
    )

    # Additional metadata
    metadata: Union[Dict[str, Any], None] = Field(
        default=None,
        description="Additional facet-specific metadata",
    )


class SearchSuggestion(BaseSchema):
    """
    Search query suggestion for refinement.

    Helps users refine their search when results are poor.
    """

    suggestion_type: str = Field(
        ...,
        pattern=r"^(spell_correction|alternative_query|related_search|popular_search)$",
        description="Type of suggestion",
    )
    text: str = Field(
        ...,
        description="Suggested search text",
    )
    reason: Union[str, None] = Field(
        default=None,
        description="Why this suggestion is offered",
        examples=[
            "Did you mean...",
            "Popular search",
            "Related to your search",
        ],
    )
    expected_results: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Estimated number of results for this suggestion",
    )


class FacetedSearchResponse(BaseSchema):
    """
    Complete faceted search response.

    Includes results, facets, and comprehensive metadata.
    """

    # Search results
    results: List[SearchResultItem] = Field(
        default_factory=list,
        description="Search result items",
    )

    # Metadata
    metadata: SearchMetadata = Field(
        ...,
        description="Search execution metadata",
    )

    # Facets for filtering
    facets: Dict[str, List[FacetBucket]] = Field(
        default_factory=dict,
        description="Available facets organized by facet name",
        examples=[
            {
                "city": [
                    {"value": "mumbai", "label": "Mumbai", "count": 45},
                    {"value": "bangalore", "label": "Bangalore", "count": 32},
                ],
                "hostel_type": [
                    {"value": "boys", "label": "Boys", "count": 50},
                    {"value": "girls", "label": "Girls", "count": 27},
                ],
            }
        ],
    )

    # Search suggestions (for query refinement)
    suggestions: List[SearchSuggestion] = Field(
        default_factory=list,
        description="Suggested query refinements",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_empty(self) -> bool:
        """Check if search returned no results."""
        return len(self.results) == 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def facet_names(self) -> List[str]:
        """Get list of available facet names."""
        return list(self.facets.keys())