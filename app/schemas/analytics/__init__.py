# --- File: app/schemas/analytics/__init__.py ---
"""
Analytics schemas package.

Comprehensive analytics module providing schemas for:
- Dashboard and KPI metrics
- Financial reporting (P&L, cashflow)
- Occupancy forecasting
- Complaint tracking
- Visitor funnel analysis
- Booking analytics
- Supervisor performance
- Platform-wide metrics
- Custom report generation
"""

# Dashboard analytics
from app.schemas.analytics.dashboard_analytics import (
    DashboardMetrics,
    KPIResponse,
    QuickStats,
    TimeseriesPoint,
    RoleSpecificDashboard,
    AlertNotification,
    DashboardWidget,
)

# Financial analytics
from app.schemas.analytics.financial_analytics import (
    FinancialReport,
    RevenueBreakdown,
    ExpenseBreakdown,
    ProfitAndLossReport,
    CashflowSummary,
    CashflowPoint,
    FinancialRatios,
    BudgetComparison,
    TaxSummary,
)

# Occupancy analytics
from app.schemas.analytics.occupancy_analytics import (
    OccupancyReport,
    OccupancyKPI,
    OccupancyTrendPoint,
    OccupancyByRoomType,
    OccupancyByFloor,
    ForecastData,
    ForecastPoint,
    SeasonalPattern,
)

# Complaint analytics
from app.schemas.analytics.complaint_analytics import (
    ComplaintKPI,
    ComplaintDashboard,
    ComplaintTrend,
    ComplaintTrendPoint,
    CategoryBreakdown,
    PriorityBreakdown,
    SLAMetrics,
)

# Visitor analytics
from app.schemas.analytics.visitor_analytics import (
    VisitorFunnel,
    TrafficSourceAnalytics,
    TrafficSourceMetrics,
    VisitorBehaviorAnalytics,
    SearchBehavior,
    EngagementMetrics,
    ConversionPathAnalysis,
)

# Booking analytics
from app.schemas.analytics.booking_analytics import (
    BookingFunnel,
    BookingKPI,
    BookingTrendPoint,
    CancellationAnalytics,
    BookingAnalyticsSummary,
    BookingSourceMetrics,
)

# Supervisor analytics
from app.schemas.analytics.supervisor_analytics import (
    SupervisorKPI,
    SupervisorDashboardAnalytics,
    SupervisorComparison,
    SupervisorTrendPoint,
    SupervisorWorkload,
    SupervisorPerformanceRating,
    TeamAnalytics,
)

# Platform analytics
from app.schemas.analytics.platform_analytics import (
    PlatformMetrics,
    GrowthMetrics,
    PlatformUsageAnalytics,
    MonthlyMetric,
    TenantMetrics,
    ChurnAnalysis,
    SystemHealthMetrics,
    RevenueMetrics,
)

# Custom reports
from app.schemas.analytics.custom_reports import (
    CustomReportRequest,
    CustomReportDefinition,
    CustomReportResult,
    CustomReportFilter,
    CustomReportField,
    ReportExportRequest,
    ReportSchedule,
    FilterOperator,
    AggregationType,
    ReportFormat,
    ReportModule,
)

__all__ = [
    # Dashboard
    "DashboardMetrics",
    "KPIResponse",
    "QuickStats",
    "TimeseriesPoint",
    "RoleSpecificDashboard",
    "AlertNotification",
    "DashboardWidget",
    
    # Financial
    "FinancialReport",
    "RevenueBreakdown",
    "ExpenseBreakdown",
    "ProfitAndLossReport",
    "CashflowSummary",
    "CashflowPoint",
    "FinancialRatios",
    "BudgetComparison",
    "TaxSummary",
    
    # Occupancy
    "OccupancyReport",
    "OccupancyKPI",
    "OccupancyTrendPoint",
    "OccupancyByRoomType",
    "OccupancyByFloor",
    "ForecastData",
    "ForecastPoint",
    "SeasonalPattern",
    
    # Complaints
    "ComplaintKPI",
    "ComplaintDashboard",
    "ComplaintTrend",
    "ComplaintTrendPoint",
    "CategoryBreakdown",
    "PriorityBreakdown",
    "SLAMetrics",
    
    # Visitor
    "VisitorFunnel",
    "TrafficSourceAnalytics",
    "TrafficSourceMetrics",
    "VisitorBehaviorAnalytics",
    "SearchBehavior",
    "EngagementMetrics",
    "ConversionPathAnalysis",
    
    # Booking
    "BookingFunnel",
    "BookingKPI",
    "BookingTrendPoint",
    "CancellationAnalytics",
    "BookingAnalyticsSummary",
    "BookingSourceMetrics",
    
    # Supervisor
    "SupervisorKPI",
    "SupervisorDashboardAnalytics",
    "SupervisorComparison",
    "SupervisorTrendPoint",
    "SupervisorWorkload",
    "SupervisorPerformanceRating",
    "TeamAnalytics",
    
    # Platform
    "PlatformMetrics",
    "GrowthMetrics",
    "PlatformUsageAnalytics",
    "MonthlyMetric",
    "TenantMetrics",
    "ChurnAnalysis",
    "SystemHealthMetrics",
    "RevenueMetrics",
    
    # Custom reports
    "CustomReportRequest",
    "CustomReportDefinition",
    "CustomReportResult",
    "CustomReportFilter",
    "CustomReportField",
    "ReportExportRequest",
    "ReportSchedule",
    "FilterOperator",
    "AggregationType",
    "ReportFormat",
    "ReportModule",
]