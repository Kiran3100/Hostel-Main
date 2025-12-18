"""
Search models package initialization.

Provides comprehensive search functionality including:
- Query logging and session tracking
- Advanced analytics and insights
- Autocomplete and intelligent suggestions
- Performance monitoring and optimization
"""

from app.models.search.search_analytics import (
    SearchTermStats,
    SearchMetrics,
    PopularSearchTerm,
    TrendingSearch,
    ZeroResultTerm,
    SearchAnalyticsReport,
)
from app.models.search.search_autocomplete import (
    AutocompleteSuggestion,
    AutocompleteQueryLog,
    SuggestionSource,
    PopularSearchSuggestion,
    SuggestionPerformance,
)
from app.models.search.search_query_log import (
    SearchQueryLog,
    SearchSession,
    SavedSearch,
)

__all__ = [
    # Query logging models
    "SearchQueryLog",
    "SearchSession",
    "SavedSearch",
    
    # Analytics models
    "SearchTermStats",
    "SearchMetrics",
    "PopularSearchTerm",
    "TrendingSearch",
    "ZeroResultTerm",
    "SearchAnalyticsReport",
    
    # Autocomplete models
    "AutocompleteSuggestion",
    "AutocompleteQueryLog",
    "SuggestionSource",
    "PopularSearchSuggestion",
    "SuggestionPerformance",
]