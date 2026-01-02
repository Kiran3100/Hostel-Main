# --- File: app/schemas/hostel/__init__.py ---
"""
Hostel schemas package.

This module re-exports all hostel-related schemas including base schemas,
responses, filters, analytics, amenities, media, policies, and more.
"""

# Base hostel schemas
from app.schemas.hostel.hostel_base import (
    HostelBase,
    HostelCreate,
    HostelMediaUpdate,
    HostelSEOUpdate,
    HostelUpdate,
)

# Response schemas
from app.schemas.hostel.hostel_response import (
    HostelDetail,
    HostelListItem,
    HostelResponse,
    HostelStats,
)

# Public facing schemas
from app.schemas.hostel.hostel_public import (
    PublicHostelCard,
    PublicHostelList,
    PublicHostelListItem,
    PublicHostelProfile,
    PublicHostelSearch,
    PublicRoomType,
)

# Admin and management schemas
from app.schemas.hostel.hostel_admin import (
    BookingSettings,
    HostelAdminView,
    HostelCapacityUpdate,
    HostelSettings,
    HostelSettingsUpdate,
    HostelStatusUpdate,
    HostelVisibilityUpdate,
    NotificationSettings,
    PaymentSettings,
)

# Search and filtering schemas
from app.schemas.hostel.hostel_search import (
    HostelSearchFilters,
    HostelSearchRequest,
    HostelSearchResponse,
    SearchFacets,
)
from app.schemas.hostel.hostel_filter import (
    AdvancedFilters,
    BulkFilterParams,
    HostelFilterParams,
    HostelSortOptions,
)

# Analytics and reporting schemas
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

# Comparison and recommendation schemas
from app.schemas.hostel.hostel_comparison import (
    ComparisonItem,
    ComparisonResult,
    HostelComparisonRequest,
)

# Amenity management schemas
from app.schemas.hostel.hostel_amenity import (
    AmenityAvailability,
    AmenityBookingRequest,
    AmenityBookingResponse,
    AmenityBookingStatus,
    AmenityCreate,
    AmenityUpdate,
    HostelAmenity,
)

# Media management schemas
from app.schemas.hostel.hostel_media import (
    MediaAdd,
    MediaResponse,
    MediaType,
    MediaUpdate,
)

# Policy management schemas
from app.schemas.hostel.hostel_policy import (
    PolicyAcknowledgment,
    PolicyCreate,
    PolicyResponse,
    PolicyType,
    PolicyUpdate,
)

__all__ = [
    # Base schemas
    "HostelBase",
    "HostelCreate",
    "HostelUpdate",
    "HostelMediaUpdate",
    "HostelSEOUpdate",
    
    # Response schemas
    "HostelResponse",
    "HostelDetail",
    "HostelListItem",
    "HostelStats",
    
    # Public schemas
    "PublicHostelProfile",
    "PublicHostelList",
    "PublicHostelCard",
    "PublicHostelListItem",
    "PublicHostelSearch",
    "PublicRoomType",
    
    # Admin schemas
    "HostelAdminView",
    "HostelSettings",
    "HostelSettingsUpdate",
    "HostelVisibilityUpdate",
    "HostelCapacityUpdate",
    "HostelStatusUpdate",
    "NotificationSettings",
    "BookingSettings",
    "PaymentSettings",
    
    # Search schemas
    "HostelSearchRequest",
    "HostelSearchResponse",
    "HostelSearchFilters",
    "SearchFacets",
    
    # Filter schemas
    "HostelFilterParams",
    "HostelSortOptions",
    "AdvancedFilters",
    "BulkFilterParams",
    
    # Analytics schemas
    "HostelAnalytics",
    "OccupancyAnalytics",
    "RevenueAnalytics",
    "BookingAnalytics",
    "ComplaintAnalytics",
    "ReviewAnalytics",
    "HostelOccupancyStats",
    "HostelRevenueStats",
    "AnalyticsRequest",
    
    # Comparison schemas
    "HostelComparisonRequest",
    "ComparisonResult",
    "ComparisonItem",
    
    # Amenity schemas
    "HostelAmenity",
    "AmenityCreate",
    "AmenityUpdate",
    "AmenityBookingRequest",
    "AmenityBookingResponse",
    "AmenityAvailability",
    "AmenityBookingStatus",
    
    # Media schemas
    "MediaType",
    "MediaAdd",
    "MediaUpdate",
    "MediaResponse",
    
    # Policy schemas
    "PolicyType",
    "PolicyCreate",
    "PolicyUpdate",
    "PolicyResponse",
    "PolicyAcknowledgment",
]