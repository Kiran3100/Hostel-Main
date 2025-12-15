from __future__ import annotations

from datetime import date as Date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.analytics.financial_analytics import FinancialReport
from app.services.common.unit_of_work import UnitOfWork
from app.services.analytics import FinancialAnalyticsService

router = APIRouter(prefix="/financial")


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
    response_model=FinancialReport,
    summary="Get financial analytics report",
)
async def get_financial_report(
    scope_type: str = Query(
        "hostel",
        description="Scope type: hostel | platform | admin (default hostel)",
    ),
    scope_id: Optional[UUID] = Query(
        None,
        description="Scope ID (hostel_id, admin_id, or null for platform-wide)",
    ),
    period_start: Date = Query(..., description="Start Date (inclusive)"),
    period_end: Date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> FinancialReport:
    """
    Compute a financial analytics report for the given scope and period.

    Includes revenue, expenses, P&L, cashflow, and collection/overdue ratios.
    """
    service = FinancialAnalyticsService(uow)
    try:
        return service.get_financial_report(
            scope_type=scope_type,
            scope_id=scope_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)