"""
Search services package.

Provides comprehensive services for:

Core search:
- SearchService: Orchestrates basic, advanced, and nearby searches

Autocomplete:
- SearchAutocompleteService: Provides typeahead suggestions

Analytics:
- SearchAnalyticsService: Generates search behavior analytics

Indexing:
- SearchIndexingService: Manages search index operations

Optimization:
- SearchOptimizationService: Suggests search quality improvements

Personalization:
- SearchPersonalizationService: Personalizes search based on visitor behavior

All services are designed to be:
- Stateless and thread-safe
- Testable with dependency injection
- Backend-agnostic (SQL/Elasticsearch/etc.)
- Logging-aware with structured context
- Error-resilient with graceful degradation
"""

from .search_analytics_service import SearchAnalyticsService
from .search_autocomplete_service import SearchAutocompleteService
from .search_indexing_service import SearchIndexingService
from .search_optimization_service import SearchOptimizationService
from .search_personalization_service import SearchPersonalizationService
from .search_service import SearchService

__all__ = [
    "SearchService",
    "SearchAutocompleteService",
    "SearchAnalyticsService",
    "SearchIndexingService",
    "SearchOptimizationService",
    "SearchPersonalizationService",
]

__version__ = "1.0.0"