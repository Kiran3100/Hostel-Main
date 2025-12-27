from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.analytics.dashboard_analytics import (
    DashboardMetrics,
    KPIResponse,
    QuickStats,
    RoleSpecificDashboard,
)
from app.services.analytics.dashboard_analytics_service import DashboardAnalyticsService

router = APIRouter(prefix="/dashboard", tags=["analytics:dashboard"])


def get_dashboard_analytics_service(
    db: Session = Depends(deps.get_db),
) -> DashboardAnalyticsService:
    return DashboardAnalyticsService(db=db)


@router.get(
    "",
    response_model=DashboardMetrics,
    summary="Get dashboard metrics for hostel or scope",
)
def get_dashboard_metrics(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: DashboardAnalyticsService = Depends(get_dashboard_analytics_service),
) -> Any:
    return service.get_dashboard_metrics(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/role",
    response_model=RoleSpecificDashboard,
    summary="Get role-specific dashboard configuration",
)
def get_role_specific_dashboard(
    role: Optional[str] = Query(None),
    _current_user=Depends(deps.get_current_user_with_roles),
    service: DashboardAnalyticsService = Depends(get_dashboard_analytics_service),
) -> Any:
    """
    Role can be provided explicitly or derived from current user.
    """
    effective_role = role or _current_user.main_role
    return service.get_role_dashboard(role=effective_role)


@router.get(
    "/quick-stats",
    response_model=QuickStats,
    summary="Get quick statistics for dashboard cards",
)
def get_quick_stats(
    hostel_id: Optional[str] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: DashboardAnalyticsService = Depends(get_dashboard_analytics_service),
) -> Any:
    return service.get_quick_stats(hostel_id=hostel_id)


@router.get(
    "/kpis",
    response_model=List[KPIResponse],
    summary="Get dashboard KPIs with trend data",
)
def get_dashboard_kpis(
    hostel_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _admin=Depends(deps.get_admin_user),
    service: DashboardAnalyticsService = Depends(get_dashboard_analytics_service),
) -> Any:
    return service.get_kpi_timeseries(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )