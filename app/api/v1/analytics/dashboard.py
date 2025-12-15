# api/v1/analytics/dashboard.py

from datetime import date
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.analytics.dashboard_analytics import DashboardMetrics as DashboardMetricsSchema
from app.services.common.unit_of_work import UnitOfWork
from app.services.analytics import DashboardAnalyticsService

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
    "/",
    response_model=DashboardMetricsSchema,
    summary="Get dashboard metrics snapshot for a scope",
)
async def get_dashboard_metrics(
    scope_type: str = Query(..., description="Scope type: hostel | platform | admin"),
    scope_id: Union[UUID, None] = Query(
        None,
        description="Scope ID (hostel_id or admin_id); null for platform scope",
    ),
    period_start: Union[date, None] = Query(
        None,
        description="Start Date (inclusive). If omitted, service will choose a default window.",
    ),
    period_end: Union[date, None] = Query(
        None,
        description="End Date (inclusive). If omitted, service will choose a default window.",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> DashboardMetricsSchema:
    """
    Fetch a pre-aggregated dashboard metrics snapshot for the given scope.

    Backed by DashboardAnalyticsService which wraps `analytics_dashboard_metrics`.
    """
    service = DashboardAnalyticsService(uow)
    try:
        return service.get_dashboard_metrics(
            scope_type=scope_type,
            scope_id=scope_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)