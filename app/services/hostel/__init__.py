# --- File: C:\Hostel-Main\app\services\hostel\__init__.py ---
"""
Hostel services package initialization.

Provides comprehensive business logic layer for hostel management
including core operations, settings, amenities, analytics, comparisons,
media, policies, and onboarding workflows.
"""

from app.services.hostel.hostel_service import HostelService
from app.services.hostel.hostel_settings_service import HostelSettingsService
from app.services.hostel.hostel_amenity_service import HostelAmenityService
from app.services.hostel.hostel_analytics_service import HostelAnalyticsService
from app.services.hostel.hostel_comparison_service import HostelComparisonService
from app.services.hostel.hostel_media_service import HostelMediaService
from app.services.hostel.hostel_policy_service import HostelPolicyService
from app.services.hostel.hostel_onboarding_service import HostelOnboardingService


__all__ = [
    # Core Services
    "HostelService",
    "HostelSettingsService",
    
    # Feature Services
    "HostelAmenityService",
    "HostelAnalyticsService",
    "HostelComparisonService",
    "HostelMediaService",
    "HostelPolicyService",
    
    # Workflow Services
    "HostelOnboardingService",
]


# Service versioning
__version__ = "1.0.0"

# Service metadata
SERVICE_METADATA = {
    "version": __version__,
    "services": {
        "hostel": {
            "class": "HostelService",
            "description": "Core hostel management operations",
            "capabilities": [
                "CRUD operations",
                "Search and discovery",
                "Capacity management",
                "Status management",
                "Analytics integration"
            ]
        },
        "settings": {
            "class": "HostelSettingsService",
            "description": "Hostel operational settings and configuration",
            "capabilities": [
                "Booking settings",
                "Payment configuration",
                "Security settings",
                "Feature flags",
                "Custom settings"
            ]
        },
        "amenity": {
            "class": "HostelAmenityService",
            "description": "Amenity and booking management",
            "capabilities": [
                "Amenity CRUD",
                "Booking management",
                "Maintenance tracking",
                "Usage analytics"
            ]
        },
        "analytics": {
            "class": "HostelAnalyticsService",
            "description": "Performance tracking and insights",
            "capabilities": [
                "Analytics generation",
                "Trend analysis",
                "Performance metrics",
                "Reporting"
            ]
        },
        "comparison": {
            "class": "HostelComparisonService",
            "description": "Competitive analysis and benchmarking",
            "capabilities": [
                "Competitive comparison",
                "Benchmarking",
                "Market intelligence",
                "Recommendations"
            ]
        },
        "media": {
            "class": "HostelMediaService",
            "description": "Media content management",
            "capabilities": [
                "Media upload",
                "Content moderation",
                "Gallery management",
                "Analytics tracking"
            ]
        },
        "policy": {
            "class": "HostelPolicyService",
            "description": "Policy and rules management",
            "capabilities": [
                "Policy CRUD",
                "Version control",
                "Acknowledgments",
                "Violation tracking",
                "Compliance reporting"
            ]
        },
        "onboarding": {
            "class": "HostelOnboardingService",
            "description": "Streamlined hostel setup and configuration",
            "capabilities": [
                "Guided workflow",
                "Template application",
                "Progress tracking",
                "Validation"
            ]
        }
    }
}


def get_service_info() -> dict:
    """
    Get information about available services.
    
    Returns:
        Dictionary with service metadata
    """
    return SERVICE_METADATA


def get_service_version() -> str:
    """
    Get current service layer version.
    
    Returns:
        Version string
    """
    return __version__