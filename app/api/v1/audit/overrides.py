# api/v1/audit/overrides.py

from datetime import date
from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.audit.admin_override_log import (
    AdminOverrideLogResponse,
    AdminOverrideDetail,
    AdminOverrideSummary,
    AdminOverrideTimelinePoint,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.audit import AdminOverrideAuditService

router = APIRouter(prefix="/overrides")


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
    response_model=List[AdminOverrideLogResponse],
    summary="List admin overrides (audit)",
)
async def list_admin_overrides(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Filter by hostel ID",
    ),
    supervisor_id: Union[UUID, None] = Query(
        None,
        description="Filter by supervisor ID",
    ),
    entity_type: Union[str, None] = Query(
        None,
        description="Filter by entity type (complaint, maintenance, leave, etc.)",
    ),
    entity_id: Union[UUID, None] = Query(
        None,
        description="Filter by entity ID",
    ),
    start_date: Union[date, None] = Query(
        None,
        description="Start Date (inclusive)",
    ),
    end_date: Union[date, None] = Query(
        None,
        description="End Date (inclusive)",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> List[AdminOverrideLogResponse]:
    """
    List admin overrides with optional filters for hostel, supervisor, entity, and period.
    """
    service = AdminOverrideAuditService(uow)
    try:
        return service.list_overrides(
            hostel_id=hostel_id,
            supervisor_id=supervisor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{override_id}",
    response_model=AdminOverrideDetail,
    summary="Get admin override details",
)
async def get_admin_override(
    override_id: UUID = Path(..., description="Override record ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> AdminOverrideDetail:
    """
    Retrieve a detailed view of a specific admin override record.
    """
    service = AdminOverrideAuditService(uow)
    try:
        return service.get_override_detail(override_id=override_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/summary",
    response_model=AdminOverrideSummary,
    summary="Get summary of admin overrides",
)
async def get_admin_override_summary(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Filter by hostel ID",
    ),
    supervisor_id: Union[UUID, None] = Query(
        None,
        description="Filter by supervisor ID",
    ),
    start_date: Union[date, None] = Query(
        None,
        description="Start Date (inclusive)",
    ),
    end_date: Union[date, None] = Query(
        None,
        description="End Date (inclusive)",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> AdminOverrideSummary:
    """
    Summarize admin overrides over a period, grouped by type, hostel, and supervisor.
    """
    service = AdminOverrideAuditService(uow)
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
    response_model=List[AdminOverrideTimelinePoint],
    summary="Get admin override timeline",
)
async def get_admin_override_timeline(
    hostel_id: Union[UUID, None] = Query(
        None,
        description="Filter by hostel ID",
    ),
    supervisor_id: Union[UUID, None] = Query(
        None,
        description="Filter by supervisor ID",
    ),
    start_date: Union[date, None] = Query(
        None,
        description="Start Date (inclusive)",
    ),
    end_date: Union[date, None] = Query(
        None,
        description="End Date (inclusive)",
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> List[AdminOverrideTimelinePoint]:
    """
    Return a timeline of admin overrides across a period for visualization/analysis.
    """
    service = AdminOverrideAuditService(uow)
    try:
        return service.get_timeline(
            hostel_id=hostel_id,
            supervisor_id=supervisor_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)