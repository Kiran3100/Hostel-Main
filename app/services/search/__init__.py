"""
Search services package.

Provides services for:

- Core search:
  - SearchService

- Autocomplete:
  - SearchAutocompleteService

- Analytics:
  - SearchAnalyticsService

- Indexing:
  - SearchIndexingService

- Optimization:
  - SearchOptimizationService

- Personalization:
  - SearchPersonalizationService
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