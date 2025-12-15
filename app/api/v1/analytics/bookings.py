# api/v1/analytics/bookings.py

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.analytics.booking_analytics import BookingAnalyticsSummary
from app.services.common.unit_of_work import UnitOfWork
from app.services.booking import BookingAnalyticsService

router = APIRouter(prefix="/bookings")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/summary",
    response_model=BookingAnalyticsSummary,
    summary="Get booking analytics for a hostel",
)
async def get_booking_analytics(
    hostel_id: UUID = Query(..., description="Hostel ID"),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> BookingAnalyticsSummary:
    """
    Produce hostel booking analytics: KPIs, daily trends, funnel, cancellations, source conversions.
    """
    service = BookingAnalyticsService(uow)
    try:
        return service.get_booking_analytics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)