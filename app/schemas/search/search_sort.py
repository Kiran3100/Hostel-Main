# --- File: app/schemas/search/search_sort.py ---
"""
Search sorting schemas with type-safe sort options.

Provides strongly-typed sorting criteria for search results.

Pydantic v2 Migration Notes:
- field_validator syntax already compatible with v2
- @computed_field with @property for computed properties
- Enum-based fields work identically in v2
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field, field_validator, computed_field

from app.schemas.common.base import BaseSchema

__all__ = [
    "SearchSortField",
    "SearchSortOrder",
    "SortCriteria",
]


class SearchSortField(str, Enum):
    """
    Available sort fields for search results.

    Provides type-safe sort field options.
    """

    RELEVANCE = "relevance"
    PRICE_LOW_TO_HIGH = "price_asc"
    PRICE_HIGH_TO_LOW = "price_desc"
    RATING_HIGH_TO_LOW = "rating_desc"
    DISTANCE_NEAR_TO_FAR = "distance_asc"
    NEWEST_FIRST = "newest"
    POPULAR = "popular"
    AVAILABILITY = "availability"


class SearchSortOrder(str, Enum):
    """Sort order direction."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class SortCriteria(BaseSchema):
    """
    Sort criteria for search results.

    Provides flexible sorting with primary and optional secondary sort.
    """

    sort_by: SearchSortField = Field(
        default=SearchSortField.RELEVANCE,
        description="Primary sort field",
    )
    sort_order: SearchSortOrder = Field(
        default=SearchSortOrder.DESCENDING,
        description="Sort direction (for applicable fields)",
    )

    # Secondary sort (for tie-breaking)
    secondary_sort_by: Optional[SearchSortField] = Field(
        default=None,
        description="Secondary sort field for tie-breaking",
    )
    secondary_sort_order: Optional[SearchSortOrder] = Field(
        default=None,
        description="Secondary sort direction",
    )

    @field_validator("sort_by")
    @classmethod
    def validate_sort_field(cls, v: SearchSortField) -> SearchSortField:
        """Validate sort field is appropriate."""
        # Some sort fields have implicit direction
        implicit_direction_fields = {
            SearchSortField.PRICE_LOW_TO_HIGH,
            SearchSortField.PRICE_HIGH_TO_LOW,
            SearchSortField.RATING_HIGH_TO_LOW,
            SearchSortField.DISTANCE_NEAR_TO_FAR,
        }

        # These fields encode direction in the field name
        # The sort_order parameter will be ignored for them
        # No validation needed - just documenting the behavior
        return v

    @computed_field  # type: ignore[misc]
    @property
    def effective_sort_order(self) -> SearchSortOrder:
        """
        Get effective sort order based on sort field.

        Some fields have implicit direction (e.g., price_asc always means ascending).
        """
        # Fields with implicit direction
        if self.sort_by == SearchSortField.PRICE_LOW_TO_HIGH:
            return SearchSortOrder.ASCENDING
        elif self.sort_by == SearchSortField.PRICE_HIGH_TO_LOW:
            return SearchSortOrder.DESCENDING
        elif self.sort_by == SearchSortField.RATING_HIGH_TO_LOW:
            return SearchSortOrder.DESCENDING
        elif self.sort_by == SearchSortField.DISTANCE_NEAR_TO_FAR:
            return SearchSortOrder.ASCENDING

        # For other fields, use specified sort_order
        return self.sort_order

    def to_db_sort(self) -> tuple[str, str]:
        """
        Convert to database sort parameters.

        Returns:
            Tuple of (field_name, direction) for database queries
        """
        field_mapping = {
            SearchSortField.RELEVANCE: "relevance_score",
            SearchSortField.PRICE_LOW_TO_HIGH: "min_price",
            SearchSortField.PRICE_HIGH_TO_LOW: "max_price",
            SearchSortField.RATING_HIGH_TO_LOW: "average_rating",
            SearchSortField.DISTANCE_NEAR_TO_FAR: "distance",
            SearchSortField.NEWEST_FIRST: "created_at",
            SearchSortField.POPULAR: "popularity_score",
            SearchSortField.AVAILABILITY: "available_beds",
        }

        field = field_mapping.get(self.sort_by, "relevance_score")
        direction = self.effective_sort_order.value

        return field, direction