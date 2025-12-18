# --- File: app/models/visitor/__init__.py ---
"""
Visitor models package.

This module exports all visitor-related SQLAlchemy models for database
operations and relationship management.
"""

from app.models.visitor.saved_search import (
    SavedSearch,
    SavedSearchExecution,
    SavedSearchMatch,
    SavedSearchNotification,
)
from app.models.visitor.visitor import (
    Visitor,
    VisitorEngagement,
    VisitorJourney,
    VisitorSegment,
    VisitorSession,
)
from app.models.visitor.visitor_dashboard import (
    AvailabilityAlert,
    PriceDropAlert,
    RecentSearch,
    RecentlyViewedHostel,
    RecommendedHostel,
    VisitorActivity,
)
from app.models.visitor.visitor_favorite import (
    FavoriteComparison,
    FavoritePriceHistory,
    VisitorFavorite,
)
from app.models.visitor.visitor_preferences import (
    NotificationPreferences,
    SearchPreferences,
    VisitorPreferences,
)

__all__ = [
    # Core Visitor Models
    "Visitor",
    "VisitorSession",
    "VisitorJourney",
    "VisitorSegment",
    "VisitorEngagement",
    # Preferences
    "VisitorPreferences",
    "SearchPreferences",
    "NotificationPreferences",
    # Favorites
    "VisitorFavorite",
    "FavoriteComparison",
    "FavoritePriceHistory",
    # Dashboard Components
    "RecentSearch",
    "RecentlyViewedHostel",
    "RecommendedHostel",
    "PriceDropAlert",
    "AvailabilityAlert",
    "VisitorActivity",
    # Saved Searches
    "SavedSearch",
    "SavedSearchExecution",
    "SavedSearchMatch",
    "SavedSearchNotification",
]