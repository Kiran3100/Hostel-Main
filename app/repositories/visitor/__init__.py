# --- File: app/repositories/visitor/__init__.py ---
"""
Visitor repositories package.

This module exports all visitor-related repository classes for
database operations and business logic.
"""

from app.repositories.visitor.visitor_repository import (
    VisitorRepository,
    VisitorSessionRepository,
    VisitorEngagementRepository,
)
from app.repositories.visitor.visitor_preferences_repository import (
    VisitorPreferencesRepository,
    SearchPreferencesRepository,
    NotificationPreferencesRepository,
)
from app.repositories.visitor.visitor_favorite_repository import (
    VisitorFavoriteRepository,
    FavoriteComparisonRepository,
    FavoritePriceHistoryRepository,
)
from app.repositories.visitor.visitor_dashboard_repository import (
    RecentSearchRepository,
    RecentlyViewedHostelRepository,
    RecommendedHostelRepository,
    PriceDropAlertRepository,
    AvailabilityAlertRepository,
    VisitorActivityRepository,
)
from app.repositories.visitor.saved_search_repository import (
    SavedSearchRepository,
    SavedSearchExecutionRepository,
    SavedSearchMatchRepository,
    SavedSearchNotificationRepository,
)
from app.repositories.visitor.visitor_aggregate_repository import (
    VisitorAggregateRepository,
)

__all__ = [
    # Core Visitor Repositories
    "VisitorRepository",
    "VisitorSessionRepository",
    "VisitorEngagementRepository",
    # Preferences Repositories
    "VisitorPreferencesRepository",
    "SearchPreferencesRepository",
    "NotificationPreferencesRepository",
    # Favorites Repositories
    "VisitorFavoriteRepository",
    "FavoriteComparisonRepository",
    "FavoritePriceHistoryRepository",
    # Dashboard Repositories
    "RecentSearchRepository",
    "RecentlyViewedHostelRepository",
    "RecommendedHostelRepository",
    "PriceDropAlertRepository",
    "AvailabilityAlertRepository",
    "VisitorActivityRepository",
    # Saved Search Repositories
    "SavedSearchRepository",
    "SavedSearchExecutionRepository",
    "SavedSearchMatchRepository",
    "SavedSearchNotificationRepository",
    # Aggregate Repository
    "VisitorAggregateRepository",
]