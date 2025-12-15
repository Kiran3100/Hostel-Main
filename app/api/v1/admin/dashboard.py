from __future__ import annotations

from datetime import date as Date
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.analytics.platform_analytics import (
    PlatformMetrics,
    GrowthMetrics,
    PlatformUsageAnalytics,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.admin import SuperAdminDashboardService

router = APIRouter(prefix="/dashboard")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/platform/metrics/latest",
    response_model=PlatformMetrics,
    summary="Get latest platform-wide metrics (super admin)",
)
async def get_latest_platform_metrics(
    uow: UnitOfWork = Depends(get_uow),
) -> PlatformMetrics:
    """
    Fetch the latest platform-level metrics snapshot.

    Backed by SuperAdminDashboardService.
    """
    service = SuperAdminDashboardService(uow)
    try:
        return service.get_latest_platform_metrics()
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/platform/growth",
    response_model=GrowthMetrics,
    summary="Get growth metrics for a period (super admin)",
)
async def get_growth_metrics(
    period_start: Date = Query(..., description="Start Date (inclusive)"),
    period_end: Date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> GrowthMetrics:
    """
    Fetch growth metrics (hostels, revenue, users) for the given period.
    """
    service = SuperAdminDashboardService(uow)
    try:
        return service.get_growth_metrics(period_start=period_start, period_end=period_end)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/platform/usage/latest",
    response_model=PlatformUsageAnalytics,
    summary="Get latest platform usage analytics (super admin)",
)
async def get_latest_platform_usage(
    uow: UnitOfWork = Depends(get_uow),
) -> PlatformUsageAnalytics:
    """
    Fetch the latest API/platform usage analytics snapshot.
    """
    service = SuperAdminDashboardService(uow)
    try:
        return service.get_latest_platform_usage()
    except ServiceError as exc:
        raise _map_service_error(exc)