from __future__ import annotations

from datetime import date as Date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.analytics.supervisor_analytics import (
    SupervisorDashboardAnalytics,
    SupervisorComparison,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.analytics import SupervisorAnalyticsService

router = APIRouter(prefix="/supervisors")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{supervisor_id}/dashboard",
    response_model=SupervisorDashboardAnalytics,
    summary="Get supervisor performance dashboard",
)
async def get_supervisor_dashboard(
    supervisor_id: UUID = Path(..., description="Supervisor ID"),
    hostel_id: UUID = Query(..., description="Hostel ID"),
    period_start: Date = Query(...),
    period_end: Date = Query(...),
    uow: UnitOfWork = Depends(get_uow),
) -> SupervisorDashboardAnalytics:
    """
    Build a performance dashboard for a specific supervisor at a hostel.
    """
    service = SupervisorAnalyticsService(uow)
    try:
        return service.get_supervisor_dashboard(
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/comparison",
    response_model=SupervisorComparison,
    summary="Compare supervisors within a hostel",
)
async def compare_supervisors(
    hostel_id: UUID = Query(..., description="Hostel ID"),
    period_start: Date = Query(...),
    period_end: Date = Query(...),
    uow: UnitOfWork = Depends(get_uow),
) -> SupervisorComparison:
    """
    Compare supervisors on performance metrics within a given hostel and period.
    """
    service = SupervisorAnalyticsService(uow)
    try:
        return service.get_supervisor_comparison(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)