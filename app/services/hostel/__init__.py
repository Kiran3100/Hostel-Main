# --- File: C:\Hostel-Main\app\services\hostel\__init__.py ---
"""
Hostel service layer.

Provides comprehensive business logic for hostel management including:
- Core hostel CRUD operations and search
- Settings and configuration management
- Amenities management with booking capabilities
- Media asset management
- Policy management with compliance tracking
- Analytics and reporting (occupancy, revenue, bookings, reviews, complaints)
- Cross-hostel comparison and competitive analysis
- Onboarding orchestration with seed data and validation

All services implement:
- Transactional integrity
- Error handling and validation
- Caching where appropriate
- Logging and monitoring
- Progress tracking for long operations
"""

from app.services.hostel.hostel_service import HostelService
from app.services.hostel.hostel_settings_service import HostelSettingsService
from app.services.hostel.hostel_amenity_service import HostelAmenityService
from app.services.hostel.hostel_media_service import HostelMediaService
from app.services.hostel.hostel_policy_service import HostelPolicyService
from app.services.hostel.hostel_analytics_service import HostelAnalyticsService
from app.services.hostel.hostel_comparison_service import HostelComparisonService
from app.services.hostel.hostel_onboarding_service import (
    HostelOnboardingService,
    OnboardingStep
)

__all__ = [
    # Core services
    "HostelService",
    "HostelSettingsService",
    "HostelAmenityService",
    "HostelMediaService",
    "HostelPolicyService",
    
    # Analytics and insights
    "HostelAnalyticsService",
    "HostelComparisonService",
    
    # Onboarding
    "HostelOnboardingService",
    "OnboardingStep",
]

__version__ = "2.0.0"
__author__ = "Hostel Management System"
__description__ = "Comprehensive hostel management service layer"

# Service categories for documentation
SERVICE_CATEGORIES = {
    "core": [
        "HostelService",
        "HostelSettingsService",
    ],
    "features": [
        "HostelAmenityService",
        "HostelMediaService",
        "HostelPolicyService",
    ],
    "analytics": [
        "HostelAnalyticsService",
        "HostelComparisonService",
    ],
    "operations": [
        "HostelOnboardingService",
    ],
}


def get_service_info() -> dict:
    """
    Get information about available services.
    
    Returns:
        Dictionary containing service metadata
    """
    return {
        "version": __version__,
        "description": __description__,
        "services": __all__,
        "categories": SERVICE_CATEGORIES,
        "total_services": len(__all__),
    }


def get_services_by_category(category: str) -> list:
    """
    Get services filtered by category.
    
    Args:
        category: Service category ('core', 'features', 'analytics', 'operations')
        
    Returns:
        List of service class names in the category
    """
    return SERVICE_CATEGORIES.get(category, [])