# app/services/analytics/__init__.py
"""
Analytics services package.

High-level analytics and reporting over core/service/transaction models:

- AttendanceAnalyticsService: student attendance reports & trends.
- ComplaintAnalyticsService: complaint KPIs and dashboard metrics.
- CustomReportService: generic, schema-driven custom reports.
- DashboardAnalyticsService: dashboard quick stats (hostel/platform/admin).
- FinancialAnalyticsService: revenue/expense, P&L, and cashflow.
- OccupancyAnalyticsService: hostel bed occupancy & trends.
- PlatformAnalyticsService: platform-wide metrics, growth, usage.
- SupervisorAnalyticsService: supervisor performance and comparisons.
"""

from .custom_report_service import CustomReportService
from .dashboard_analytics_service import DashboardAnalyticsService
from .financial_analytics_service import FinancialAnalyticsService
from .occupancy_analytics_service import OccupancyAnalyticsService
from .platform_analytics_service import PlatformAnalyticsService
from .supervisor_analytics_service import SupervisorAnalyticsService
from .visitor_analytics_service import VisitorAnalyticsService

__all__ = [
    "CustomReportService",
    "DashboardAnalyticsService",
    "FinancialAnalyticsService",
    "OccupancyAnalyticsService",
    "PlatformAnalyticsService",
    "SupervisorAnalyticsService",
    "VisitorAnalyticsService",

]