from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.analytics.complaint_analytics import (
    CategoryBreakdown,
    ComplaintDashboard,
    ComplaintKPI,
    ComplaintTrend,
    SLAMetrics,
)
from app.services.analytics.complaint_analytics_service import ComplaintAnalyticsService

router = APIRouter(prefix="/complaints", tags=["analytics:complaints"])


def get_complaint_analytics_service(
    db: Session = Depends(deps.get_db),
) -> ComplaintAnalyticsService:
    return ComplaintAnalyticsService(db=db)


@router.get(
    "/dashboard",
    response_model=ComplaintDashboard,
    summary="Get complaint analytics dashboard",
)
def get_complaint_dashboard(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: ComplaintAnalyticsService = Depends(get_complaint_analytics_service),
) -> Any:
    return service.get_dashboard(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/kpis",
    response_model=ComplaintKPI,
    summary="Get complaint KPIs",
)
def get_complaint_kpis(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: ComplaintAnalyticsService = Depends(get_complaint_analytics_service),
) -> Any:
    return service.get_kpis(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/trend",
    response_model=ComplaintTrend,
    summary="Get complaint trend analysis",
)
def get_complaint_trend(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    granularity: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    _admin=Depends(deps.get_admin_user),
    service: ComplaintAnalyticsService = Depends(get_complaint_analytics_service),
) -> Any:
    return service.get_trend(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
    )


@router.get(
    "/categories",
    response_model=CategoryBreakdown,
    summary="Get complaint breakdown by category",
)
def get_category_breakdown(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: ComplaintAnalyticsService = Depends(get_complaint_analytics_service),
) -> Any:
    return service.get_category_breakdown(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/sla",
    response_model=SLAMetrics,
    summary="Get complaint SLA metrics",
)
def get_sla_metrics(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: ComplaintAnalyticsService = Depends(get_complaint_analytics_service),
) -> Any:
    return service.get_sla_metrics(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )