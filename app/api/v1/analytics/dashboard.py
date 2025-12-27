"""
Dashboard Analytics API Endpoints.

Provides centralized dashboard analytics including:
- Aggregated metrics across modules
- Role-specific dashboard configurations
- Quick statistics for dashboard cards
- KPI time-series data
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.analytics.dashboard_analytics import (
    DashboardMetrics,
    KPIResponse,
    QuickStats,
    RoleSpecificDashboard,
)
from app.services.analytics.dashboard_analytics_service import DashboardAnalyticsService

from .dependencies import (
    AdminUser,
    CurrentUserWithRoles,
    DateRange,
    HostelFilter,
    get_dashboard_analytics_service,
    handle_analytics_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["analytics:dashboard"])

# Type alias for service dependency
DashboardService = Annotated[
    DashboardAnalyticsService,
    Depends(get_dashboard_analytics_service),
]


@router.get(
    "",
    response_model=DashboardMetrics,
    summary="Get dashboard metrics for hostel or scope",
    description="""
    Retrieves comprehensive dashboard metrics including:
    - Occupancy overview
    - Revenue summary
    - Booking statistics
    - Complaint status
    - Recent activity feed
    
    Can be filtered by hostel and date range.
    """,
    responses={
        200: {"description": "Dashboard metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_dashboard_metrics(
    hostel_filter: HostelFilter,
    date_range: DateRange,
    _admin: AdminUser,
    service: DashboardService,
) -> DashboardMetrics:
    """
    Get aggregated dashboard metrics.
    
    Provides a unified view of key metrics across all
    analytics modules for the main dashboard display.
    """
    try:
        return service.get_dashboard_metrics(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching dashboard metrics: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/role",
    response_model=RoleSpecificDashboard,
    summary="Get role-specific dashboard configuration",
    description="""
    Retrieves dashboard configuration tailored to user role:
    - Widget layout and visibility
    - Available metrics
    - Quick actions
    - Navigation shortcuts
    
    Role can be explicitly provided or derived from current user.
    """,
    responses={
        200: {"description": "Role-specific dashboard retrieved successfully"},
        401: {"description": "Authentication required"},
    },
)
def get_role_specific_dashboard(
    role: Annotated[
        Optional[str],
        Query(
            description="User role (defaults to current user's role)",
            examples=["admin", "manager", "staff"],
        ),
    ] = None,
    current_user: CurrentUserWithRoles = None,
    service: DashboardService = Depends(get_dashboard_analytics_service),
) -> RoleSpecificDashboard:
    """
    Get role-specific dashboard configuration.
    
    Returns dashboard layout and available widgets based on
    the user's role and permissions.
    """
    try:
        # Use provided role or fall back to user's main role
        effective_role = role or getattr(current_user, "main_role", "staff")
        return service.get_role_dashboard(role=effective_role)
    except Exception as e:
        logger.error(f"Error fetching role dashboard: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/quick-stats",
    response_model=QuickStats,
    summary="Get quick statistics for dashboard cards",
    description="""
    Retrieves quick statistics optimized for dashboard cards:
    - Today's check-ins/check-outs
    - Current occupancy rate
    - Pending complaints
    - Today's revenue
    - Active bookings
    
    Designed for real-time dashboard updates.
    """,
    responses={
        200: {"description": "Quick stats retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_quick_stats(
    hostel_filter: HostelFilter,
    _admin: AdminUser,
    service: DashboardService,
) -> QuickStats:
    """
    Get quick statistics for dashboard cards.
    
    Returns lightweight metrics optimized for frequent
    polling and real-time dashboard updates.
    """
    try:
        return service.get_quick_stats(hostel_id=hostel_filter.hostel_id)
    except Exception as e:
        logger.error(f"Error fetching quick stats: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/kpis",
    response_model=List[KPIResponse],
    summary="Get dashboard KPIs with trend data",
    description="""
    Retrieves key performance indicators with historical trend:
    - Current value
    - Previous period comparison
    - Percentage change
    - Trend direction
    - Sparkline data for visualization
    """,
    responses={
        200: {"description": "Dashboard KPIs retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_dashboard_kpis(
    hostel_filter: HostelFilter,
    date_range: DateRange,
    _admin: AdminUser,
    service: DashboardService,
) -> List[KPIResponse]:
    """
    Get dashboard KPIs with trend data.
    
    Returns KPIs with historical comparison data
    for displaying trends and performance changes.
    """
    try:
        return service.get_kpi_timeseries(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching dashboard KPIs: {e}")
        raise handle_analytics_error(e)