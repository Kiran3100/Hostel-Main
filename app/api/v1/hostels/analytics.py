"""
Hostel Analytics API Endpoints
Provides analytics and statistical data for hostels
"""
from typing import Any, Dict, List
from datetime import date

from fastapi import APIRouter, Depends, Query, HTTPException, status, Path
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_analytics import (
    HostelAnalytics,
    OccupancyStats,
    RevenueStats,
    AnalyticsPeriod,
    TrendData,
)
from app.services.hostel.hostel_analytics_service import HostelAnalyticsService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/hostels/analytics", tags=["hostels:analytics"])


def get_analytics_service(
    db: Session = Depends(deps.get_db)
) -> HostelAnalyticsService:
    """
    Dependency to get hostel analytics service instance
    
    Args:
        db: Database session
        
    Returns:
        HostelAnalyticsService instance
    """
    return HostelAnalyticsService(db=db)


@router.get(
    "/dashboard",
    response_model=HostelAnalytics,
    summary="Get hostel analytics dashboard",
    description="Retrieve comprehensive analytics dashboard for a hostel",
    responses={
        200: {"description": "Analytics data retrieved successfully"},
        400: {"description": "Invalid parameters"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def get_dashboard(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        min_length=1,
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    period: AnalyticsPeriod = Query(
        AnalyticsPeriod.MONTHLY,
        description="Time period for analytics aggregation"
    ),
    start_date: date | None = Query(
        None,
        description="Start date for custom date range"
    ),
    end_date: date | None = Query(
        None,
        description="End date for custom date range"
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelAnalyticsService = Depends(get_analytics_service),
) -> HostelAnalytics:
    """
    Get comprehensive analytics dashboard for a hostel.
    
    Provides metrics including:
    - Occupancy rates
    - Revenue statistics
    - Booking trends
    - Popular room types
    - Student demographics
    
    Args:
        hostel_id: The hostel identifier
        period: Aggregation period (daily, weekly, monthly, yearly)
        start_date: Optional custom start date
        end_date: Optional custom end date
        admin: Current admin user (from dependency)
        service: Analytics service instance
        
    Returns:
        Comprehensive analytics dashboard data
        
    Raises:
        HTTPException: If retrieval fails or hostel not found
    """
    try:
        logger.info(
            f"Admin {admin.id} requesting dashboard for hostel {hostel_id} "
            f"with period {period}"
        )
        
        # Validate date range if provided
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be before end_date")
        
        dashboard = service.get_dashboard(
            hostel_id=hostel_id,
            period=period,
            start_date=start_date,
            end_date=end_date
        )
        
        if not dashboard:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found or no data available"
            )
        
        logger.info(f"Dashboard data retrieved for hostel {hostel_id}")
        return dashboard
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving dashboard: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics dashboard"
        )


@router.get(
    "/occupancy",
    response_model=OccupancyStats,
    summary="Get occupancy statistics",
    description="Retrieve detailed occupancy statistics for a hostel",
    responses={
        200: {"description": "Occupancy stats retrieved successfully"},
        400: {"description": "Invalid parameters"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def get_occupancy_stats(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        min_length=1,
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    period: AnalyticsPeriod = Query(
        AnalyticsPeriod.MONTHLY,
        description="Time period for statistics"
    ),
    room_type: str | None = Query(
        None,
        description="Filter by specific room type"
    ),
    floor: int | None = Query(
        None,
        description="Filter by specific floor",
        ge=0
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelAnalyticsService = Depends(get_analytics_service),
) -> OccupancyStats:
    """
    Get detailed occupancy statistics.
    
    Provides:
    - Current occupancy rate
    - Available beds
    - Occupied beds
    - Historical trends
    - Peak occupancy periods
    
    Args:
        hostel_id: The hostel identifier
        period: Aggregation period
        room_type: Optional room type filter
        floor: Optional floor filter
        admin: Current admin user
        service: Analytics service instance
        
    Returns:
        Detailed occupancy statistics
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.info(
            f"Retrieving occupancy stats for hostel {hostel_id} "
            f"with period {period}"
        )
        
        stats = service.occupancy_stats(
            hostel_id=hostel_id,
            period=period,
            room_type=room_type,
            floor=floor
        )
        
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found or no occupancy data available"
            )
        
        logger.info(f"Occupancy stats retrieved for hostel {hostel_id}")
        return stats
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving occupancy stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve occupancy statistics"
        )


@router.get(
    "/revenue",
    response_model=RevenueStats,
    summary="Get revenue statistics",
    description="Retrieve detailed revenue statistics for a hostel",
    responses={
        200: {"description": "Revenue stats retrieved successfully"},
        400: {"description": "Invalid parameters"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def get_revenue_stats(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        min_length=1,
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    period: AnalyticsPeriod = Query(
        AnalyticsPeriod.MONTHLY,
        description="Time period for statistics"
    ),
    include_projections: bool = Query(
        False,
        description="Include revenue projections for next period"
    ),
    breakdown_by_room_type: bool = Query(
        True,
        description="Include breakdown by room type"
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelAnalyticsService = Depends(get_analytics_service),
) -> RevenueStats:
    """
    Get detailed revenue statistics.
    
    Provides:
    - Total revenue
    - Revenue by room type
    - Revenue trends
    - Payment method breakdown
    - Outstanding payments
    - Projected revenue
    
    Args:
        hostel_id: The hostel identifier
        period: Aggregation period
        include_projections: Whether to include future projections
        breakdown_by_room_type: Whether to include room type breakdown
        admin: Current admin user
        service: Analytics service instance
        
    Returns:
        Detailed revenue statistics
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.info(
            f"Retrieving revenue stats for hostel {hostel_id} "
            f"with period {period}"
        )
        
        stats = service.revenue_stats(
            hostel_id=hostel_id,
            period=period,
            include_projections=include_projections,
            breakdown_by_room_type=breakdown_by_room_type
        )
        
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found or no revenue data available"
            )
        
        logger.info(f"Revenue stats retrieved for hostel {hostel_id}")
        return stats
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving revenue stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve revenue statistics"
        )


@router.get(
    "/trends",
    response_model=List[TrendData],
    summary="Get trend analysis",
    description="Retrieve historical trend data for various metrics",
    responses={
        200: {"description": "Trend data retrieved successfully"},
        400: {"description": "Invalid parameters"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
    },
)
def get_trends(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    metric: str = Query(
        ...,
        description="Metric to analyze (occupancy, revenue, bookings)",
        regex="^(occupancy|revenue|bookings|complaints|maintenance)$"
    ),
    period: AnalyticsPeriod = Query(
        AnalyticsPeriod.MONTHLY,
        description="Time period for trend analysis"
    ),
    points: int = Query(
        12,
        description="Number of data points to return",
        ge=1,
        le=365
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelAnalyticsService = Depends(get_analytics_service),
) -> List[TrendData]:
    """
    Get historical trend data for analysis.
    
    Args:
        hostel_id: The hostel identifier
        metric: The metric to analyze
        period: Aggregation period
        points: Number of historical data points
        admin: Current admin user
        service: Analytics service instance
        
    Returns:
        List of trend data points
    """
    try:
        logger.info(
            f"Retrieving {metric} trends for hostel {hostel_id}"
        )
        
        trends = service.get_trends(
            hostel_id=hostel_id,
            metric=metric,
            period=period,
            points=points
        )
        
        return trends
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving trends: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve trend data"
        )


@router.get(
    "/{hostel_id}/export",
    summary="Export analytics data",
    description="Export analytics data in various formats (CSV, Excel, PDF)",
    responses={
        200: {"description": "Export file generated successfully"},
        400: {"description": "Invalid parameters"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
    },
)
def export_analytics(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    format: str = Query(
        "csv",
        description="Export format",
        regex="^(csv|excel|pdf)$"
    ),
    period: AnalyticsPeriod = Query(
        AnalyticsPeriod.MONTHLY,
        description="Time period for export"
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelAnalyticsService = Depends(get_analytics_service),
) -> Any:
    """
    Export analytics data to file.
    
    Args:
        hostel_id: The hostel identifier
        format: Export file format
        period: Time period for data
        admin: Current admin user
        service: Analytics service instance
        
    Returns:
        File download response
    """
    try:
        logger.info(
            f"Admin {admin.id} exporting analytics for hostel {hostel_id} "
            f"in {format} format"
        )
        
        export_file = service.export_analytics(
            hostel_id=hostel_id,
            format=format,
            period=period
        )
        
        return export_file
        
    except Exception as e:
        logger.error(f"Error exporting analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export analytics data"
        )