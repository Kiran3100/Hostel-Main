from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_analytics import HostelAnalytics
from app.services.hostel.hostel_analytics_service import HostelAnalyticsService

router = APIRouter(prefix="/hostels/analytics", tags=["hostels:analytics"])


def get_analytics_service(db: Session = Depends(deps.get_db)) -> HostelAnalyticsService:
    return HostelAnalyticsService(db=db)


@router.get(
    "/dashboard",
    response_model=HostelAnalytics,
    summary="Get hostel analytics dashboard",
)
def get_dashboard(
    hostel_id: str = Query(...),
    period: str = Query("monthly", regex="^(daily|weekly|monthly|yearly)$"),
    _admin=Depends(deps.get_admin_user),
    service: HostelAnalyticsService = Depends(get_analytics_service),
) -> Any:
    return service.get_dashboard(hostel_id=hostel_id, period=period)


@router.get(
    "/occupancy",
    summary="Get occupancy statistics",
)
def get_occupancy_stats(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: HostelAnalyticsService = Depends(get_analytics_service),
) -> Any:
    return service.occupancy_stats(hostel_id=hostel_id)


@router.get(
    "/revenue",
    summary="Get revenue statistics",
)
def get_revenue_stats(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: HostelAnalyticsService = Depends(get_analytics_service),
) -> Any:
    return service.revenue_stats(hostel_id=hostel_id)