"""
Analytics models package.

Comprehensive analytics data models providing persistent storage for:
- Booking analytics and conversion tracking
- Complaint management analytics
- Dashboard KPIs and metrics
- Financial P&L and cashflow
- Occupancy tracking and forecasting
- Platform-wide multi-tenant analytics
- Supervisor performance tracking
- Visitor funnel and behavior analytics
- Custom report definitions and results
"""

# Base analytics utilities
from app.models.analytics.base_analytics import (
    BaseAnalyticsModel,
    AnalyticsMixin,
    MetricMixin,
    TrendMixin,
    AggregationMixin,
    CachedAnalyticsMixin,
    HostelScopedMixin,
    ComparisonMixin,
)

# Booking analytics
from app.models.analytics.booking_analytics import (
    BookingKPI,
    BookingTrendPoint,
    BookingFunnelAnalytics,
    CancellationAnalytics,
    BookingSourceMetrics,
    BookingAnalyticsSummary,
)

# Complaint analytics
from app.models.analytics.complaint_analytics import (
    ComplaintKPI,
    SLAMetrics,
    ComplaintTrendPoint,
    CategoryBreakdown,
    PriorityBreakdown,
    ComplaintDashboard,
)

# Dashboard analytics
from app.models.analytics.dashboard_analytics import (
    DashboardKPI,
    TimeseriesMetric,
    DashboardWidget,
    AlertNotification,
    QuickStats,
    RoleSpecificDashboard,
)

# Financial analytics
from app.models.analytics.financial_analytics import (
    RevenueBreakdown,
    ExpenseBreakdown,
    FinancialRatios,
    ProfitAndLossStatement,
    CashflowPoint,
    CashflowSummary,
    BudgetComparison,
    TaxSummary,
    FinancialReport,
)

# Occupancy analytics
from app.models.analytics.occupancy_analytics import (
    OccupancyKPI,
    OccupancyTrendPoint,
    OccupancyByRoomType,
    OccupancyByFloor,
    SeasonalPattern,
    ForecastPoint,
    ForecastData,
    OccupancyReport,
)

# Platform analytics
from app.models.analytics.platform_analytics import (
    TenantMetrics,
    PlatformMetrics,
    MonthlyMetric,
    GrowthMetrics,
    ChurnAnalysis,
    SystemHealthMetrics,
    PlatformUsageAnalytics,
    RevenueMetrics,
)

# Supervisor analytics
from app.models.analytics.supervisor_analytics import (
    SupervisorWorkload,
    SupervisorPerformanceRating,
    SupervisorKPI,
    SupervisorTrendPoint,
    SupervisorComparison,
    TeamAnalytics,
)

# Visitor analytics
from app.models.analytics.visitor_analytics import (
    VisitorFunnel,
    TrafficSourceMetrics,
    SearchBehavior,
    EngagementMetrics,
    VisitorBehaviorAnalytics,
    ConversionPathAnalysis,
    TrafficSourceAnalytics,
)

# Custom reports
from app.models.analytics.custom_reports import (
    CustomReportDefinition,
    ReportSchedule,
    ReportExecutionHistory,
    CachedReportResult,
)

__all__ = [
    # Base
    'BaseAnalyticsModel',
    'AnalyticsMixin',
    'MetricMixin',
    'TrendMixin',
    'AggregationMixin',
    'CachedAnalyticsMixin',
    'HostelScopedMixin',
    'ComparisonMixin',
    
    # Booking
    'BookingKPI',
    'BookingTrendPoint',
    'BookingFunnelAnalytics',
    'CancellationAnalytics',
    'BookingSourceMetrics',
    'BookingAnalyticsSummary',
    
    # Complaint
    'ComplaintKPI',
    'SLAMetrics',
    'ComplaintTrendPoint',
    'CategoryBreakdown',
    'PriorityBreakdown',
    'ComplaintDashboard',
    
    # Dashboard
    'DashboardKPI',
    'TimeseriesMetric',
    'DashboardWidget',
    'AlertNotification',
    'QuickStats',
    'RoleSpecificDashboard',
    
    # Financial
    'RevenueBreakdown',
    'ExpenseBreakdown',
    'FinancialRatios',
    'ProfitAndLossStatement',
    'CashflowPoint',
    'CashflowSummary',
    'BudgetComparison',
    'TaxSummary',
    'FinancialReport',
    
    # Occupancy
    'OccupancyKPI',
    'OccupancyTrendPoint',
    'OccupancyByRoomType',
    'OccupancyByFloor',
    'SeasonalPattern',
    'ForecastPoint',
    'ForecastData',
    'OccupancyReport',
    
    # Platform
    'TenantMetrics',
    'PlatformMetrics',
    'MonthlyMetric',
    'GrowthMetrics',
    'ChurnAnalysis',
    'SystemHealthMetrics',
    'PlatformUsageAnalytics',
    'RevenueMetrics',
    
    # Supervisor
    'SupervisorWorkload',
    'SupervisorPerformanceRating',
    'SupervisorKPI',
    'SupervisorTrendPoint',
    'SupervisorComparison',
    'TeamAnalytics',
    
    # Visitor
    'VisitorFunnel',
    'TrafficSourceMetrics',
    'SearchBehavior',
    'EngagementMetrics',
    'VisitorBehaviorAnalytics',
    'ConversionPathAnalysis',
    'TrafficSourceAnalytics',
    
    # Custom Reports
    'CustomReportDefinition',
    'ReportSchedule',
    'ReportExecutionHistory',
    'CachedReportResult',
]