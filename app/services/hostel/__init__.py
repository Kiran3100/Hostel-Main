# app/services/hostel/__init__.py
"""
Hostel-related services.

- HostelService: core Hostel CRUD, visibility and status updates.
- HostelAdminViewService: admin dashboard view & settings.
- HostelAnalyticsService: hostel-level analytics aggregation.
- HostelComparisonService: multi-hostel comparison for admins/visitors.
"""

from .hostel_service import HostelService
from .hostel_admin_view_service import HostelAdminViewService, HostelSettingsStore
from .hostel_analytics_service import HostelAnalyticsService
from .hostel_comparison_service import HostelComparisonService

__all__ = [
    "HostelService",
    "HostelAdminViewService",
    "HostelSettingsStore",
    "HostelAnalyticsService",
    "HostelComparisonService",
]