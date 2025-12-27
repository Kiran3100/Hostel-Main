"""
Occupancy Analytics API Endpoints.

Provides comprehensive occupancy analytics including:
- Occupancy reports and KPIs
- Trend analysis
- Forecasting
- Seasonal pattern detection
"""

from __future__ import annotations

import logging
from typing import Annotated, List

from fastapi import APIRouter, Depends

from app.schemas.analytics.occupancy_analytics import (
    ForecastData,
    OccupancyKPI,
    OccupancyReport,
    OccupancyTrendPoint,
    SeasonalPattern,
)
from app.services.analytics.occupancy_analytics_service import OccupancyAnalyticsService

from .dependencies import (
    AdminUser,
    ForecastConfig,
    HostelFilter,
    RequiredDateRange,
    TrendConfig,
    get_occupancy_analytics_service,
    handle_analytics_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/occupancy", tags=["analytics:occupancy"])

# Type alias for service dependency
OccupancyService = Annotated[
    OccupancyAnalyticsService,
    Depends(get_occupancy_analytics_service),
]


@router.get(
    "/report",
    response_model=OccupancyReport,
    summary="Get comprehensive occupancy report",
    description="""
    Retrieves a comprehensive occupancy report including:
    - Overall occupancy rate
    - Occupancy by room type
    - Bed-level occupancy
    - Peak occupancy periods
    - Underperforming periods
    - Comparison with previous periods
    """,
    responses={
        200: {"description": "Occupancy report retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_occupancy_report(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: OccupancyService,
) -> OccupancyReport:
    """
    Get comprehensive occupancy report.
    
    Provides detailed occupancy analysis for the
    specified date range.
    """
    try:
        return service.get_report(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching occupancy report: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/kpis",
    response_model=OccupancyKPI,
    summary="Get occupancy KPIs",
    description="""
    Retrieves key performance indicators for occupancy:
    - Average occupancy rate
    - RevPAR (Revenue Per Available Room)
    - ADR (Average Daily Rate)
    - Available room nights
    - Sold room nights
    """,
    responses={
        200: {"description": "Occupancy KPIs retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_occupancy_kpis(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    _admin: AdminUser,
    service: OccupancyService,
) -> OccupancyKPI:
    """
    Get occupancy key performance indicators.
    
    Returns core occupancy metrics for performance
    monitoring and benchmarking.
    """
    try:
        return service.get_kpis(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching occupancy KPIs: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/trend",
    response_model=List[OccupancyTrendPoint],
    summary="Get occupancy trend data",
    description="""
    Retrieves occupancy trend data over time:
    - Daily/weekly/monthly occupancy rates
    - Room nights sold
    - Revenue trends
    - Comparison with previous periods
    
    Supports multiple granularity levels for analysis.
    """,
    responses={
        200: {"description": "Occupancy trends retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_occupancy_trend(
    hostel_filter: HostelFilter,
    date_range: RequiredDateRange,
    trend_config: TrendConfig,
    _admin: AdminUser,
    service: OccupancyService,
) -> List[OccupancyTrendPoint]:
    """
    Get occupancy trends with specified granularity.
    
    Returns time-series occupancy data for visualization
    and pattern analysis.
    """
    try:
        return service.get_trend(
            hostel_id=hostel_filter.hostel_id,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            granularity=trend_config.granularity.value,
        )
    except Exception as e:
        logger.error(f"Error fetching occupancy trends: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/forecast",
    response_model=ForecastData,
    summary="Get occupancy forecast",
    description="""
    Retrieves occupancy forecast using predictive models:
    - Predicted occupancy rates
    - Confidence intervals
    - Expected revenue
    - Recommended actions
    
    Available models:
    - EXPONENTIAL_SMOOTHING (default)
    - LINEAR_REGRESSION
    - MOVING_AVERAGE
    """,
    responses={
        200: {"description": "Occupancy forecast retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_occupancy_forecast(
    hostel_filter: HostelFilter,
    forecast_config: ForecastConfig,
    _admin: AdminUser,
    service: OccupancyService,
) -> ForecastData:
    """
    Get occupancy forecast.
    
    Uses historical data and predictive models to
    forecast future occupancy levels.
    """
    try:
        return service.get_forecast(
            hostel_id=hostel_filter.hostel_id,
            days_ahead=forecast_config.days_ahead,
            model=forecast_config.model.value,
        )
    except Exception as e:
        logger.error(f"Error fetching occupancy forecast: {e}")
        raise handle_analytics_error(e)


@router.get(
    "/seasonal-patterns",
    response_model=List[SeasonalPattern],
    summary="Get seasonal occupancy patterns",
    description="""
    Retrieves detected seasonal patterns in occupancy:
    - Day-of-week patterns
    - Monthly seasonality
    - Holiday effects
    - Event-driven patterns
    - Year-over-year comparisons
    
    Useful for pricing and capacity planning.
    """,
    responses={
        200: {"description": "Seasonal patterns retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
    },
)
def get_seasonal_patterns(
    hostel_filter: HostelFilter,
    _admin: AdminUser,
    service: OccupancyService,
) -> List[SeasonalPattern]:
    """
    Get seasonal occupancy patterns.
    
    Identifies recurring patterns in occupancy data
    to support demand forecasting and pricing strategies.
    """
    try:
        return service.get_seasonal_patterns(hostel_id=hostel_filter.hostel_id)
    except Exception as e:
        logger.error(f"Error fetching seasonal patterns: {e}")
        raise handle_analytics_error(e)