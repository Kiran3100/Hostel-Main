"""
Analytics service layer.

This package provides business logic for analytics generation, aggregation,
export, predictive analytics, and report orchestration across modules.

Version: 2.0.0
Last Updated: 2024
"""

from app.services.analytics.analytics_engine_service import AnalyticsEngineService
from app.services.analytics.analytics_export_service import AnalyticsExportService
from app.services.analytics.booking_analytics_service import BookingAnalyticsService
from app.services.analytics.complaint_analytics_service import ComplaintAnalyticsService
from app.services.analytics.dashboard_analytics_service import DashboardAnalyticsService
from app.services.analytics.financial_analytics_service import FinancialAnalyticsService
from app.services.analytics.occupancy_analytics_service import OccupancyAnalyticsService
from app.services.analytics.platform_analytics_service import PlatformAnalyticsService
from app.services.analytics.predictive_analytics_service import PredictiveAnalyticsService
from app.services.analytics.report_generation_service import ReportGenerationService
from app.services.analytics.supervisor_analytics_service import SupervisorAnalyticsService
from app.services.analytics.visitor_analytics_service import VisitorAnalyticsService

__all__ = [
    # Core Services
    "AnalyticsEngineService",
    "AnalyticsExportService",
    
    # Domain-Specific Analytics
    "BookingAnalyticsService",
    "ComplaintAnalyticsService",
    "DashboardAnalyticsService",
    "FinancialAnalyticsService",
    "OccupancyAnalyticsService",
    "PlatformAnalyticsService",
    "SupervisorAnalyticsService",
    "VisitorAnalyticsService",
    
    # Advanced Services
    "PredictiveAnalyticsService",
    "ReportGenerationService",
]

__version__ = "2.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Comprehensive analytics services for hostel management platform"

# Service metadata
SERVICE_METADATA = {
    "analytics_engine": {
        "description": "Orchestrates analytics across all domains",
        "features": ["parallel_processing", "caching", "metrics_tracking"],
    },
    "analytics_export": {
        "description": "Exports analytics to multiple formats",
        "formats": ["excel", "csv", "json", "pdf"],
    },
    "booking_analytics": {
        "description": "Booking performance and trends",
        "metrics": ["kpis", "funnel", "cancellations", "sources"],
    },
    "complaint_analytics": {
        "description": "Complaint tracking and SLA metrics",
        "metrics": ["kpis", "sla", "trends", "categories", "priorities"],
    },
    "dashboard_analytics": {
        "description": "Role-based dashboard analytics",
        "features": ["widgets", "alerts", "quick_stats", "kpis"],
    },
    "financial_analytics": {
        "description": "Financial reporting and analysis",
        "reports": ["pnl", "cashflow", "ratios", "budget_comparison"],
    },
    "occupancy_analytics": {
        "description": "Occupancy tracking and forecasting",
        "features": ["forecasting", "seasonal_patterns", "breakdowns"],
    },
    "platform_analytics": {
        "description": "Platform-wide multi-tenant analytics",
        "metrics": ["growth", "churn", "system_health", "usage", "revenue"],
    },
    "predictive_analytics": {
        "description": "Predictive modeling and forecasting",
        "models": ["occupancy", "revenue", "demand", "churn"],
    },
    "report_generation": {
        "description": "Custom report creation and scheduling",
        "features": ["templates", "scheduling", "sharing", "permissions"],
    },
    "supervisor_analytics": {
        "description": "Supervisor performance tracking",
        "metrics": ["workload", "performance", "team_analytics"],
    },
    "visitor_analytics": {
        "description": "Visitor behavior and conversion tracking",
        "metrics": ["funnel", "traffic_sources", "engagement", "conversion_paths"],
    },
}

def get_service_info(service_name: str) -> dict:
    """
    Get information about a specific analytics service.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Dictionary containing service metadata
    """
    return SERVICE_METADATA.get(service_name, {})

def list_available_services() -> list:
    """
    List all available analytics services.
    
    Returns:
        List of service names
    """
    return list(SERVICE_METADATA.keys())

def get_version() -> str:
    """
    Get the version of the analytics services package.
    
    Returns:
        Version string
    """
    return __version__