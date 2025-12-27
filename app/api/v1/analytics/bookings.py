from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.analytics.booking_analytics import (
    BookingAnalyticsSummary,
    BookingFunnel,
    BookingKPI,
    BookingSourceMetrics,
    BookingTrendPoint,
    CancellationAnalytics,
)
from app.services.analytics.booking_analytics_service import BookingAnalyticsService

router = APIRouter(prefix="/bookings", tags=["analytics:bookings"])


def get_booking_analytics_service(
    db: Session = Depends(deps.get_db),
) -> BookingAnalyticsService:
    return BookingAnalyticsService(db=db)


@router.get(
    "/summary",
    response_model=BookingAnalyticsSummary,
    summary="Get booking analytics summary",
)
def get_booking_summary(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: BookingAnalyticsService = Depends(get_booking_analytics_service),
) -> Any:
    """
    High-level summary: KPIs, cancellation analytics, source performance, trends.
    """
    return service.get_summary(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/kpis",
    response_model=BookingKPI,
    summary="Get booking KPIs",
)
def get_booking_kpis(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: BookingAnalyticsService = Depends(get_booking_analytics_service),
) -> Any:
    return service.get_kpis(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/trend",
    response_model=List[BookingTrendPoint],
    summary="Get booking trends",
)
def get_booking_trend(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    granularity: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    _admin=Depends(deps.get_admin_user),
    service: BookingAnalyticsService = Depends(get_booking_analytics_service),
) -> Any:
    return service.get_trend(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
    )


@router.get(
    "/funnel",
    response_model=BookingFunnel,
    summary="Get booking conversion funnel",
)
def get_booking_funnel(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: BookingAnalyticsService = Depends(get_booking_analytics_service),
) -> Any:
    return service.get_funnel(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/cancellations",
    response_model=CancellationAnalytics,
    summary="Get booking cancellation analytics",
)
def get_cancellation_analytics(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: BookingAnalyticsService = Depends(get_booking_analytics_service),
) -> Any:
    return service.get_cancellations(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/sources",
    response_model=List[BookingSourceMetrics],
    summary="Get booking source metrics",
)
def get_booking_sources(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: BookingAnalyticsService = Depends(get_booking_analytics_service),
) -> Any:
    return service.get_source_metrics(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )