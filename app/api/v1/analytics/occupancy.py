from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.analytics.occupancy_analytics import (
    ForecastData,
    OccupancyKPI,
    OccupancyReport,
    OccupancyTrendPoint,
    SeasonalPattern,
)
from app.services.analytics.occupancy_analytics_service import OccupancyAnalyticsService

router = APIRouter(prefix="/occupancy", tags=["analytics:occupancy"])


def get_occupancy_analytics_service(
    db: Session = Depends(deps.get_db),
) -> OccupancyAnalyticsService:
    return OccupancyAnalyticsService(db=db)


@router.get(
    "/report",
    response_model=OccupancyReport,
    summary="Get comprehensive occupancy report",
)
def get_occupancy_report(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: OccupancyAnalyticsService = Depends(get_occupancy_analytics_service),
) -> Any:
    return service.get_report(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/kpis",
    response_model=OccupancyKPI,
    summary="Get occupancy KPIs",
)
def get_occupancy_kpis(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: OccupancyAnalyticsService = Depends(get_occupancy_analytics_service),
) -> Any:
    return service.get_kpis(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/trend",
    response_model=List[OccupancyTrendPoint],
    summary="Get occupancy trend data",
)
def get_occupancy_trend(
    hostel_id: Optional[str] = Query(None),
    start_date: date = Query(...),
    end_date: date = Query(...),
    granularity: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    _admin=Depends(deps.get_admin_user),
    service: OccupancyAnalyticsService = Depends(get_occupancy_analytics_service),
) -> Any:
    return service.get_trend(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
    )


@router.get(
    "/forecast",
    response_model=ForecastData,
    summary="Get occupancy forecast",
)
def get_occupancy_forecast(
    hostel_id: Optional[str] = Query(None),
    days_ahead: int = Query(30, ge=1, le=365),
    model: str = Query("EXPONENTIAL_SMOOTHING"),
    _admin=Depends(deps.get_admin_user),
    service: OccupancyAnalyticsService = Depends(get_occupancy_analytics_service),
) -> Any:
    return service.get_forecast(
        hostel_id=hostel_id,
        days_ahead=days_ahead,
        model=model,
    )


@router.get(
    "/seasonal-patterns",
    response_model=List[SeasonalPattern],
    summary="Get seasonal occupancy patterns",
)
def get_seasonal_patterns(
    hostel_id: Optional[str] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: OccupancyAnalyticsService = Depends(get_occupancy_analytics_service),
) -> Any:
    return service.get_seasonal_patterns(hostel_id=hostel_id)