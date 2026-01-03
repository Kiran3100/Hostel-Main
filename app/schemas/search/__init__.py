# --- File: app/schemas/search/__init__.py ---
"""
Search schemas package.

Provides comprehensive search functionality including:
- Basic and advanced hostel search
- Autocomplete and suggestions
- Search analytics and insights
- Faceted search with filtering
- Search history tracking

Example:
    from app.schemas.search import (
        AdvancedSearchRequest,
        FacetedSearchResponse,
        SearchAnalytics,
    )
"""

from app.schemas.search.search_analytics import (
    PopularSearchTerm,
    SearchAnalytics,
    SearchAnalyticsRequest,
    SearchMetrics,
    SearchTermStats,
    TrendingSearch,
    ZeroResultTerm,
)
from app.schemas.search.search_autocomplete import (
    AutocompleteRequest,
    AutocompleteResponse,
    Suggestion,
    SuggestionType,
)
from app.schemas.search.search_filters import (
    AmenityFilter,
    AvailabilityFilter,
    LocationFilter,
    PriceFilter,
    RatingFilter,
    SearchFilterSet,
)
from app.schemas.search.search_request import (
    AdvancedSearchRequest,
    BasicSearchRequest,
    NearbySearchRequest,
    SavedSearchCreate,
    SavedSearchResponse,
    SavedSearchUpdate,
    SearchHistoryResponse,
    # New schemas for router compatibility
    SavedSearch,
    SavedSearchExecution,
    SavedSearchList,
)
from app.schemas.search.search_response import (
    FacetBucket,
    FacetedSearchResponse,
    SearchMetadata,
    SearchResultItem,
    SearchSuggestion,
)
from app.schemas.search.search_sort import (
    SearchSortField,
    SearchSortOrder,
    SortCriteria,
)

__all__ = [
    # Request schemas
    "BasicSearchRequest",
    "AdvancedSearchRequest",
    "NearbySearchRequest",
    "SavedSearchCreate",
    "SavedSearchUpdate",
    # Response schemas
    "SearchResultItem",
    "FacetedSearchResponse",
    "SearchMetadata",
    "SearchSuggestion",
    "FacetBucket",
    "SavedSearchResponse",
    "SearchHistoryResponse",
    # New schemas for router compatibility
    "SavedSearch",
    "SavedSearchExecution", 
    "SavedSearchList",
    # Autocomplete
    "AutocompleteRequest",
    "AutocompleteResponse",
    "Suggestion",
    "SuggestionType",
    # Filters
    "PriceFilter",
    "RatingFilter",
    "AmenityFilter",
    "LocationFilter",
    "AvailabilityFilter",
    "SearchFilterSet",
    # Sort
    "SortCriteria",
    "SearchSortField",
    "SearchSortOrder",
    # Analytics
    "SearchAnalytics",
    "SearchAnalyticsRequest",
    "SearchTermStats",
    "SearchMetrics",
    "PopularSearchTerm",
    "TrendingSearch",
    "ZeroResultTerm",
]