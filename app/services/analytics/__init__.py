# --- File: C:\Hostel-Main\app\services\analytics\__init__.py ---
"""
Analytics services package.

Provides business logic layer for all analytics operations with:
- Comprehensive data processing and calculation
- Cross-module orchestration
- Report generation and export
- Predictive analytics and forecasting
- Performance optimization
"""

from app.services.analytics.analytics_engine_service import (
    AnalyticsEngineService
)
from app.services.analytics.booking_analytics_service import (
    BookingAnalyticsService
)
from app.services.analytics.complaint_analytics_service import (
    ComplaintAnalyticsService
)
from app.services.analytics.dashboard_analytics_service import (
    DashboardAnalyticsService
)
from app.services.analytics.financial_analytics_service import (
    FinancialAnalyticsService
)
from app.services.analytics.occupancy_analytics_service import (
    OccupancyAnalyticsService
)
from app.services.analytics.platform_analytics_service import (
    PlatformAnalyticsService
)
from app.services.analytics.supervisor_analytics_service import (
    SupervisorAnalyticsService
)
from app.services.analytics.visitor_analytics_service import (
    VisitorAnalyticsService
)
from app.services.analytics.predictive_analytics_service import (
    PredictiveAnalyticsService
)
from app.services.analytics.report_generation_service import (
    ReportGenerationService
)
from app.services.analytics.analytics_export_service import (
    AnalyticsExportService
)

__all__ = [
    'AnalyticsEngineService',
    'BookingAnalyticsService',
    'ComplaintAnalyticsService',
    'DashboardAnalyticsService',
    'FinancialAnalyticsService',
    'OccupancyAnalyticsService',
    'PlatformAnalyticsService',
    'SupervisorAnalyticsService',
    'VisitorAnalyticsService',
    'PredictiveAnalyticsService',
    'ReportGenerationService',
    'AnalyticsExportService',
]