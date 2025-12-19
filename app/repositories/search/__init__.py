"""
Search Repositories Package

Comprehensive repository layer for search functionality including
query logging, analytics, autocomplete, and aggregation.
"""

from app.repositories.search.search_query_log_repository import (
    SearchQueryLogRepository,
    SearchSessionRepository,
    SavedSearchRepository
)
from app.repositories.search.search_analytics_repository import (
    SearchTermStatsRepository,
    SearchMetricsRepository,
    PopularSearchTermRepository,
    TrendingSearchRepository,
    ZeroResultTermRepository,
    SearchAnalyticsReportRepository
)
from app.repositories.search.search_autocomplete_repository import (
    AutocompleteSuggestionRepository,
    AutocompleteQueryLogRepository,
    SuggestionSourceRepository,
    PopularSearchSuggestionRepository,
    SuggestionPerformanceRepository
)
from app.repositories.search.search_aggregate_repository import (
    SearchAggregateRepository
)

__all__ = [
    # Query logging repositories
    "SearchQueryLogRepository",
    "SearchSessionRepository",
    "SavedSearchRepository",
    
    # Analytics repositories
    "SearchTermStatsRepository",
    "SearchMetricsRepository",
    "PopularSearchTermRepository",
    "TrendingSearchRepository",
    "ZeroResultTermRepository",
    "SearchAnalyticsReportRepository",
    
    # Autocomplete repositories
    "AutocompleteSuggestionRepository",
    "AutocompleteQueryLogRepository",
    "SuggestionSourceRepository",
    "PopularSearchSuggestionRepository",
    "SuggestionPerformanceRepository",
    
    # Aggregate repository
    "SearchAggregateRepository",
]