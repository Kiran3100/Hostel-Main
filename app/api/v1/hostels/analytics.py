from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.hostel.hostel_analytics import (
    HostelAnalytics,
    HostelOccupancyStats,
    HostelRevenueStats,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.hostel import HostelAnalyticsService

router = APIRouter()


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{hostel_id}/analytics",
    response_model=HostelAnalytics,
    summary="Get comprehensive analytics for a hostel",
)
async def get_hostel_analytics(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> HostelAnalytics:
    """
    Aggregate analytics for a hostel over a period:
    occupancy, revenue, bookings, complaints, reviews.
    """
    service = HostelAnalyticsService(uow)
    try:
        return service.get_hostel_analytics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{hostel_id}/analytics/occupancy",
    response_model=HostelOccupancyStats,
    summary="Get occupancy stats for a hostel",
)
async def get_hostel_occupancy_stats(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> HostelOccupancyStats:
    """
    Occupancy-focused stats for a hostel (overall and by room type).
    """
    service = HostelAnalyticsService(uow)
    try:
        return service.get_occupancy_stats(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{hostel_id}/analytics/revenue",
    response_model=HostelRevenueStats,
    summary="Get revenue stats for a hostel",
)
async def get_hostel_revenue_stats(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> HostelRevenueStats:
    """
    Revenue-focused stats for a hostel (monthly revenue, per-student metrics, etc.).
    """
    service = HostelAnalyticsService(uow)
    try:
        return service.get_revenue_stats(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)