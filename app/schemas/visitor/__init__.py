# --- File: app/schemas/visitor/__init__.py ---
"""
Visitor schemas package.

This module exports all visitor-related schemas for easy importing
across the application.
"""

from __future__ import annotations

from app.schemas.visitor.visitor_base import (
    VisitorBase,
    VisitorCreate,
    VisitorUpdate,
)
from app.schemas.visitor.visitor_dashboard import (
    AvailabilityAlert,
    BookingHistory,
    BookingHistoryItem,
    PriceDropAlert,
    RecentSearch,
    RecentlyViewedHostel,
    RecommendedHostel,
    SavedHostelItem,
    SavedHostels,
    VisitorDashboard,
)
from app.schemas.visitor.visitor_favorites import (
    FavoriteComparison,
    FavoriteHostelItem,
    FavoriteRequest,
    FavoritesList,
    FavoriteUpdate,
    FavoritesExport,
)
from app.schemas.visitor.visitor_preferences import (
    PreferenceUpdate,
    SavedSearch,
    SearchPreferences,
    VisitorPreferences,
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
    "SearchPreferences",
    "SavedSearch",
    # Dashboard
    "VisitorDashboard",
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
]