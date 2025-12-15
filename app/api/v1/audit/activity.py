# api/v1/audit/activity.py
from __future__ import annotations

from datetime import date as Date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.audit.supervisor_activity_log import (
    SupervisorActivityCreate,
    SupervisorActivityLogResponse,
    SupervisorActivityDetail,
    SupervisorActivityFilter,
    SupervisorActivitySummary,
    SupervisorActivityTimelinePoint,
)
from app.schemas.common.pagination import PaginatedResponse
from app.services.common.unit_of_work import UnitOfWork
from app.services.audit import SupervisorActivityService

router = APIRouter(prefix="/activity")


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


@router.post(
    "/",
    response_model=SupervisorActivityDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Log supervisor activity",
)
async def log_supervisor_activity(
    payload: SupervisorActivityCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> SupervisorActivityDetail:
    """
    Create a new supervisor activity log entry.
    """
    service = SupervisorActivityService(uow)
    try:
        return service.log_activity(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/",
    response_model=PaginatedResponse[SupervisorActivityLogResponse],
    summary="List supervisor activity logs",
)
async def list_supervisor_activity(
    filters: SupervisorActivityFilter = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedResponse[SupervisorActivityLogResponse]:
    """
    List supervisor activity logs with filters (hostel, supervisor, category, Date range)
    and pagination.
    """
    service = SupervisorActivityService(uow)
    try:
        return service.list_activity(filters=filters)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{activity_id}",
    response_model=SupervisorActivityDetail,
    summary="Get supervisor activity details",
)
async def get_supervisor_activity(
    activity_id: UUID = Path(..., description="Supervisor activity log ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> SupervisorActivityDetail:
    """
    Retrieve details for a specific supervisor activity log entry.
    """
    service = SupervisorActivityService(uow)
    try:
        return service.get_activity(activity_id=activity_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/summary",
    response_model=SupervisorActivitySummary,
    summary="Get supervisor activity summary",
)
async def get_supervisor_activity_summary(
    hostel_id: Optional[UUID] = Query(
        None,
        description="Filter by hostel ID",
    ),
    supervisor_id: Optional[UUID] = Query(
        None,
        description="Filter by supervisor ID",
    ),
    start_date: Optional[Date] = Query(
        None,
        description="Start Date (inclusive)",
    ),
    end_date: Optional[Date] = Query(
        None,
        description="End Date (inclusive)",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> SupervisorActivitySummary:
    """
    Summarize supervisor activity over a period (counts, categories, types, etc.).
    """
    service = SupervisorActivityService(uow)
    try:
        return service.get_summary(
            hostel_id=hostel_id,
            supervisor_id=supervisor_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/timeline",
    response_model=List[SupervisorActivityTimelinePoint],
    summary="Get supervisor activity timeline",
)
async def get_supervisor_activity_timeline(
    hostel_id: Optional[UUID] = Query(
        None,
        description="Filter by hostel ID",
    ),
    supervisor_id: Optional[UUID] = Query(
        None,
        description="Filter by supervisor ID",
    ),
    start_date: Optional[Date] = Query(
        None,
        description="Start Date (inclusive)",
    ),
    end_date: Optional[Date] = Query(
        None,
        description="End Date (inclusive)",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> List[SupervisorActivityTimelinePoint]:
    """
    Return timeline points for supervisor activity for visualization/analysis.
    """
    service = SupervisorActivityService(uow)
    try:
        return service.get_timeline(
            hostel_id=hostel_id,
            supervisor_id=supervisor_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)