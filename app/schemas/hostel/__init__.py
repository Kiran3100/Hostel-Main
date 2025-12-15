# --- File: app/schemas/hostel/__init__.py ---
from __future__ import annotations

from app.schemas.hostel.hostel_admin import (
    HostelAdminView,
    HostelCapacityUpdate,
    HostelSettings,
    HostelStatusUpdate,
    HostelVisibilityUpdate,
)
from app.schemas.hostel.hostel_analytics import (
    AnalyticsRequest,
    BookingAnalytics,
    ComplaintAnalytics,
    HostelAnalytics,
    HostelOccupancyStats,
    HostelRevenueStats,
    OccupancyAnalytics,
    RevenueAnalytics,
    ReviewAnalytics,
)
from app.schemas.hostel.hostel_base import (
    HostelBase,
    HostelCreate,
    HostelMediaUpdate,
    HostelSEOUpdate,
    HostelUpdate,
)
from app.schemas.hostel.hostel_comparison import (
    ComparisonItem,
    ComparisonResult,
    HostelComparisonRequest,
)
from app.schemas.hostel.hostel_filter import (
    AdvancedFilters,
    BulkFilterParams,
    HostelFilterParams,
    HostelSortOptions,
)
from app.schemas.hostel.hostel_public import (
    PublicHostelCard,
    PublicHostelList,
    PublicHostelProfile,
    PublicRoomType,
)
from app.schemas.hostel.hostel_response import (
    HostelDetail,
    HostelListItem,
    HostelResponse,
    HostelStats,
)
from app.schemas.hostel.hostel_search import (
    HostelSearchFilters,
    HostelSearchRequest,
    HostelSearchResponse,
    SearchFacets,
)

__all__ = [
    # Base
    "HostelBase",
    "HostelCreate",
    "HostelUpdate",
    "HostelMediaUpdate",
    "HostelSEOUpdate",
    # Response
    "HostelResponse",
    "HostelDetail",
    "HostelListItem",
    "HostelStats",
    # Public
    "PublicHostelProfile",
    "PublicHostelList",
    "PublicHostelCard",
    "PublicRoomType",
    # Admin
    "HostelAdminView",
    "HostelSettings",
    "HostelVisibilityUpdate",
    "HostelCapacityUpdate",
    "HostelStatusUpdate",
    # Search
    "HostelSearchRequest",
    "HostelSearchResponse",
    "HostelSearchFilters",
    "SearchFacets",
    # Filter
    "HostelFilterParams",
    "HostelSortOptions",
    "AdvancedFilters",
    "BulkFilterParams",
    # Analytics
    "HostelAnalytics",
    "OccupancyAnalytics",
    "RevenueAnalytics",
    "BookingAnalytics",
    "ComplaintAnalytics",
    "ReviewAnalytics",
    "HostelOccupancyStats",
    "HostelRevenueStats",
    "AnalyticsRequest",
    # Comparison
    "HostelComparisonRequest",
    "ComparisonResult",
    "ComparisonItem",
]