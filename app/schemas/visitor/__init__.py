# --- File: app/schemas/visitor/__init__.py ---
"""
Visitor schemas package.

This module exports all visitor-related schemas for easy importing
across the application.
"""

from app.schemas.visitor.visitor_base import (
    VisitorBase,
    VisitorCreate,
    VisitorUpdate,
)
from app.schemas.visitor.visitor_dashboard import (
    ActivityItem,
    ActivityTimeline,
    AvailabilityAlert,
    BookingHistory,
    BookingHistoryItem,
    DashboardSummary,
    PriceDropAlert,
    QuickAction,
    QuickActions,
    RecentSearch,
    RecentlyViewedHostel,
    RecommendedHostel,
    SavedHostelItem,
    SavedHostels,
    VisitorDashboard,
)
from app.schemas.visitor.visitor_favorites import (
    FavoriteBulkOperation,
    FavoriteComparison,
    FavoriteHostelItem,
    FavoriteRequest,
    FavoritesList,
    FavoriteUpdate,
    FavoritesExport,
)
from app.schemas.visitor.visitor_preferences import (
    DisplayPreferences,
    NotificationPreferences,
    PreferenceUpdate,
    PreferencesUpdate,
    PrivacyPreferences,
    SavedSearch,
    SearchPreferences,
    VisitorPreferences,
)
from app.schemas.visitor.visitor_recommendations import (
    RecommendationExplanation,
    RecommendationFeedback,
    RecommendationReason,
)
from app.schemas.visitor.visitor_response import (
    VisitorDetail,
    VisitorProfile,
    VisitorResponse,
    VisitorStats,
)

__all__ = [
    # Base Schemas
    "VisitorBase",
    "VisitorCreate",
    "VisitorUpdate",
    # Response Schemas
    "VisitorResponse",
    "VisitorProfile",
    "VisitorDetail",
    "VisitorStats",
    # Preferences
    "VisitorPreferences",
    "PreferenceUpdate",
    "PreferencesUpdate",
    "NotificationPreferences",
    "PrivacyPreferences",
    "DisplayPreferences",
    "SearchPreferences",
    "SavedSearch",
    # Dashboard
    "VisitorDashboard",
    "DashboardSummary",
    "ActivityTimeline",
    "ActivityItem",
    "QuickActions",
    "QuickAction",
    "SavedHostels",
    "SavedHostelItem",
    "BookingHistory",
    "BookingHistoryItem",
    "RecentSearch",
    "RecentlyViewedHostel",
    "RecommendedHostel",
    "PriceDropAlert",
    "AvailabilityAlert",
    # Favorites
    "FavoriteRequest",
    "FavoritesList",
    "FavoriteHostelItem",
    "FavoriteUpdate",
    "FavoritesExport",
    "FavoriteComparison",
    "FavoriteBulkOperation",
    # Recommendations
    "RecommendationFeedback",
    "RecommendationExplanation",
    "RecommendationReason",
]