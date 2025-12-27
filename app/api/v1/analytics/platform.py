"""
Platform Analytics API Endpoints.

Provides platform-wide analytics for super administrators:
- Platform metrics and health
- Growth and churn analysis
- Revenue metrics
- Usage analytics
- Tenant (hostel) metrics
"""

from __future__ import annotations

import logging
from typing import Annotated, List

from fastapi import APIRouter, Depends

from app.schemas.analytics.platform_analytics import (
    ChurnAnalysis,
    GrowthMetrics,
    PlatformMetrics,
    PlatformUsageAnalytics,
    RevenueMetrics,
    SystemHealthMetrics,
    TenantMetrics,
)
from app.services.analytics.platform_analytics_service import PlatformAnalyticsService

from .dependencies import (
    DateRange,
    SuperAdminUser,
    get_platform_analytics_service,
    handle_analytics_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platform", tags=["analytics:platform"])

# Type alias for service dependency
PlatformService = Annotated[
    PlatformAnalyticsService,
    Depends(get_platform_analytics_service),
]


@router.get(
    "/metrics",
    response_model=PlatformMetrics,
    summary="Get high-level platform metrics",
    description="""
    Retrieves high-level platform metrics:
    - Total hostels on platform
    - Total active users
    - Total bookings processed
    - Platform revenue
    - Growth indicators
    
    Super admin access required.
    """,
    responses={
        200: {"description": "Platform metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Super admin access required"},
    },
)
def get_platform_metrics(
    date_range: DateRange,
    _super_admin: SuperAdminUser,
    service: PlatformService,
) -> PlatformMetrics:
    """
    Get high-level platform metrics.
    
    Provides executive-level overview of platform
    performance and health.
    """
    try:
        return service.get_platform_metrics(
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching platform metrics: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/growth",
    response_model=GrowthMetrics,
    summary="Get platform growth metrics",
    description="""
    Retrieves platform growth metrics:
    - New hostel signups
    - User acquisition rate
    - Booking volume growth
    - Revenue growth
    - Market expansion indicators
    """,
    responses={
        200: {"description": "Growth metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Super admin access required"},
    },
)
def get_growth_metrics(
    date_range: DateRange,
    _super_admin: SuperAdminUser,
    service: PlatformService,
) -> GrowthMetrics:
    """
    Get platform growth metrics.
    
    Tracks platform expansion and acquisition
    metrics over time.
    """
    try:
        return service.get_growth(
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching growth metrics: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/churn",
    response_model=ChurnAnalysis,
    summary="Get churn analysis",
    description="""
    Retrieves churn analysis:
    - Hostel churn rate
    - User churn rate
    - Churn reasons breakdown
    - At-risk accounts
    - Retention metrics
    """,
    responses={
        200: {"description": "Churn analysis retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Super admin access required"},
    },
)
def get_churn_analysis(
    date_range: DateRange,
    _super_admin: SuperAdminUser,
    service: PlatformService,
) -> ChurnAnalysis:
    """
    Get churn analysis.
    
    Provides insights into customer retention
    and identifies at-risk accounts.
    """
    try:
        return service.get_churn(
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching churn analysis: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/health",
    response_model=SystemHealthMetrics,
    summary="Get system health metrics",
    description="""
    Retrieves system health metrics:
    - API response times
    - Error rates
    - Database performance
    - Service availability
    - Infrastructure status
    """,
    responses={
        200: {"description": "System health metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Super admin access required"},
    },
)
def get_system_health(
    _super_admin: SuperAdminUser,
    service: PlatformService,
) -> SystemHealthMetrics:
    """
    Get system health metrics.
    
    Monitors platform infrastructure health
    and performance indicators.
    """
    try:
        return service.get_system_health()
    except Exception as e:
        logger.error(f"Error fetching system health: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/revenue",
    response_model=RevenueMetrics,
    summary="Get platform revenue metrics",
    description="""
    Retrieves platform revenue metrics:
    - Total platform revenue
    - Revenue by plan/tier
    - Average revenue per hostel
    - Revenue trends
    - Payment success rates
    """,
    responses={
        200: {"description": "Revenue metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Super admin access required"},
    },
)
def get_revenue_metrics(
    date_range: DateRange,
    _super_admin: SuperAdminUser,
    service: PlatformService,
) -> RevenueMetrics:
    """
    Get platform revenue metrics.
    
    Tracks platform monetization and revenue
    performance over time.
    """
    try:
        return service.get_revenue_metrics(
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching revenue metrics: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/usage",
    response_model=PlatformUsageAnalytics,
    summary="Get platform usage analytics",
    description="""
    Retrieves platform usage analytics:
    - Active users by period
    - Feature usage breakdown
    - API call volumes
    - Session metrics
    - Engagement scores
    """,
    responses={
        200: {"description": "Usage analytics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Super admin access required"},
    },
)
def get_platform_usage(
    date_range: DateRange,
    _super_admin: SuperAdminUser,
    service: PlatformService,
) -> PlatformUsageAnalytics:
    """
    Get platform usage analytics.
    
    Analyzes how customers use the platform
    to inform product development.
    """
    try:
        return service.get_usage_analytics(
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching usage analytics: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/tenants",
    response_model=List[TenantMetrics],
    summary="Get metrics per tenant (hostel)",
    description="""
    Retrieves metrics for each tenant on the platform:
    - Hostel performance metrics
    - Usage statistics
    - Payment status
    - Health indicators
    - Growth metrics
    
    Useful for account management and support prioritization.
    """,
    responses={
        200: {"description": "Tenant metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Super admin access required"},
    },
)
def get_tenant_metrics(
    _super_admin: SuperAdminUser,
    service: PlatformService,
) -> List[TenantMetrics]:
    """
    Get metrics per tenant (hostel).
    
    Provides per-hostel analytics for platform
    administration and support.
    """
    try:
        return service.get_tenant_metrics()
    except Exception as e:
        logger.error(f"Error fetching tenant metrics: {e}")
        raise handle_analytics_error(e)