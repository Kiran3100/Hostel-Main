# api/v1/audit/reports.py

from datetime import date
from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.audit.audit_reports import (
    AuditReport,
    UserActivitySummary,
    EntityChangeSummary,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.reporting import AuditReportingService

router = APIRouter(prefix="/reports")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.get(
    "/",
    response_model=AuditReport,
    summary="Get overall audit report",
)
async def get_audit_report(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Optional hostel filter",
    ),
    user_id: Union[UUID, None] = Query(
        None,
        description="Optional user filter",
    ),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> AuditReport:
    """
    Return an overall audit report for the given period, aggregating audit logs,
    overrides, and supervisor activities by entity type and category.
    """
    service = AuditReportingService(uow)
    try:
        return service.get_audit_report(
            hostel_id=hostel_id,
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/user-activity",
    response_model=UserActivitySummary,
    summary="Get user activity summary",
)
async def get_user_activity_summary(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Optional hostel filter",
    ),
    user_id: Union[UUID, None] = Query(
        None,
        description="User ID to summarize activity for",
    ),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> UserActivitySummary:
    """
    Summarize user activity over a period (counts of actions, categories, etc.).
    """
    service = AuditReportingService(uow)
    try:
        return service.get_user_activity_summary(
            hostel_id=hostel_id,
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/entities",
    response_model=List[EntityChangeSummary],
    summary="Get entity change summaries",
)
async def get_entity_change_summaries(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Optional hostel filter",
    ),
    entity_type: Union[str, None] = Query(
        None,
        description="Optional entity type filter (hostel, room, student, etc.)",
    ),
    period_start: date = Query(..., description="Start Date (inclusive)"),
    period_end: date = Query(..., description="End Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> List[EntityChangeSummary]:
    """
    Summarize changes per entity type over a period (counts, categories).
    """
    service = AuditReportingService(uow)
    try:
        return service.get_entity_change_summaries(
            hostel_id=hostel_id,
            entity_type=entity_type,
            period_start=period_start,
            period_end=period_end,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)