# api/v1/analytics/visitors.py

from datetime import date
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.analytics.visitor_analytics import (
    VisitorFunnel,
    TrafficSourceAnalytics,
    VisitorBehaviorAnalytics as VisitorBehaviorAnalyticsSchema,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.analytics import VisitorAnalyticsService

router = APIRouter(prefix="/visitors")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/funnel",
    response_model=VisitorFunnel,
    summary="Get visitor funnel analytics",
)
async def get_visitor_funnel(
    hostel_id: Union[UUID, None] = Query(None, description="Optional hostel filter"),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> VisitorFunnel:
    """
    Return high-level funnel metrics: visits → registrations → bookings.
    """
    service = VisitorAnalyticsService(uow)
    try:
        return service.get_funnel(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/traffic",
    response_model=TrafficSourceAnalytics,
    summary="Get traffic source analytics",
)
async def get_traffic_sources(
    hostel_id: Union[UUID, None] = Query(None, description="Optional hostel filter"),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> TrafficSourceAnalytics:
    """
    Return per-source traffic and conversion analytics.
    """
    service = VisitorAnalyticsService(uow)
    try:
        return service.get_traffic_sources(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/behavior/{visitor_id}",
    response_model=VisitorBehaviorAnalyticsSchema,
    summary="Get aggregated behavior analytics for a visitor",
)
async def get_visitor_behavior(
    visitor_id: UUID = Path(..., description="Visitor ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> VisitorBehaviorAnalyticsSchema:
    """
    Return aggregated behavior metrics for a specific visitor.
    """
    service = VisitorAnalyticsService(uow)
    try:
        return service.get_visitor_behavior(visitor_id=visitor_id)
    except ServiceError as exc:
        raise _map_service_error(exc)