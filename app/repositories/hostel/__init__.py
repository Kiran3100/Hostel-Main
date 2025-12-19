"""
Hostel repositories package initialization.
"""

from app.repositories.hostel.hostel_repository import HostelRepository
from app.repositories.hostel.hostel_settings_repository import HostelSettingsRepository
from app.repositories.hostel.hostel_aggregate_repository import HostelAggregateRepository
from app.repositories.hostel.hostel_amenity_repository import HostelAmenityRepository
from app.repositories.hostel.hostel_analytics_repository import HostelAnalyticsRepository
from app.repositories.hostel.hostel_comparison_repository import HostelComparisonRepository
from app.repositories.hostel.hostel_media_repository import HostelMediaRepository
from app.repositories.hostel.hostel_policy_repository import HostelPolicyRepository

__all__ = [
    "HostelRepository",
    "HostelSettingsRepository", 
    "HostelAggregateRepository",
    "HostelAmenityRepository",
    "HostelAnalyticsRepository",
    "HostelComparisonRepository",
    "HostelMediaRepository",
    "HostelPolicyRepository",
]