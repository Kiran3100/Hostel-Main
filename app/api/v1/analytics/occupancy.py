from __future__ import annotations

from datetime import date as Date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.analytics.occupancy_analytics import OccupancyReport
from app.services.common.unit_of_work import UnitOfWork
from app.services.analytics import OccupancyAnalyticsService

router = APIRouter(prefix="/occupancy")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/report",
    response_model=OccupancyReport,
    summary="Get occupancy report for a hostel",
)
async def get_occupancy_report(
    hostel_id: UUID = Query(..., description="Hostel ID"),
    period_start: Date = Query(..., description="Start Date (inclusive)"),
    period_end: Date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> OccupancyReport:
    """
    Build an occupancy report for the given hostel and period.

    Includes KPIs, daily trend, and occupancy by room type.
    """
    service = OccupancyAnalyticsService(uow)
    try:
        return service.get_occupancy_report(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)