"""
Complaint Analytics API Endpoints.

Provides comprehensive complaint analytics including:
- Dashboard overview
- Key Performance Indicators
- Trend analysis
- Category breakdown
- SLA metrics and compliance
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.analytics.complaint_analytics import (
    CategoryBreakdown,
    ComplaintDashboard,
    ComplaintKPI,
    ComplaintTrend,
    SLAMetrics,
)
from app.services.analytics.complaint_analytics_service import ComplaintAnalyticsService

from .dependencies import (
    AdminUser,
    DateRange,
    HostelFilter,
    TrendConfig,
    get_complaint_analytics_service,
    handle_analytics_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/complaints", tags=["analytics:complaints"])

# Type alias for service dependency
ComplaintService = Annotated[
    ComplaintAnalyticsService,
    Depends(get_complaint_analytics_service),
]


@router.get(
    "/dashboard",
    response_model=ComplaintDashboard,
    summary="Get complaint analytics dashboard",
    description="""
    Retrieves a comprehensive complaint analytics dashboard including:
    - Overall complaint statistics
    - Resolution metrics
    - Priority distribution
    - Recent complaint activity
    - Performance indicators
    """,
    responses={
        200: {"description": "Complaint dashboard data retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_complaint_dashboard(
    hostel_filter: HostelFilter,
    date_range: DateRange,
    _admin: AdminUser,
    service: ComplaintService,
) -> ComplaintDashboard:
    """
    Get comprehensive complaint analytics dashboard.
    
    Aggregates all complaint-related metrics into a single
    dashboard view for quick monitoring and analysis.
    """
    try:
        return service.get_dashboard(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching complaint dashboard: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/kpis",
    response_model=ComplaintKPI,
    summary="Get complaint KPIs",
    description="""
    Retrieves key performance indicators for complaints:
    - Total complaints received
    - Resolution rate
    - Average resolution time
    - Customer satisfaction score
    - Escalation rate
    """,
    responses={
        200: {"description": "Complaint KPIs retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_complaint_kpis(
    hostel_filter: HostelFilter,
    date_range: DateRange,
    _admin: AdminUser,
    service: ComplaintService,
) -> ComplaintKPI:
    """
    Get complaint key performance indicators.
    
    Returns core metrics for measuring complaint handling
    performance over the specified time period.
    """
    try:
        return service.get_kpis(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching complaint KPIs: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/trend",
    response_model=ComplaintTrend,
    summary="Get complaint trend analysis",
    description="""
    Retrieves complaint trend data over time with configurable granularity.
    
    Tracks patterns in:
    - Complaint volume
    - Resolution times
    - Category distribution over time
    - Satisfaction trends
    """,
    responses={
        200: {"description": "Complaint trends retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_complaint_trend(
    hostel_filter: HostelFilter,
    date_range: DateRange,
    trend_config: TrendConfig,
    _admin: AdminUser,
    service: ComplaintService,
) -> ComplaintTrend:
    """
    Get complaint trends with specified granularity.
    
    Returns time-series data for visualizing complaint patterns
    and identifying trends over the selected period.
    """
    try:
        return service.get_trend(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            granularity=trend_config.granularity.value,
        )
    except Exception as e:
        logger.error(f"Error fetching complaint trends: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/categories",
    response_model=CategoryBreakdown,
    summary="Get complaint breakdown by category",
    description="""
    Retrieves complaint breakdown by category:
    - Maintenance issues
    - Cleanliness concerns
    - Noise complaints
    - Staff-related issues
    - Amenity problems
    - Other categories
    
    Includes count, percentage, and resolution metrics per category.
    """,
    responses={
        200: {"description": "Category breakdown retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_category_breakdown(
    hostel_filter: HostelFilter,
    date_range: DateRange,
    _admin: AdminUser,
    service: ComplaintService,
) -> CategoryBreakdown:
    """
    Get complaint breakdown by category.
    
    Provides detailed analysis of complaints by type
    to help prioritize improvement areas.
    """
    try:
        return service.get_category_breakdown(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching category breakdown: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/sla",
    response_model=SLAMetrics,
    summary="Get complaint SLA metrics",
    description="""
    Retrieves Service Level Agreement metrics for complaints:
    - Response time compliance
    - Resolution time compliance
    - Escalation adherence
    - SLA breach analysis
    - Performance by priority level
    """,
    responses={
        200: {"description": "SLA metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_sla_metrics(
    hostel_filter: HostelFilter,
    date_range: DateRange,
    _admin: AdminUser,
    service: ComplaintService,
) -> SLAMetrics:
    """
    Get complaint SLA compliance metrics.
    
    Monitors adherence to service level agreements
    and identifies areas for process improvement.
    """
    try:
        return service.get_sla_metrics(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching SLA metrics: {e}")
        raise handle_analytics_error(e)