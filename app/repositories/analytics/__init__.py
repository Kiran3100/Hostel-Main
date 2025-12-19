"""
Analytics repositories package.

Provides data access layer for all analytics models with:
- Comprehensive CRUD operations
- Complex query building and optimization
- Aggregation and calculation logic
- Caching integration
- Performance tracking
"""

from app.repositories.analytics.analytics_aggregate_repository import (
    AnalyticsAggregateRepository
)
from app.repositories.analytics.booking_analytics_repository import (
    BookingAnalyticsRepository
)
from app.repositories.analytics.complaint_analytics_repository import (
    ComplaintAnalyticsRepository
)
from app.repositories.analytics.custom_reports_repository import (
    CustomReportsRepository
)
from app.repositories.analytics.dashboard_analytics_repository import (
    DashboardAnalyticsRepository
)
from app.repositories.analytics.financial_analytics_repository import (
    FinancialAnalyticsRepository
)
from app.repositories.analytics.occupancy_analytics_repository import (
    OccupancyAnalyticsRepository
)
from app.repositories.analytics.platform_analytics_repository import (
    PlatformAnalyticsRepository
)
from app.repositories.analytics.supervisor_analytics_repository import (
    SupervisorAnalyticsRepository
)
from app.repositories.analytics.visitor_analytics_repository import (
    VisitorAnalyticsRepository
)

__all__ = [
    'AnalyticsAggregateRepository',
    'BookingAnalyticsRepository',
    'ComplaintAnalyticsRepository',
    'CustomReportsRepository',
    'DashboardAnalyticsRepository',
    'FinancialAnalyticsRepository',
    'OccupancyAnalyticsRepository',
    'PlatformAnalyticsRepository',
    'SupervisorAnalyticsRepository',
    'VisitorAnalyticsRepository',
]