from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.admin import (
    MultiHostelDashboard,
    AggregatedStats,
    HostelQuickStats,
    CrossHostelComparison,
)
from app.services.admin.multi_hostel_dashboard_service import MultiHostelDashboardService

router = APIRouter(prefix="/dashboard", tags=["admin:dashboard"])


def get_dashboard_service(
    db: Session = Depends(deps.get_db),
) -> MultiHostelDashboardService:
    return MultiHostelDashboardService(db=db)


@router.get(
    "",
    response_model=MultiHostelDashboard,
    summary="Get multi-hostel dashboard",
)
def get_dashboard(
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> Any:
    return service.generate_dashboard(admin_id=current_admin.id)


@router.post(
    "/refresh",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger dashboard refresh",
)
def refresh_dashboard(
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> Any:
    service.refresh_dashboard(admin_id=current_admin.id)
    return {"detail": "Dashboard refresh triggered"}


@router.get(
    "/stats",
    response_model=AggregatedStats,
    summary="Get aggregated portfolio statistics",
)
def get_aggregated_stats(
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> Any:
    return service.get_aggregated_stats(admin_id=current_admin.id)


@router.get(
    "/hostels/{hostel_id}/quick-stats",
    response_model=HostelQuickStats,
    summary="Get quick stats for a hostel in portfolio",
)
def get_hostel_quick_stats(
    hostel_id: str,
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> Any:
    return service.get_hostel_quick_stats(admin_id=current_admin.id, hostel_id=hostel_id)


@router.get(
    "/comparison",
    response_model=CrossHostelComparison,
    summary="Get cross-hostel comparison",
)
def get_cross_hostel_comparison(
    current_admin=Depends(deps.get_admin_user),
    service: MultiHostelDashboardService = Depends(get_dashboard_service),
) -> Any:
    return service.get_cross_hostel_comparison(admin_id=current_admin.id)