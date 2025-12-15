# --- File: app/schemas/search/search_autocomplete.py ---
"""
Autocomplete and suggestion schemas for search.

Provides real-time search suggestions as users type.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "SuggestionType",
    "AutocompleteRequest",
    "Suggestion",
    "AutocompleteResponse",
]


class SuggestionType(str, Enum):
    """
    Type of autocomplete suggestion.

    Helps categorize and display suggestions appropriately.
    """

    HOSTEL = "hostel"
    CITY = "city"
    AREA = "area"
    LANDMARK = "landmark"
    AMENITY = "amenity"
    POPULAR_SEARCH = "popular_search"


class AutocompleteRequest(BaseCreateSchema):
    """
    Autocomplete request for search suggestions.

    Optimized for real-time typeahead functionality.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    prefix: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Search prefix (user's partial input)",
        examples=["mumb", "boys host", "pg near"],
    )
    suggestion_type: Optional[SuggestionType] = Field(
        default=None,
        description="Filter suggestions by type (optional)",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of suggestions to return",
    )

    # Context for personalization
    user_latitude: Optional[float] = Field(
        default=None,
        ge=-90,
        le=90,
        description="User latitude for location-based suggestions",
    )
    user_longitude: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180,
        description="User longitude for location-based suggestions",
    )

    # Filtering
    include_types: Optional[List[SuggestionType]] = Field(
        default=None,
        description="Include only these suggestion types",
        examples=[["hostel", "city"]],
    )
    exclude_types: Optional[List[SuggestionType]] = Field(
        default=None,
        description="Exclude these suggestion types",
    )

    @field_validator("prefix")
    @classmethod
    def normalize_prefix(cls, v: str) -> str:
        """
        Normalize search prefix.

        - Trim whitespace
        - Convert to lowercase for matching
        """
        normalized = v.strip().lower()
        if not normalized:
            raise ValueError("Search prefix cannot be empty or only whitespace")
        return normalized

    @field_validator("include_types", "exclude_types")
    @classmethod
    def validate_type_lists(
        cls,
        v: Optional[List[SuggestionType]],
    ) -> Optional[List[SuggestionType]]:
        """Remove duplicates from type lists."""
        if v is not None:
            return list(dict.fromkeys(v))  # Preserve order while removing dupes
        return v


class Suggestion(BaseSchema):
    """
    Single autocomplete suggestion.

    Provides rich metadata for displaying suggestions.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Core fields
    value: str = Field(
        ...,
        description="Suggestion value (what to insert into search)",
        examples=["Mumbai", "Boys Hostel in Andheri"],
    )
    label: str = Field(
        ...,
        description="Display label (formatted for UI)",
        examples=["Mumbai, Maharashtra", "Boys Hostel in Andheri (15 results)"],
    )
    type: SuggestionType = Field(
        ...,
        description="Suggestion type",
    )

    # Metadata
    score: float = Field(
        default=0.0,
        ge=0,
        description="Relevance/popularity score",
    )
    result_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated number of results for this suggestion",
    )

    # Rich data (optional)
    icon: Optional[str] = Field(
        default=None,
        description="Icon identifier for UI display",
        examples=["location", "building", "search"],
    )
    thumbnail_url: Optional[str] = Field(
        default=None,
        description="Thumbnail image URL (for hostel suggestions)",
    )

    # Additional context
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional type-specific metadata",
        examples=[
            {"city": "Mumbai", "state": "Maharashtra"},
            {"hostel_id": "uuid", "min_price": 10000},
        ],
    )

    # Highlighting
    highlighted_label: Optional[str] = Field(
        default=None,
        description="Label with matched portions highlighted (HTML)",
        examples=["<strong>Mumb</strong>ai, Maharashtra"],
    )


class AutocompleteResponse(BaseSchema):
    """
    Autocomplete response with suggestions.

    Groups suggestions by type for better UX.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    suggestions: List[Suggestion] = Field(
        default_factory=list,
        description="Ordered list of suggestions",
    )

    # Grouped suggestions (optional, for categorized display)
    grouped_suggestions: Optional[Dict[str, List[Suggestion]]] = Field(
        default=None,
        description="Suggestions grouped by type",
        examples=[
            {
                "hostel": [{"value": "XYZ Hostel", "label": "XYZ Hostel"}],
                "city": [{"value": "Mumbai", "label": "Mumbai, Maharashtra"}],
            }
        ],
    )

    # Metadata
    prefix: str = Field(
        ...,
        description="Original search prefix",
    )
    total_suggestions: int = Field(
        ...,
        ge=0,
        description="Total number of suggestions returned",
    )
    execution_time_ms: int = Field(
        ...,
        ge=0,
        description="Suggestion generation time in milliseconds",
    )

    # Popular searches (shown when no prefix match)
    popular_searches: Optional[List[str]] = Field(
        default=None,
        description="Popular search terms (shown for empty/short prefix)",
        examples=[["Boys Hostel Mumbai", "PG in Bangalore", "Hostel near me"]],
    )

    @classmethod
    def create_grouped(
        cls,
        suggestions: List[Suggestion],
        prefix: str,
        execution_time_ms: int = 0,
    ) -> "AutocompleteResponse":
        """
        Create response with automatic grouping by type.

        Args:
            suggestions: List of suggestions
            prefix: Original search prefix
            execution_time_ms: Execution time

        Returns:
            AutocompleteResponse with grouped suggestions
        """
        # Group suggestions by type
        grouped: Dict[str, List[Suggestion]] = {}
        for suggestion in suggestions:
            type_key = suggestion.type.value
            if type_key not in grouped:
                grouped[type_key] = []
            grouped[type_key].append(suggestion)

        return cls(
            suggestions=suggestions,
            grouped_suggestions=grouped if grouped else None,
            prefix=prefix,
            total_suggestions=len(suggestions),
            execution_time_ms=execution_time_ms,
        )