# --- File: C:\Hostel-Main\app\models\hostel\__init__.py ---
"""
Hostel models package initialization.
"""

from app.models.hostel.hostel import Hostel
from app.models.hostel.hostel_amenity import (
    AmenityBooking,
    AmenityCategory,
    HostelAmenity,
)
from app.models.hostel.hostel_analytics import (
    HostelAnalytic,
    OccupancyTrend,
    RevenueTrend,
)
from app.models.hostel.hostel_comparison import (
    BenchmarkData,
    CompetitorAnalysis,
    HostelComparison,
)
from app.models.hostel.hostel_media import HostelMedia, MediaCategory
from app.models.hostel.hostel_policy import (
    HostelPolicy,
    PolicyAcknowledgment,
    PolicyViolation,
)
from app.models.hostel.hostel_settings import HostelSettings

__all__ = [
    # Core
    "Hostel",
    # Amenities
    "HostelAmenity",
    "AmenityCategory",
    "AmenityBooking",
    # Analytics
    "HostelAnalytic",
    "OccupancyTrend",
    "RevenueTrend",
    # Comparison
    "HostelComparison",
    "BenchmarkData",
    "CompetitorAnalysis",
    # Media
    "HostelMedia",
    "MediaCategory",
    # Policy
    "HostelPolicy",
    "PolicyAcknowledgment",
    "PolicyViolation",
    # Settings
    "HostelSettings",
]