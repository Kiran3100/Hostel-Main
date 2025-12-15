# app/services/visitor/__init__.py
"""
Visitor-facing services.

- VisitorService:
    Core profile retrieval and updates for Visitor (public side).

- VisitorDashboardService:
    Visitor dashboard aggregation (favorites, bookings, stats).

- FavoritesService:
    Manage favorites/wishlist for hostels.

- VisitorPreferencesService:
    Manage visitor preferences (budget, room type, notifications, etc.).

- VisitorHostelSearchService:
    Public hostel search facade (visitor_hostel).
"""

from .visitor_service import VisitorService
from .visitor_dashboard_service import VisitorDashboardService
from .favorites_service import FavoritesService
from .visitor_preferences_service import VisitorPreferencesService
from .visitor_hostel_search_service import VisitorHostelSearchService

__all__ = [
    "VisitorService",
    "VisitorDashboardService",
    "FavoritesService",
    "VisitorPreferencesService",
    "VisitorHostelSearchService",
]