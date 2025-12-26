"""
Visitor services package.

Provides comprehensive services for visitor profile management, dashboards,
favorites, preferences, saved searches, recommendations, conversions, and
behavioral tracking.

All services follow consistent patterns:
- Comprehensive error handling and logging
- Input validation
- Transaction management
- Caching where appropriate
- GDPR-compliant data handling
"""

from .saved_search_service import SavedSearchService
from .visitor_conversion_service import VisitorConversionService
from .visitor_dashboard_service import VisitorDashboardService
from .visitor_favorite_service import VisitorFavoriteService
from .visitor_preference_service import VisitorPreferenceService
from .visitor_recommendation_service import VisitorRecommendationService
from .visitor_service import VisitorService
from .visitor_tracking_service import VisitorTrackingService

__all__ = [
    "SavedSearchService",
    "VisitorConversionService",
    "VisitorDashboardService",
    "VisitorFavoriteService",
    "VisitorPreferenceService",
    "VisitorRecommendationService",
    "VisitorService",
    "VisitorTrackingService",
]

__version__ = "1.0.0"